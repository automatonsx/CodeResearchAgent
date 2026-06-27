# Scout Architecture

Scout is a multi-agent code review pipeline built on LangGraph. It reads a repository or PR diff, runs static analysis tools, routes findings through a chain of specialized agents, validates every finding deterministically, and produces three outputs: a `SKILL.md` coding-standards file, a `scout-report.md` Markdown report, and a `.git/hooks/pre-commit` hook. The pipeline never touches source files; it is read-only by construction.

---

## Current Approach

Scout's design is grounded in two convictions:

1. **Tool-first, LLM-second.** Ruff, semgrep, and AST analysis produce ground-truth findings before any LLM is invoked. LLMs structure those findings and may add judgment calls, but only if they quote the offending code verbatim. The Critic node re-opens the file to verify every quoted snippet.

2. **Corpus-only citations.** All best-practice references come from a curated, local `best_practices.json` (53 practices, indexed in ChromaDB). There is no live web search. This keeps citations deterministic, auditable, and offline-safe. Citations arrive via two paths:
   - **Deterministic (rule_map):** Linter codes like `S608` or `B006` are indexed in `rule_map.py` at import time. A lookup is O(1) with no vector search.
   - **Semantic (ChromaDB):** Findings that have no rule code are matched to practices via a cosine-similarity query, optionally filtered by category (`security`, `code`, `design`, `testing`, `observability`, `api`).

---

## LangGraph Setup

The graph is defined in [backend/graph.py](../backend/graph.py) and compiled from a `StateGraph(ReviewState)`:

```
START
  └─► context
        └─► code_quality
              └─► security
                    └─► architecture
                          └─► test_review
                                └─► grounding
                                      └─► critic
                                            ├─(needs_recheck, iterations < 2)─► recheck ─► code_quality
                                            └─(validated)──────────────────────────────► report ─► END
```

### Key LangGraph concepts used

| Concept | Where |
|---|---|
| `StateGraph(ReviewState)` | `build_graph()` in `graph.py` |
| `add_node` | All 9 nodes registered with `g.add_node(name, fn)` |
| `add_edge` | Linear chain: `context → code_quality → … → critic` |
| `add_conditional_edges` | Critic exit: `critic_router` returns `"recheck"` or `"report"` |
| `graph.invoke(initial_state, {"recursion_limit": 50})` | `run()` and `run_standards()` |

### `_track()` wrapper

Every non-trivial node is wrapped with `_track(name, node_fn)`:

```python
def _track(name: str, node_fn):
    def _wrapped(state: ReviewState) -> ReviewState:
        result = node_fn(state)
        executed = list(state.get("agents_executed", []))
        if name not in executed:
            executed.append(name)
        return {**(result or {}), "agents_executed": executed}
    return _wrapped
```

This lets any downstream consumer see which agents ran successfully, in order, without each agent needing to manage its own bookkeeping.

### `recheck` node

`recheck` is a single-line state transformer: it increments `iterations` and returns. LangGraph then routes back to `code_quality`, which re-runs with the Critic's `critique` dict visible in state. The loop is capped at `MAX_ITERATIONS = 2`.

---

## Shared State: `ReviewState`

Defined in [backend/state.py](../backend/state.py) as a `TypedDict(total=False)` — all fields are optional so partial updates from nodes merge cleanly.

```python
class ReviewState(TypedDict, total=False):
    input_type: str        # "repo" | "pr_diff"
    source: str            # folder path or diff text
    context: dict          # {language, files, entry_points, review_path, changed_lines}
    tool_findings: list    # raw output from ruff / semgrep / AST scanner
    findings: list         # structured findings (validated, annotated)
    citations: list        # corpus matches appended by grounding_node
    critique: dict         # {dropped, low_confidence, needs_recheck, notes}
    iterations: int        # recheck loop counter
    final_report: dict     # {summary, recommendations, verdict, score, stats}
    agents_executed: list  # ordered agent names that ran successfully
    standards: dict        # extracted coding standards (standards_node only)
```

Every node receives the full `ReviewState` and returns a **partial dict** of only the keys it changed. LangGraph merges these updates automatically.

---

## Agents

### 1. `context_node` — [backend/agents/context.py](../backend/agents/context.py)

**Reads from state:** `input_type`, `source`  
**Writes to state:** `context`

