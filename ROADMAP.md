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

## 🔜 Next (near-term gaps)
- [ ] **eslint** as ground truth for JS/TS (today JS uses the LLM reviewer). Optional, like
      semgrep — detect + run if available, fall back to the LLM otherwise.
- [ ] **Verify Docker** — build & run `deployment/Dockerfile` end-to-end.
- [ ] **Filter findings to changed lines** in PR-diff mode (use `context.changed_lines`)
      so it comments only on what the PR touched.
- [ ] **PR-URL input** — fetch a GitHub PR's diff via the API (needs a token).
- [ ] **Markdown export in the UI** — a "Download report" button.
- [ ] Expand `expected.json` for a true precision number; add a second labelled repo.

## 🌭 Later (the bigger vision)
- [ ] The 5 domain agents (distributed systems, ML, DB, API, scalability).
- [ ] Real research corpus (arxiv/IEEE) instead of the curated mini-corpus.
- [ ] GitHub Action posting inline PR comments.
- [ ] Large-repo chunking (beyond the ~40-file cap).
- [ ] "Learns team preferences" memory; PDF export; auth/multi-user.
- [ ] Observability: token/cost metrics, traces.

## Known cleanup
- `AI_USAGE.md` must be kept **live** during the build (tools used, Skills fired, AI/human %).
