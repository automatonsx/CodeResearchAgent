# Scout — Research-Aware Code Review Assistant

> Point it at a **repo or a GitHub URL** → get a **prioritized, cited review report**,
> a **SKILL.md** that teaches Claude Code your project's rules, and a **pre-commit hook**
> that blocks critical violations before they land.

Scout is **not a linter wrapper.** Every finding is grounded in real tool output
(`ruff` / `ast` / generic scanner), verified by a **Critic loop**, and cited against a
curated best-practices corpus — so hallucinated findings get dropped before you see them.

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
| Tavily API key *(optional)* | higher-quality web research in the Architecture agent; free tier works |

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
#   Optionally add:
#     TAVILY_API_KEY

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

### 3. Claude Code MCP (talk to Scout directly in Claude)

Scout ships as an MCP server. Once connected, Claude can call `review_repo`,
`review_pr`, and `onboard_repo` as tools — no terminal needed.

**Connect it:**

1. Open Claude Code in the Scout project folder — it reads `.mcp.json` automatically.
2. Or add it to your user-level Claude Code config:

```json
// ~/.claude.json  →  add under "mcpServers"
{
  "mcpServers": {
    "scout": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/absolute/path/to/scout"
    }
  }
}
```

**Then in any Claude Code session:**

> *"Scout, review https://github.com/martinmimigames/tiny-music-player"*
> → Claude calls `review_repo`, returns the full Markdown report

> *"Onboard this repo: /path/to/myproject"*
> → Claude calls `onboard_repo`, writes SKILL.md + scout-report.md + hook, returns a summary

**Available MCP tools:**

| Tool | What it does |
|---|---|
| `review_repo(path_or_url)` | Full review → Markdown report. Writes nothing. |
| `review_pr(pr_url)` | Review changed lines in a GitHub PR → Markdown report. |
| `onboard_repo(path_or_url, install_hooks)` | Full pipeline → SKILL.md + scout-report.md + pre-commit hook written into the repo. |

---

## CLI — no server

```bash
python -m backend.graph data/sample_repo repo
python -m backend.graph https://github.com/owner/repo github
python -m backend.graph "$(cat data/sample.diff)" pr_diff
```

Reports are saved to `reports/`.

---

## How the agents work

```
Context → Code-Quality → Security → Architecture → Test-Review
       → Grounding → Critic ──(recheck, max 2)──┐
                         └──(validated)──► Report → Standards → END
```

| Agent | Job | Grounded by |
|---|---|---|
| **Context** | Detect languages, walk source files | file system |
| **Code-Quality** | Smells, complexity, dead code | `ruff` + `ast` (Python); LLM (other langs) |
| **Security** | Secrets, injection, unsafe calls | `ruff` bandit rules + generic pattern scanner |
| **Architecture** | Separation of concerns, design patterns | web research + KB |
| **Test-Review** | Coverage gaps, missing edge cases | LLM |
| **Grounding** | Attach best-practice citation to each finding | ChromaDB corpus |
| **Critic** | Re-open each `file:line`, drop false positives | re-reads actual code |
| **Report** | Prioritize, score, verdict | — |
| **Standards** | Extract project rules → SKILL.md | verified findings |

**Languages supported:** any.
- **Python** — `ruff` + `ast` (deeply tool-grounded)
- **JS/TS** — `eslint` (optional) + generic scanner
- **Java, Go, Kotlin, Ruby, PHP, C/C++, Rust, Swift, …** — generic scanner + LLM (Critic-verified)

---

## How Scout avoids hallucinations

1. **No finding without a `file:line`** — the Critic re-opens every finding in the actual file or drops it.
2. **Tool facts vs. LLM opinion** — `ruff`/`ast` results are ground truth; LLM findings must quote code or get dropped.
3. **Every finding cites a best practice** from the curated ChromaDB corpus.
4. **Read-only guard** — after analysis, Scout asserts no source file was modified (`git diff`). Raises an error if violated.

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
│   ├── agents/              # context, code_quality, security, architecture,
│   │                        # test_review, grounding, critic, report, standards
│   ├── tools/               # ruff_runner, generic_scan, ast_utils, web_research
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
**ruff / Python ast** · **ChromaDB** · **MCP** (Model Context Protocol) · **GitPython**