Discovers the repository structure: walks the file tree (or parses the diff), detects language, identifies entry points, records `review_path`. For PR mode it also extracts `changed_lines` — a `{file: [line_numbers]}` map used later by the Critic to scope findings to lines the PR actually touched.

---

### 2. `code_quality_node` — [backend/agents/code_quality.py](../backend/agents/code_quality.py)

**Reads from state:** `context`, `tool_findings`, `critique` (on recheck)  
**Writes to state:** `tool_findings` (first pass), `findings`

First pass: runs **ruff** (`E,F,W,C90,S,B` rules) over all Python files. Ruff bundles flake8-bandit (`S` rules), so security ground-truth is captured here even without semgrep.

Calls `structure_findings("code_quality", "code", raw)` — a shared helper that enriches each raw tool finding with a code snippet, sends them to the LLM, and gets back structured findings with issue, severity, effort, and a quoted example. On a recheck pass, the Critic's `critique` dict is appended to the prompt so the LLM avoids re-emitting dropped findings.

---

### 3. `security_node` — [backend/agents/security.py](../backend/agents/security.py)

**Reads from state:** `context`, `tool_findings`, `critique`  
**Writes to state:** `findings`

Runs **semgrep** (if installed) over the repo path. On Windows semgrep is best-effort; the agent falls back gracefully to ruff's `S` rules already captured by `code_quality_node`. Calls `structure_findings("security", "security", raw)`. Each structured finding is then passed through `rule_map.citation_for()` in `_structure.py` to attach an instant corpus citation when the rule code (e.g. `S608`, `S307`) has a direct mapping.

---

### 4. `architecture_node` — [backend/agents/architecture.py](../backend/agents/architecture.py)

**Reads from state:** `context`, `findings`  
**Writes to state:** `findings`

No static analysis tool. Reads up to 12 source files (capped at 2500 chars each), loads the project knowledge base, and queries ChromaDB for up to 8 design-category practices using three queries:

```
"{language} architecture design patterns"
"separation of concerns module structure"
"code organization maintainability"
```

Sends file content + KB + corpus hits to the LLM (`"You are a senior software architect"`). Validates every recommendation against the set of actually-read files — recommendations for files not in scope are discarded. Citations are validated against the corpus IDs returned by the query, so the LLM cannot invent references.

Architecture findings carry `type="design"`, `line=0` (file-level), and `kb_grounded=True` when a KB module was referenced.

---

### 5. `test_review_node` — [backend/agents/test_review.py](../backend/agents/test_review.py)

**Reads from state:** `context`, `findings`  
**Writes to state:** `findings`

Separates files into source vs. test by path convention (`test_*.py`, `*.spec.js`, files under `tests/`, etc.). Extracts public function/class names from source files using `ast.parse` (Python) or regex (JS/TS). Compares them against test function names found in existing test files.

Queries ChromaDB for up to 6 testing-category practices:

```
"{language} unit testing best practices"
"test coverage assertions edge cases"
```

Sends the inventory to the LLM to produce actionable test suggestions. Only findings for files that were actually read are kept.

---

### 6. `grounding_node` — [backend/agents/grounding.py](../backend/agents/grounding.py)

**Reads from state:** `findings`  
**Writes to state:** `findings`, `citations`

No LLM call. Iterates every finding and skips those already cited (by `kb_grounded=True` or an existing `research_basis`). For the rest, constructs a query string from the finding's type, tool evidence, and issue text, then calls ChromaDB `retrieve(query, k=3)`. Attaches up to 2 distinct citations (deduped by title) as `research_basis`.

This is the fallback citation path for findings that `rule_map` couldn't cover deterministically.

---

### 7. `critic_node` + `critic_router` — [backend/agents/critic.py](../backend/agents/critic.py)

**Reads from state:** `findings`, `context`, `iterations`  
**Writes to state:** `findings`, `critique`

The agentic verification layer. No LLM call — pure file I/O and string matching.

For each finding:

1. **File:line verifiable?** Opens the file and checks the line is in range. Drops if not.
2. **Quoted code matches?** For non-tool findings: re-opens the file, reads a ±3-line window around the reported line, and checks whether a 12-character prefix of the quoted example appears in the window. Drops if not (likely hallucinated).
3. **Deduplication.** Collapses the same `(file, line, type)` triple.
4. **Confidence scoring.** Calls `score_finding(f, critic_verified=True)` which produces a `0–1` score based on: tool-grounded, KB-grounded, has research_basis, has a quoted example, critic verified. Low-confidence non-tool findings are flagged.
5. **PR scoping.** If `changed_lines` is present, drops findings more than 2 lines from any changed line (except file-level architecture findings).

