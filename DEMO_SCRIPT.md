# DEMO_SCRIPT.md — Scout (7 minutes)

Goal: prove it's a **tool-grounded, self-correcting, cited** reviewer — not a linter wrapper.

| Time | Beat | Say / show |
|------|------|------------|
| **0:00–1:00** | **Problem + user** | "A single LLM 'review this' hallucinates issues and gives unsourced advice. Engineers need findings they can trust." |
| **1:00–3:00** | **Architecture** | Walk the graph: Context → Code-Quality → Security → Dependency → Architecture → Test-Review → Grounding → Critic ⇄ re-check → Report. Emphasize **tools = ground truth, Critic = verifier**, the **research citations**, and that **no codebase is sent to the LLM** — architecture/test-review send structural skeletons (ast / tree-sitter) + docstrings, code-quality/security send tool findings + tiny ±2-line snippets. |
| **3:00–5:00** | **Live run** | Run on `data/sample_repo` (or paste `data/sample.diff`). Show the **glass-box** lighting up; point at the **Critic drop/flag stats**; trigger the **`review-repo` Skill**. |
| **5:00–6:00** | **Report** | Findings sorted by severity, each with `file:line`, the **fix**, **🔧 tool evidence** (S602/B006/…), and a **📚 best-practice citation**. Call out the **📦 Dependencies** section (OSV.dev + npm audit, no LLM). Show the verdict + analysis grade. |
| **6:00–7:00** | **AI usage + limits** | AI-generated vs. human-designed (AI_USAGE.md). Name 2–3 limitations (LIMITATIONS.md). |

## Pre-demo checklist
- [ ] `.env` has working `AZURE_OPENAI_*`
- [ ] Backend running from repo root: `uvicorn backend.main:app --reload`
- [ ] Frontend running: `npm run dev`
- [ ] `data/sample_repo` and `data/sample.diff` present (planted issues)
- [ ] One run rehearsed end-to-end (repo mode)
- [ ] `review-repo` Skill verified to save into `reports/`
- [ ] Fallback: a pre-generated report saved in `reports/` if the API is down

## The "Critic drops a false positive" beat
The sample inputs reliably yield real findings (hardcoded secret, SQL injection,
`shell=True`, `eval`, bare except, mutable default). If the LLM emits a low-confidence
**judgment** finding, the Critic flags it and the **re-check loop fires** — call that out
live. Worst case, show the **dropped/duplicate** count in the glass-box stats.
