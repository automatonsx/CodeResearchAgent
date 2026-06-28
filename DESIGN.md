# DESIGN.md — Scout (Research-Aware Code Review)

Architecture and design rationale. Answers the 10 workshop questions.

---

## 1. What problem are we solving?
Code review is slow, inconsistent, and a single LLM "review this" prompt hallucinates
issues and gives unsourced advice you can't trust. Scout produces a **prioritized,
verified, cited review**: every finding is backed by a real tool result + a best-practice
principle, and the Critic drops anything it can't confirm at a `file:line`.

## 2. Who is the user?
Engineers reviewing a **pull request** or auditing a **small repo** — who want to know
*what's wrong, why (the principle/source), the fix, and the effort* — not just a wall of
linter noise.

## 3. End-to-end flow
```
Input (repo folder OR PR diff)
  → FastAPI POST /review
  → LangGraph: Context → Code-Quality → Security → Dependency → Architecture
               → Test-Review → Grounding → Critic ⇄ (re-check, default off)
                                                          → Report
  → {summary, recommendations[], verdict, score}
  → React report view (severity, file:line, fix, tool evidence, citation)
```
(`standards` mode runs after the graph to also emit a repo-specific SKILL.md.)
Per-node state is streamed to the frontend for the **glass-box view**.

## 4. Why this architecture (multi-agent graph)?
- **Separation of concerns** — Code-Quality and Security have distinct ground-truth tools
  and prompts; each is independently testable.
- **A verify-then-report loop** is the natural shape of trustworthy review; a linear
  fan-out can't drop false positives or re-check weak findings.
- **Tools as ground truth, LLM as structurer** — the deterministic tools anchor the
  findings; the LLM only explains, prioritizes, and suggests fixes.

## 5. What part is "agentic"?
The **Critic → re-check loop.** The Critic re-opens every `file:line`, removes
unverifiable/duplicate findings, flags low-confidence LLM-judgment findings, and *routes
the graph back* to re-analyze with that feedback — a control decision, capped at 2 loops.

## 6. What part is RAG?
The **Grounding step.** A curated best-practices corpus (~67 entries: OWASP, PEP 8/257,
McCabe, bandit rules, etc.) is embedded in **ChromaDB**; each finding is matched to the
principle/source behind it and cited in `research_basis`. Linter rule codes (e.g. `S608`,
`B006`) get an O(1) deterministic citation via `rule_map`; the rest go through a semantic
ChromaDB query. There is **no web search** — citations are corpus-only, so they're
deterministic, auditable, and offline-safe.

## 7. What can go wrong?
- **Hallucinated findings** → Critic drops anything without a verifiable `file:line`.
- **Linter noise / duplicates** → deduped by `(file, line, type)`; severity-prioritized.
- **Tool gaps** (semgrep missing on Windows) → ruff `S` (bandit) + AST cover security.
- **Infinite re-check** → hard loop cap (`MAX_ITERATIONS`, default `0` = loop off; raise via `SCOUT_MAX_ITERATIONS`).
- **Over-confident LLM opinions** → judgment findings must quote code, are low-confidence,
  and get re-checked.

## 8. How do we reduce hallucination?
See README "How we trust the output." Core rules: verifiable `file:line` required; tool
facts vs. LLM opinion separated; every finding cited; Critic loop removes false positives.

## 9. What did we deliberately NOT build (vs. the full vision in plan.md)?
- The 5 domain agents (distributed systems, ML, DB, API, scalability).
- Scraping arxiv/IEEE/ACM — we use a curated mini-corpus instead. (Web search was
  prototyped and then removed entirely; grounding is corpus-only.)
- GitHub Action / inline PR comments; "learns team preferences"; PDF export; auto-merge.
- Large-repo chunking (soft ~80-file cap, `SCOUT_MAX_FILES`); LLM steps are batched
  (`_batch.py`) rather than chunked into a single windowed pass.

**Since shipped (beyond v1):** Python (ruff narrowed to bug rules `F,B,C90,E7,E9` + ast),
JS/TS/React/Vue via **eslint**, other languages via **semgrep** when installed, and a
**dependency CVE audit** (OSV.dev for Python pins + `npm audit` for JS). The
language-agnostic LLM reviewer on raw files is now opt-in only (`SCOUT_GENERIC_REVIEW=1`).
To keep token cost bounded, the architecture/test agents review a **structural skeleton**
(imports + signatures + line counts via ast/tree-sitter), never raw file bodies.

## 10. Two-week plan (if this continued)
- **Week 1:** JS/TS via eslint; semgrep in Docker; large-repo chunking; richer corpus
  with embeddings from Azure; per-finding confidence calibration; planted-issue eval set
  (precision/recall).
- **Week 2:** GitHub Action posting inline PR comments; the 5 domain agents; "learns team
  preferences" memory; PDF/Markdown export; observability (traces, token/cost).

---

## Shared state object
```python
class ReviewState(TypedDict, total=False):
    input_type: str            # "pr_diff" | "repo"
    source: str                # diff text or repo path
    context: dict              # {language, review_path, files, changed_lines, entry_points}
    tool_findings: list        # raw ground-truth from ruff/semgrep/ast
    findings: list             # structured findings (schema below)
    citations: list            # corpus matches per finding
    critique: dict             # {dropped, low_confidence, needs_recheck, notes}
    iterations: int            # loop guard (MAX_ITERATIONS, default 0 = re-check off)
    final_report: dict         # {summary, recommendations, verdict, score, stats}
    agents_executed: list      # ordered names of agents that ran successfully
    standards: dict            # extracted coding standards (standards mode only)
```

## Finding schema
```python
{
  "type": "code | security | dependency | design | testing",
  "severity": "critical | major | minor | suggestion",
  "file": "path", "line": 42,
  "issue": "...", "suggestion": "...", "example": "...",
  "research_basis": ["best-practice citation"],   # from corpus
  "tool_evidence": "ruff/eslint/semgrep/ast/osv/npm-audit code",  # ground truth ("" => LLM judgment)
  "effort": "low | medium | high",
  "confidence": 0.0
}
```

## Critic router
```
if critique["needs_recheck"] and iterations < MAX_ITERATIONS:  → recheck (re-analyze with feedback)
else:                                                          → report
# MAX_ITERATIONS defaults to 0, so by default the Critic runs once and routes to report.
```
