# ROADMAP — Scout

Where we are vs. the full vision in `CODE_REVIEW_PLAN.md` (and the 12-agent stretch).

## ✅ Done
- LangGraph engine: Context → Code-Quality → Security → Grounding → Critic ⇄ Report.
- Inputs: local repo folder, **public GitHub URL** (shallow clone), PR diff text.
- Any language: Python tool-grounded (ruff + ast); others via secret/pattern scanner +
  quote-grounded LLM reviewer the Critic verifies.
- Grounding: ~13-entry best-practices corpus in ChromaDB (keyword fallback).
- Self-correcting Critic: drops unverifiable/duplicate/hallucinated findings; **re-check
  loop** fires on hallucination/low-confidence (max 2).
- Report: prioritized, scored, verdict, **Markdown export** (`reports/`) + JSON.
- FastAPI (`/review`, `/review/stream`) + React glass-box UI.
- Skills: `review-repo`, `build-corpus`. Docs, sample data, Dockerfile.
- **Eval harness**: `evals/score.py` — recall on planted issues + Critic ablation.
- **eslint** ground truth for JS/TS (optional, like semgrep; bundled flat config in
  `backend/tools/eslint_env`). Falls back to the LLM reviewer if not installed.

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
- [ ] Large-repo chunking (beyond the ~40-file cap).
- [ ] "Learns team preferences" memory; PDF export; auth/multi-user.
- [ ] Observability: token/cost metrics, traces.

## Known cleanup
- `AI_USAGE.md` must be kept **live** during the build (tools used, Skills fired, AI/human %).
