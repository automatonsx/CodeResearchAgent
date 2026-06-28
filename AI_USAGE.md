# AI_USAGE.md — Scout (Research-Aware Code Review)

> **Keep this live from hour one.** Log AI tools used, Skills fired, and the AI-vs-human
> split as you build. Graders read this.

## Tools used
| Tool | What for |
|------|----------|
| Claude Code (CLI) | Repo scaffold, docs, agent/graph/tool code, prompt drafting |
| Custom Skills | `review-repo` (run the review), `build-corpus` (rebuild the RAG index) |
| Azure OpenAI `gpt-4o` | Architecture & test-review reasoning (over structural skeletons + docstrings, **not** raw code), structuring tool findings into scored items, and the summary. Detection is NOT done by the LLM. |
| ruff (F,B,C90,E7,E9) + Python ast | Ground-truth static analysis (quality + bandit `S*` security) |
| eslint / semgrep | Ground-truth detection for JS/TS (eslint) and other languages (semgrep) |
| OSV.dev + npm audit | Dependency CVE detection (no LLM, cites OWASP A06) |
| ChromaDB | Best-practices corpus retrieval (citation grounding) |

## Skills fired
| When | Skill | Result |
|------|-------|--------|
| _(log each live run, e.g. "Day 2 — `review-repo` on data/sample_repo → reports/sample.md")_ | | |

## AI vs human split (running estimate)
| Area | AI-generated | Human-designed / edited |
|------|--------------|-------------------------|
| Architecture & graph design | — | ✅ designed by team |
| Tool runners (ruff/ast/diff) | ✅ draft | reviewed |
| Agent prompts | ✅ draft | ✅ tuned |
| Best-practices corpus | ✅ draft | ✅ curated by team |
| Frontend UI | ✅ draft | ✅ branded |
| Docs (this set) | ✅ draft | ✅ edited |

## Log
- **Initial build:** repurposed the multi-agent engine from web research to
  research-aware code review — `ReviewState`, Context/Code-Quality/Security/Dependency/
  Architecture/Test-Review/Grounding/Critic/Report agents, ruff+ast+eslint+semgrep
  ground-truth tools, OSV.dev + npm audit dependency auditing, ChromaDB best-practices
  corpus, PR-diff + repo inputs, and a findings-report UI. Scaffolded with Claude Code.
- **No codebase to the LLM:** detection is done by tools (ruff/eslint/semgrep/OSV);
  the LLM only reasons over structural skeletons (ast for Python, tree-sitter otherwise)
  + first-line docstrings for architecture/test review, and structures tool findings —
  never raw file bodies. The optional `generic_review` LLM reviewer (raw bodies for
  languages no tool covers) is opt-in via `SCOUT_GENERIC_REVIEW=1`.
