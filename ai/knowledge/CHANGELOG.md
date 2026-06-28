# Knowledge-Base Changelog

## 2026-06-28 · scalable tool-grounded review + dependency audit

Expanded the pipeline to five review agents: Context → Code-Quality → Security → Dependency → Architecture → Test-Review → Grounding → Critic → Report. Added a new Dependency agent (no LLM) that audits declared dependencies for known CVEs — Python pins via OSV.dev and JS via `npm audit` — citing OWASP A06 and rendering a "📦 Dependencies" section. Stopped sending any codebase to the LLM: Architecture and Test-Review now reason over structural skeletons (stdlib `ast` for Python, tree-sitter for other languages) plus docstrings, while Code-Quality and Security send tool findings and tiny snippets only. Reworked detection to ruff bug-rules (F, B, C90, E7, E9; formatting rules dropped) + ast for Python, eslint for JS/TS/React/Vue, and semgrep for other languages, with the generic LLM reviewer now opt-in via `SCOUT_GENERIC_REVIEW=1`. Made the pipeline scale with batched, size-bounded, concurrent and self-healing LLM calls, governed by new env knobs (`SCOUT_MAX_FILES`, `SCOUT_BATCH_WORKERS`, `SCOUT_BATCH_ITEMS`, `SCOUT_MAX_ITERATIONS`, `SCOUT_MAX_OUTPUT_TOKENS`, `SCOUT_GENERIC_REVIEW`, `SCOUT_SEMGREP_CONFIG`); the standards node now dedupes and caps findings so SKILL.md synthesis fits context. Gave `~/.scout/.env` priority over a target repo's local `.env`, and removed the numeric score from the generated Markdown report. New modules: `backend/agents/_batch.py`, `backend/agents/dependency.py`, `backend/tools/code_skeleton.py`, `backend/tools/dep_audit.py`; new dependencies: tree-sitter and tree-sitter-language-pack.

## 2026-06-25 · seed

Initial knowledge-base seed from repo.

## 2026-06-25 · b62351f7fb3d3a5c6f04e6345b67d3117897f829

Introduced an Architecture & Design agent to provide KB-grounded, higher-level suggestions. Updated the agent graph to include this new agent. Added a KB retrieval mechanism for module-specific reviews. Enhanced the frontend to visualize and display KB-grounded findings. Added a new prompt for the Architecture & Design agent.

## 2026-06-25 · 889879046226c5272b57246307ab25464f93af3a

Introduced a new Test Coverage agent to identify missing tests and suggest actionable test cases. Enhanced the Architecture agent with web-research-enriched reviews. Updated the execution graph to include the Test Coverage agent. Added web research capabilities and integrated them across multiple agents. Updated the report generation process to include categorized findings and web research sources.

