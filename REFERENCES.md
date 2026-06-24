# REFERENCES.md — Scout (Research-Aware Code Review)

Declare every reused repo, template, tool, or snippet, and list the custom features.

## Reused / external
| Source | Used for | License |
|--------|----------|---------|
| [LangGraph](https://langchain-ai.github.io/langgraph/) | State graph + conditional Critic loop | MIT |
| [LangChain](https://python.langchain.com/) | LLM wiring (`langchain-openai`) | MIT |
| [ruff](https://docs.astral.sh/ruff/) | Ground-truth lint (E/F/W/C90/B) + bandit (S) security | MIT |
| [semgrep](https://semgrep.dev/) (optional) | Additional security scanning | LGPL-2.1 |
| Python `ast` (stdlib) | Complexity / docstring / mutable-default checks | PSF |
| [ChromaDB](https://www.trychroma.com/) | Best-practices corpus (RAG citations) | Apache-2.0 |
| [GitPython](https://gitpython.readthedocs.io/) | Diff handling support | BSD-3 |
| [FastAPI](https://fastapi.tiangolo.com/) | Backend REST + streaming | MIT |
| [Vite + React](https://vitejs.dev/) | Frontend scaffold | MIT |

## Corpus sources (cited in findings)
OWASP (Top 10, Secrets/Input-Validation cheat sheets), PEP 8, PEP 257, PEP 484,
McCabe "A Complexity Measure" (1976), Bandit rules, Google Python Style Guide,
Python Logging HOWTO. See [backend/corpus/best_practices.json](backend/corpus/best_practices.json).

## Our custom features (built by Team 7)
1. **Tool-grounded findings** — `ruff`/`ast`/`semgrep` are ground truth; the LLM only
   structures, explains, and scores. Each finding keeps its `tool_evidence`.
2. **Self-correcting Critic loop** — re-opens every `file:line`, drops unverifiable /
   duplicate findings, re-checks low-confidence ones (max 2).
3. **Research-grounded citations** — every finding cites a best-practice principle from a
   curated ChromaDB corpus (`research_basis`).
4. **Two inputs, one engine** — repo folder OR PR diff (diff reconstructed to a temp tree
   so the same tools run on changed code).
5. **Glass-box orchestration view** — live agent graph + Critic drop/flag stats.
6. **Prioritized, scored report** — severity ordering, 0–10 score, verdict.
