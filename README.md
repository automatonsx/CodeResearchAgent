# Scout — Research-Aware Code Review Assistant

> Point it at a **repo folder or a PR diff** → get a **prioritized, cited review report**.
> Every finding is grounded in **real tool output + a best-practices corpus**, self-checked
> by a **Critic loop**, and scored. *(Workshop Project 8 — Team 7.)*

Scout is **not a linter wrapper.** The hook: *"Your code has issue X — here's the
principle/source behind it, the fix, and the effort it takes."* The LLM **proposes**;
tools (`ruff`/`ast`/`semgrep`) and the **Critic verify** before anything is shown.

---

## The agents

| Agent | Job | Grounded by |
|-------|-----|-------------|
| **Context Extractor** | Detect languages, find source files to review | file walk / diff parse |
| **Code-Quality Agent** | Smells, complexity, dead code, missing tests | `ruff`+`ast` (Python), `eslint` (JS/TS); LLM reviewer (other langs) |
| **Security Agent** | Secrets, injection, unsafe calls | `ruff` bandit (`S`), `eslint` (no-eval…), `semgrep`*, generic secret/pattern scan |
| **Architecture & Design** | Repo-aware suggestions (separation of concerns, consistency with established patterns) | the project **knowledge base** (`ai/knowledge`) |
| **Grounding** | Attach a best-practice citation to each finding | ChromaDB corpus |
| **Critic** | Re-open each `file:line`; drop false positives → loop | re-reads + verifies quoted code |
| **Report Generator** | Prioritize, score, verdict, summary | — |

\* semgrep is optional (poor native-Windows support); ruff's `S` rules + AST are the fallback.

**Languages:** any. **Python** (ruff + ast) and **JS/TS** (eslint) are deeply
**tool-grounded**. **Other languages** (Go, Java, Ruby, PHP, C/C++, …) are reviewed by a
language-agnostic secret/pattern scanner (ground truth) + an LLM reviewer whose findings
the **Critic verifies** by re-checking the quoted code — so hallucinated findings get
dropped. (eslint is optional, like semgrep — set it up below; otherwise JS falls back to
the LLM reviewer.)

### Orchestration graph (the twist 🟡)

```
Context → Code-Quality → Security → Grounding → Critic ──(recheck, max 2)──┐
                            ▲                                              │
                            └──────────────────────────────────────────────┘
                                                  └──(validated)──► Report → END
```

The **Critic → re-check loop** is what makes Scout *agentic*, not a fan-out pipeline.
It re-opens every `file:line`, drops unverifiable/duplicate findings, and re-checks
low-confidence ones (capped at 2 loops).

---

## How we trust the output (anti-hallucination)

1. **No finding without a verifiable `file:line`** — the Critic re-opens it or drops it.
2. **Tool facts vs. LLM opinion** — `ruff`/`ast`/`semgrep` results are ground truth;
   LLM-judgment findings must quote code and are marked low-confidence for re-check.
3. **Every finding cites a best-practice** from the curated ChromaDB corpus.
4. **Critic loop** removes false positives and re-checks before the report is built.

---

## Tech stack

**React** (Vite) · **FastAPI** · **LangGraph + LangChain** · **Azure OpenAI** `gpt-4o` ·
**ruff / Python ast** (+ optional **semgrep**) · **ChromaDB** (best-practices corpus) ·
**GitPython** (diff support).

Flow: `React → FastAPI → LangGraph (agents via LangChain) → Azure gpt-4o / ruff / ChromaDB`

---

## Quick start

```bash
# 0. Configure secrets
cp .env.example .env            # add AZURE_OPENAI_* (semgrep optional)

# 1. Backend (FastAPI + LangGraph) — run from the REPO ROOT
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload           # http://localhost:8000

# 2. Frontend (React + Vite) — second terminal
cd frontend
npm install && npm run dev                   # http://localhost:5173

# 3. (Optional) eslint ground-truth for JS/TS — without this, JS uses the LLM reviewer
cd backend/tools/eslint_env && npm install
```

Open http://localhost:5173 and pick an input:
- **Repo folder** — a local path (try `data/sample_repo`)
- **GitHub URL** — a public repo; Scout clones it. A `…/tree/<branch>/<subdir>` link
  reviews just that subfolder (try `https://github.com/PyCQA/bandit/tree/main/examples`)
- **PR diff** — paste a unified diff (try `data/sample.diff`)

CLI (no server):
```bash
python -m backend.graph "data/sample_repo" repo
python -m backend.graph "https://github.com/PyCQA/bandit/tree/main/examples" github
python -m backend.graph "$(cat data/sample.diff)" pr_diff
```
> Public repos are shallow-cloned to a temp dir; a soft cap (~60 files) keeps large
> repos demo-fast. Point at a `…/tree/.../subdir` link to focus the review.

---

## Repo layout

```
.
├── README.md  DESIGN.md  AI_USAGE.md  REFERENCES.md  DEMO_SCRIPT.md  LIMITATIONS.md
├── .claude/skills/
│   ├── review-repo/SKILL.md      # graded Skill — review a repo/diff, save report
│   └── build-corpus/SKILL.md     # stretch Skill — (re)build the corpus index
├── backend/
│   ├── main.py                   # POST /review, /review/stream
│   ├── graph.py                  # LangGraph wiring + Critic loop
│   ├── state.py                  # ReviewState
│   ├── llm.py                    # Azure OpenAI client (LangChain)
│   ├── agents/                   # context, code_quality, security, grounding, critic, report
│   ├── tools/                    # ruff_runner, semgrep_runner, ast_utils, diff_utils
│   └── corpus/                   # best_practices.json + build_index.py (ChromaDB)
├── frontend/                     # React (Vite) — input + glass-box + report view
├── evals/                        # planted-issue test set (stretch)
├── deployment/                   # Dockerfile
├── data/                         # sample_repo/ + sample.diff
└── reports/                      # saved reports (review-repo output)
```

## CI — PR checks

[.github/workflows/pr-checks.yml](.github/workflows/pr-checks.yml) runs on every PR:
- **Lint & compile** (ruff + `compileall`) and **frontend build** — always run, no secrets.
- **Scout AI review** — fetches the PR diff, runs the review graph, posts the report as a
  PR comment + uploads it as an artifact. Runs only if Azure OpenAI secrets are set.

To enable the Scout review job, add these in **Settings → Secrets and variables → Actions**:
`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`,
`AZURE_OPENAI_API_VERSION`. (`GITHUB_TOKEN` is provided automatically.) Without them, that
job skips cleanly and the static checks still run.

## Architecture knowledge base (auto-maintained)

After anything merges to `main`, [.github/workflows/kb-update.yml](.github/workflows/kb-update.yml)
distills the diff into a living knowledge base under [ai/knowledge/](ai/knowledge/):
- `architecture.json` — structured source of truth (per-module purpose, files, patterns, decisions)
- `ARCHITECTURE.md` — human-readable rendering
- `CHANGELOG.md` — what each merge changed, architecturally

The KB is committed back to the repo (loop-guarded via `paths-ignore`), so it's versioned
and reviewable. Bootstrap or refresh locally:
```bash
python -m backend.knowledge.update --seed                  # from the current repo
python -m backend.knowledge.update --diff-file merge.diff  # from a merge diff
```
Next: index the KB so reviews become repo-aware. See [ROADMAP.md](ROADMAP.md).

See [DESIGN.md](DESIGN.md) for the architecture rationale and the 2-week roadmap.
