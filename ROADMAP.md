# ROADMAP — Scout

Where we are vs. the full vision in `CODE_REVIEW_PLAN.md` (and the 12-agent stretch).

## ✅ Done
- LangGraph engine: Context → Code-Quality → Security → Dependency → Architecture →
  Test-Review → Grounding → Critic ⇄ Report (5 review agents).
- Inputs: local repo folder, **public GitHub URL** (shallow clone), PR diff text.
- **Multi-language linting (tool-grounded):** Python via ruff bug-rules (F, B, C90, E7,
  E9) + ast; JS/TS/React/Vue via **eslint**; other languages via **semgrep**. The generic
  LLM reviewer is opt-in only (`SCOUT_GENERIC_REVIEW=1`).
- **Dependency / CVE audit (no LLM):** OSV.dev for Python `==` pins + `npm audit` for JS;
  cites OWASP A06, rendered in a "📦 Dependencies" section.
- **No codebase sent to the LLM:** Architecture & Test-Review reason over structural
  skeletons (ast for Python, tree-sitter for others) + docstrings; Code-Quality/Security
  send tool findings + tiny snippets only.
- **Cost/scale:** batched, size-bounded, concurrent, self-healing LLM calls; tunable via
  `SCOUT_MAX_FILES`/`SCOUT_BATCH_WORKERS`/`SCOUT_BATCH_ITEMS`/`SCOUT_MAX_OUTPUT_TOKENS`/etc.
- Grounding: ~13-entry best-practices corpus in ChromaDB (keyword fallback).
- Self-correcting Critic: drops unverifiable/duplicate/hallucinated findings; **re-check
  loop** fires on hallucination/low-confidence (`SCOUT_MAX_ITERATIONS`, default 0).
- Report: prioritized, verdict, analysis-quality grade, **Markdown export** (`reports/`)
  + JSON. (Numeric score removed.)
- FastAPI (`/review`, `/review/stream`) + React glass-box UI.
- Skills: `review-repo`, `build-corpus`. Docs, sample data, Dockerfile.
- **Eval harness**: `evals/score.py` — recall on planted issues + Critic ablation.

## 🔜 Next (near-term gaps)
- [ ] **Verify Docker** — build & run `deployment/Dockerfile` end-to-end (also bundle the
      eslint env into the image).
- [ ] **Filter findings to changed lines** in PR-diff mode (use `context.changed_lines`)
      so it comments only on what the PR touched.
- [ ] **PR-URL input** — fetch a GitHub PR's diff via the API (needs a token).
- [ ] **Markdown export in the UI** — a "Download report" button.
- [ ] Expand `expected.json` for a true precision number; add a second labelled repo.

## 🧠 Knowledge base (in progress)
- [x] **Self-maintaining architecture KB** — `kb-update.yml` distills each merge to `main`
      into `ai/knowledge/` (`architecture.json` = truth, `ARCHITECTURE.md` = readable,
      `CHANGELOG.md` = per-merge log). Seed: `python -m backend.knowledge.update --seed`.
- [x] **Consume the KB in reviews** — an Architecture & Design agent looks up the relevant
      KB modules for the reviewed files and produces repo-aware suggestions (cited "KB: …").
      Active only when the code maps to a known module (your own PRs); quiet on external repos.
- [ ] Index the KB in ChromaDB for fuzzy/cross-module retrieval (currently direct lookup).
- [ ] **External benchmarking** — "what others do better" (cross-repo / industry). Later.

## 🌭 Later (the bigger vision)
- [ ] The 5 domain agents (distributed systems, ML, DB, API, scalability).
- [ ] Real research corpus (arxiv/IEEE) instead of the curated mini-corpus.
- [x] GitHub Action that reviews the PR + posts a summary comment
      (`.github/workflows/pr-checks.yml`). Next: **inline** line comments.
- [x] Full-repo coverage by default (all files reviewed; batching keeps it safe).
      `SCOUT_MAX_FILES` is now an optional cap for cheaper runs, not the default.
- [ ] "Learns team preferences" memory; PDF export; auth/multi-user.
- [ ] Observability: token/cost metrics, traces.

## Known cleanup
- `AI_USAGE.md` must be kept **live** during the build (tools used, Skills fired, AI/human %).
