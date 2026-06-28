# Scout — Research-Aware Code Review Assistant

> Point it at a **repo or a GitHub URL** → get a **prioritized, cited review report**,
> a **SKILL.md** that teaches Claude Code your project's rules, and a **pre-commit hook**
> that blocks critical violations before they land.

Scout is **not a linter wrapper.** Every finding is grounded in real tool output
(`ruff` / `ast` / `eslint` / `semgrep` / OSV CVE data), verified by a **Critic loop**, and
cited against a curated best-practices corpus — so hallucinated findings get dropped before
you see them. **No codebase is ever sent to the LLM:** the deep-analysis agents see only a
structural skeleton (imports + signatures) and tool findings, never raw file bodies.

---

## What Scout produces for any repo

```
<repo>/
  .claude/
    skills/code-standards/SKILL.md   ← auto-loaded by Claude Code in every session
    scout-report.md                   ← full findings with citations + analysis grade
  .git/hooks/pre-commit               ← blocks CRITICAL issues on every git commit
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | |
| Node 18+ | only for the web UI frontend |
| **Azure OpenAI** API key | `gpt-4o` deployment — Scout's LLM backbone |

---

## Setup (one time)

```bash
# 1. Clone
git clone https://github.com/<your-username>/scout.git
cd scout

# 2. Configure secrets  (.env is gitignored — never committed)
cp .env.example .env
#   Open .env and fill in:
#     AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
#     AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_MODEL, AZURE_OPENAI_API_VERSION

# 3. Install Python dependencies
pip install -r backend/requirements.txt

# 4. Build the best-practices corpus (ChromaDB index used for citations)
python -m backend.corpus.build_index

# 5. (Optional) JS/TS ground-truth linting via eslint
cd backend/tools/eslint_env && npm install && cd ../../..
```

---

## Three ways to use Scout

### 1. One-command repo onboarding (recommended)

Clones (or uses a local path), runs all agents, writes SKILL.md + scout-report.md +
installs the pre-commit hook — everything in one command:

```bash
# GitHub URL
python scripts/onboard_repo.py https://github.com/owner/repo

# Local path
python scripts/onboard_repo.py /path/to/your/repo

# Save a Markdown report too (written to reports/ in Scout's own folder)
python scripts/onboard_repo.py https://github.com/owner/repo --save-report

# Also install the pre-push hook
python scripts/onboard_repo.py https://github.com/owner/repo --pre-push

# Dry run — see what would happen without writing anything
python scripts/onboard_repo.py https://github.com/owner/repo --dry-run
```

After it finishes, commit the artefacts so your whole team gets them:

```bash
cd repos/<repo-name>          # (or your local path)
git add .claude/
git commit -m "chore: add Scout coding standards and review report"
```

---

### 2. Web UI (browser)

```bash
# Terminal 1 — backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** — paste a local path, GitHub URL, or PR diff.
The review streams agent-by-agent as it runs.

---

### 3. Claude Code MCP — Scout in every repo, zero config per repo

Install Scout once. It registers itself globally in Claude Code so it's available
in **every** repo you open — no per-repo setup.

```bash
# Install Scout (anywhere on your machine)
pip install git+https://github.com/<your-username>/scout

# One-time setup: stores API keys globally, registers MCP, builds corpus
scout setup
```

`scout setup` interactively asks for your Azure OpenAI keys, saves them to
`~/.scout/.env`, and patches `~/.claude.json` so Scout's MCP server starts
automatically in every Claude Code session. `~/.scout/.env` takes **priority** over
any `.env` in the repo you're reviewing, so Scout always uses your configured deployment.

**Then open any repo in Claude Code and say:**

> *"Scout, onboard this repo"*
> → Claude calls `onboard_repo(".")`, writes three files into your current repo:
> - `.claude/skills/code-standards/SKILL.md` — auto-loaded by Claude Code from now on
> - `.claude/scout-report.md` — full findings with citations
> - `.git/hooks/pre-commit` — blocks CRITICAL issues on every commit

> *"Just review it, don't write anything"*
> → Claude calls `review_repo(".")`, returns the Markdown report inline

> *"Review this PR"*
> → Claude calls `review_pr("https://github.com/owner/repo/pull/42")`

**Available MCP tools:**

| Tool | What it does |
|---|---|
| `review_repo(path_or_url)` | Full review → Markdown report. Writes nothing. |
| `review_pr(pr_url)` | Review changed lines in a GitHub PR → Markdown report. |
| `onboard_repo(path_or_url, install_hooks)` | Full pipeline → SKILL.md + scout-report.md + pre-commit hook written into the repo. Defaults to current directory. |

---

## CLI — no server

```bash
python -m backend.graph data/sample_repo repo
python -m backend.graph https://github.com/owner/repo github
python -m backend.graph "$(cat data/sample.diff)" pr_diff
```

Reports are saved to `reports/`.

---

## Tuning (environment variables)

All LLM-facing steps are **batched** (`backend/agents/_batch.py`): size-bounded, run
concurrently, with self-healing split-on-failure (a failing batch bisects; worst case one
item is dropped and logged). Calls use JSON mode with a bounded `max_tokens`. Knobs:

| Variable | Default | What it does |
|---|---|---|
| `SCOUT_MAX_FILES` | `80` | Max source files reviewed per run |
| `SCOUT_BATCH_WORKERS` | `4` | Max concurrent LLM calls (primary 429 lever) |
| `SCOUT_BATCH_ITEMS` | `8` | Max files packed into one LLM batch |
| `SCOUT_MAX_ITERATIONS` | `0` | Critic re-check loop passes (`0` = off) |
| `SCOUT_MAX_OUTPUT_TOKENS` | `4000` | Bounded output tokens per LLM call |
| `SCOUT_GENERIC_REVIEW` | `0` | `1` enables the LLM fallback that reads raw non-Python files |
| `SCOUT_SEMGREP_CONFIG` | `auto` | semgrep ruleset for non-Python/JS languages |

