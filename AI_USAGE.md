# AI_USAGE.md — Scout (Research-Aware Code Review)

> **Keep this live from hour one.** Log AI tools used, Skills fired, and the AI-vs-human
> split as you build. Graders read this.

## Tools used
| Tool | What for |
|------|----------|
| Claude Code (CLI) | Repo scaffold, docs, agent/graph/tool code, prompt drafting |
| Custom Skills | `review-repo` (run the review), `build-corpus` (rebuild the RAG index) |
| Azure OpenAI `gpt-4o` | The agents at runtime (structuring tool output, summary) |
| ruff / Python ast | Ground-truth static analysis (quality + bandit security) |
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
  research-aware code review — `ReviewState`, Context/Code-Quality/Security/Grounding/
  Critic/Report agents, ruff+ast ground-truth tools, ChromaDB best-practices corpus,
  PR-diff + repo inputs, and a findings-report UI. Scaffolded with Claude Code.