`critic_router` inspects the resulting `critique`:

```python
def critic_router(state: ReviewState) -> str:
    critique = state.get("critique", {})
    if critique.get("needs_recheck") and state.get("iterations", 0) < MAX_ITERATIONS:
        return "recheck"
    return "report"
```

If hallucinated findings were dropped or low-confidence findings remain, and the iteration budget allows, it routes back to `code_quality` via the `recheck` node (which increments the counter). Otherwise it routes to `report`.

---

### 8. `report_node` — [backend/agents/report.py](../backend/agents/report.py)

**Reads from state:** `findings`, `citations`, `critique`, `context`, `agents_executed`  
**Writes to state:** `final_report`

Aggregates all findings by severity and category. Computes a score (0–10) weighted by severity counts. Calls the LLM once to produce a prose `summary` and prioritized `recommendations`. Includes stats: total findings, tool-grounded rate, corpus citation rate, agents executed.

---

### 9. `standards_node` — [backend/agents/standards.py](../backend/agents/standards.py)

**Reads from state:** `findings`, `tool_findings`, `context`  
**Writes to state:** `standards`

Not in the main graph — called separately by `run_standards()` after the graph completes. Extracts DO/DON'T rules from findings. Detects frameworks from file content using inline regex patterns (pytest, django, fastapi, flask, react, vue, express). Returns a `standards` dict consumed by `save_skill()` to generate `SKILL.md`.

---

## Grounding System Detail

```
tool finding (e.g. ruff S608)
    │
    ▼
rule_map.citation_for("S608")         ← O(1), built at import time from best_practices.json tags
    │ hit → research_basis attached, skip ChromaDB
    │ miss ↓
    ▼
grounding_node: corpus_retrieve(query, k=3)   ← cosine similarity in ChromaDB
    │ returns up to 2 distinct practices
    ▼
finding.research_basis = ["Use parameterized queries — OWASP Top 10 A03:2021"]
```

`best_practices.json` has 53 practices, each with a `category` field (`security`, `code`, `design`, `testing`, `observability`, `api`). ChromaDB stores category in metadata; `retrieve(query, k, category=...)` passes `where={"category": category}` so architecture queries don't accidentally surface testing practices.

---

## Three Outputs

### `SKILL.md`

Generated by `save_skill()` in [backend/standards_skill.py](../backend/standards_skill.py) after `standards_node` runs. Written to `<repo>/.claude/skills/code-standards/SKILL.md` so Claude Code auto-discovers it on every session in that repo. Contains DO/DON'T rules and the pre-commit command.

### `scout-report.md`

Generated by `save_report_to_dir()` in [backend/report_md.py](../backend/report_md.py). Written to `<repo>/.claude/scout-report.md`. Markdown table of all findings with severity, file:line, issue, and corpus citation. Includes a stats block: score, finding count by category, corpus citation rate.

### `.git/hooks/pre-commit`

Generated by `scripts/install_hooks.py`. A deterministic shell script that runs ruff + a pattern scan in under 1 second. No LLM call — designed to be fast enough to run on every commit without friction.

---

## MCP Server and CLI

**MCP server** (`backend/mcp_server.py`): exposes three tools via `FastMCP` over stdio transport:
- `review_repo(path)` → calls `run(path, "repo")`
- `review_pr(diff)` → calls `run(diff, "pr_diff")`
- `onboard_repo(path)` → calls `run_standards(path)`, installs hook

**CLI** (`backend/graph.py __main__`): `python -m backend.graph <path> [--standards] [--save] [--install-hooks]`

**Installable** (`pyproject.toml`): `pip install -e .` adds a `scout` entry point.

---

## Read-Only Guarantee

Before the graph runs, `_dirty_source_files(review_path)` snapshots which files already have uncommitted changes. After the graph finishes, `_assert_repo_unmodified()` compares the post-run dirty set against that snapshot. Only *new* modifications introduced by the pipeline raise a `RuntimeError`. Pre-existing uncommitted changes are excluded. Subprocess calls use `encoding="utf-8", errors="replace"` throughout to handle non-ASCII filenames on Windows without crashing.