---

## How the agents work

```
Context → Code-Quality → Security → Dependency → Architecture → Test-Review
       → Grounding → Critic ──(recheck)──┐
                         └──(validated)──► Report → END
```

The graph itself ends at **Report**. The **Standards** step (which writes `SKILL.md`)
runs *after* the graph in `run_standards()` — that's the path the onboarding flow uses.

| Agent | Job | Grounded by |
|---|---|---|
| **Context** | Detect languages, walk source files | file system |
| **Code-Quality** | Smells, complexity, dead code | `ruff` bug rules `F,B,C90,E7,E9` + `ast` (Python); `eslint` (JS/TS/Vue); `semgrep` (other langs, when installed) |
| **Security** | Secrets, injection, unsafe calls | `ruff` bandit (`S`) rules + `semgrep` |
| **Dependency** | Known CVEs in declared dependencies | **OSV.dev** API (pinned `requirements*.txt`) + `npm audit` (JS lockfile) — no LLM; cites OWASP A06 |
| **Architecture** | Separation of concerns, design patterns | structural skeleton + best-practices corpus + KB |
| **Test-Review** | Coverage gaps, missing edge cases | structural skeleton + LLM |
| **Grounding** | Attach best-practice citation to each finding | ChromaDB corpus |
| **Critic** | Re-open each `file:line`, drop false positives | re-reads actual code |
| **Report** | Prioritize, verdict | — |
| **Standards** | Extract project rules → SKILL.md *(post-graph, onboard only)* | verified findings |

**Languages supported:** any.
- **Python** — `ruff` (bug rules only — pure-formatting `E*`/`W*` are excluded as noise) + `ast` (deeply tool-grounded)
- **JS / TS / React / Vue / Next.js** — `eslint` (bundled env includes typescript-eslint, eslint-plugin-react, eslint-plugin-vue; `.vue` supported)
- **Java, Go, Kotlin, Ruby, PHP, C/C++, Rust, Swift, …** — `semgrep` when installed; optional LLM fallback via `SCOUT_GENERIC_REVIEW=1` (off by default), Critic-verified

---

## How Scout avoids hallucinations

1. **No codebase is sent to the LLM** — Architecture & Test-Review see only a *structural skeleton* (imports + class/function signatures + line counts + first-line docstrings; Python via stdlib `ast`, other languages via tree-sitter, unsupported languages fall back to a small text head). Code-Quality & Security send only tool findings plus a tiny ±2-line snippet (each line capped at 300 chars) — never whole files.
2. **No finding without a `file:line`** — the Critic re-opens every finding in the actual file or drops it.
3. **Tool facts vs. LLM opinion** — `ruff`/`ast`/`eslint`/`semgrep`/OSV results are ground truth; LLM findings must quote code or get dropped.
4. **Every finding cites a best practice** from the curated ChromaDB corpus.
5. **Read-only guard** — after analysis, Scout asserts no source file was modified (`git diff`). Raises an error if violated.

---

## Repo layout

```
.
├── backend/
│   ├── main.py              # FastAPI — POST /review, /review/stream (SSE)
│   ├── graph.py             # LangGraph wiring + run() / run_standards()
│   ├── mcp_server.py        # MCP server — review_repo, review_pr, onboard_repo
│   ├── state.py             # ReviewState (LangGraph)
│   ├── llm.py               # Azure OpenAI client
│   ├── report_md.py         # Markdown report renderer
│   ├── standards_skill.py   # SKILL.md renderer
│   ├── agents/              # context, code_quality, security, dependency,
│   │                        # architecture, test_review, grounding, critic,
│   │                        # report, standards, _batch (concurrent batching)
│   ├── tools/               # ruff_runner, eslint_runner, semgrep_runner,
│   │                        # generic_scan, ast_utils, code_skeleton (tree-sitter),
│   │                        # dep_audit (OSV + npm audit)
│   └── corpus/              # best_practices.json + build_index.py (ChromaDB)
├── frontend/                # React (Vite) — streaming review UI
├── scripts/
│   ├── onboard_repo.py      # one-command onboarding CLI
│   └── install_hooks.py     # install pre-commit / pre-push hooks
├── .claude/skills/          # Claude Code skills for Scout itself
├── .mcp.json                # MCP server config (auto-loaded by Claude Code)
├── .env.example             # copy → .env, fill in API keys
├── data/sample_repo/        # tiny Python repo with intentional bugs (demo)
├── docs/best_practices.json # curated KB — 53 best practices with citations
└── reports/                 # saved review reports
```

---

## CI

`.github/workflows/pr-checks.yml` runs on every PR:
- **Lint + compile** (`ruff` + `compileall`) and **frontend build** — always run, no secrets needed.
- **Scout AI review** — fetches the PR diff, runs the pipeline, posts the report as a PR comment.
  Runs only when Azure OpenAI secrets are set in repo Settings → Secrets → Actions:
  `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.
  Without them, that job skips cleanly.

---

## Tech stack

**React** (Vite) · **FastAPI** · **LangGraph + LangChain** · **Azure OpenAI** `gpt-4o` ·
**ruff / Python ast** · **tree-sitter** (language-pack skeletons) · **eslint / semgrep** ·
**OSV.dev** (dependency CVEs) · **ChromaDB** · **MCP** (Model Context Protocol) · **GitPython**
