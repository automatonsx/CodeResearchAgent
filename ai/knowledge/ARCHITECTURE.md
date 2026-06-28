# Architecture Knowledge Base — Scout

> Auto-maintained from merges to `main`. Source of truth: [`architecture.json`](architecture.json). Edits here are regenerated — change the JSON or let a merge update it.

_Last updated: 2026-06-28_

## Overview

Scout is a research-aware code review assistant designed to analyze repositories or pull request diffs and produce a prioritized, cited review report. Its architecture is centered around a multi-agent graph: context extraction, code-quality analysis, security checks, a dependency-vulnerability (CVE) audit, architecture & design review, test-coverage review, grounding findings in a best-practices corpus, and a Critic verification step. All best-practice citations come from a curated local `best_practices.json` corpus indexed in ChromaDB — there is no live web search (Tavily and all web-research paths have been removed). No raw source code is sent to the LLM: the architecture and test agents review a structural skeleton (imports + class/function signatures + line counts) extracted via stdlib `ast` (Python) or tree-sitter (other languages), while the tool agents send only tool findings plus tiny ±2-line snippets. All LLM-facing steps are batched with concurrent, self-healing split-on-failure for cost and scale. The report groups findings into categorized sections (security, dependencies, code, design, testing).

## Modules

### `.claude/skills`
Contains skill definitions for specific tasks like reviewing repositories or building the best-practices corpus.

**Key files:** `.claude/skills/build-corpus/SKILL.md`, `.claude/skills/review-repo/SKILL.md`

**Patterns / conventions:**
- Task-specific skill definitions

**Design decisions:**
- Appears to modularize task-specific logic for extensibility.

### `.github/workflows`
Defines CI workflows for linting, building, and running Scout reviews on pull requests.

**Key files:** `.github/workflows/kb-update.yml`, `.github/workflows/pr-checks.yml`

**Patterns / conventions:**
- GitHub Actions workflows

**Design decisions:**
- Includes optional AI-based review steps gated by secret availability.

### `backend`
Orchestrates the backend, including API endpoints, agent graph execution, and shared state management.

**Key files:** `backend/__init__.py`, `backend/graph.py`, `backend/knowledge/__init__.py`, `backend/knowledge/extractor.py`, `backend/knowledge/store.py`, `backend/knowledge/update.py`, `backend/llm.py`, `backend/main.py`, `backend/notify/__init__.py`, `backend/notify/github_review.py`, `backend/report_md.py`, `backend/state.py`

**Patterns / conventions:**
- FastAPI for API
- LangGraph for agent orchestration

**Design decisions:**
- Uses LangGraph to manage the multi-agent workflow.
- Appears to integrate Azure OpenAI for LLM-based tasks.

### `backend/agents`
Implements the core agents for context extraction, code quality, security, dependency-vulnerability audit, architecture/design review, test coverage, grounding, critique, and report generation.

**Key files:** `backend/agents/__init__.py`, `backend/agents/_batch.py`, `backend/agents/_generic.py`, `backend/agents/_snippet.py`, `backend/agents/_structure.py`, `backend/agents/code_quality.py`, `backend/agents/context.py`, `backend/agents/critic.py`, `backend/agents/dependency.py`, `backend/agents/grounding.py`, `backend/agents/report.py`, `backend/agents/security.py`, `backend/agents/architecture.py`, `backend/agents/test_review.py`

**Patterns / conventions:**
- Agent-based modular design
- Separation of concerns
- Shared batching with self-healing split-on-failure (`_batch.py`) for all LLM-facing agents

**Design decisions:**
- Added a Dependency Audit agent (`dependency.py`) — CVE scan of declared deps via OSV.dev (Python) + `npm audit` (JS), no LLM, cites OWASP A06.
- The Architecture & Test agents review a structural skeleton (imports + signatures + line counts), never raw file bodies, to keep token cost bounded.
- Citations are grounded only in the `best_practices.json` corpus — web research has been removed.
- Uses a graph-based LangGraph orchestration for agent communication.

### `backend/corpus`
Manages the best-practices corpus used for grounding findings.

**Key files:** `backend/corpus/__init__.py`, `backend/corpus/best_practices.json`, `backend/corpus/build_index.py`

**Patterns / conventions:**
- Corpus management and indexing

**Design decisions:**
- Uses ChromaDB for embedding and querying best-practice principles.

### `backend/graph.py`
Defines the execution graph for orchestrating agents in the multi-agent workflow.

**Key files:** `backend/graph.py`

**Patterns / conventions:**
- Graph-based orchestration

**Design decisions:**
- The review chain is: context → code_quality → security → dependency → architecture → test_review → grounding → critic → report (5 review agents).
- The new Dependency agent runs after Security and before Architecture.
- The Critic re-check loop is the agentic twist, but defaults to off (`MAX_ITERATIONS = 0`, `SCOUT_MAX_ITERATIONS`).
- The `standards` step is not in the graph — it runs after the graph in `run_standards()` to synthesize SKILL.md.

### `backend/knowledge`
Manages the project's knowledge base, including retrieval of relevant modules for reviews.

**Key files:** `backend/knowledge/__init__.py`, `backend/knowledge/extractor.py`, `backend/knowledge/store.py`, `backend/knowledge/update.py`, `backend/knowledge/retrieve.py`

**Patterns / conventions:**
- Knowledge base management

**Design decisions:**
- Added a retrieval mechanism (`retrieve.py`) to identify relevant KB modules for reviewed files.
- Supports direct module lookup for KB-grounded reviews.

### `backend/report_md.py`
Generates a final review report in Markdown format, including categorized findings.

**Key files:** `backend/report_md.py`

**Patterns / conventions:**
- Markdown rendering for reports

**Design decisions:**
- Categorized sections for findings: 🔒 Security, 📦 Dependencies, 💻 Code Quality, 🏗️ Architecture & Design, 🧪 Test Coverage.
- Enhanced finding blocks with severity badges and corpus citations.

### `backend/requirements.txt`
Specifies Python dependencies for the backend.

**Key files:** `backend/requirements.txt`

**Patterns / conventions:**
- Dependency management

**Design decisions:**
- Added `tree-sitter` and `tree-sitter-language-pack` for language-agnostic structural skeleton extraction.
- Dependency audit uses the OSV.dev HTTP API (stdlib `urllib`) + `npm audit` — `pip-audit` is not used.
- semgrep remains optional (not well-supported on native Windows); ruff's bandit (S) rules + AST cover security if it's absent.

### `backend/state.py`
Defines the shared state structure for the multi-agent workflow.

**Key files:** `backend/state.py`

**Patterns / conventions:**
- Shared state management

**Design decisions:**
- `ReviewState` is a `TypedDict(total=False)` so each node returns only the keys it changed.
- Loop guard `MAX_ITERATIONS` defaults to `0` (Critic re-check off by default; `SCOUT_MAX_ITERATIONS`).

### `backend/tools`
Provides ground-truth tool runners and utilities for static analysis, structural-skeleton extraction, dependency auditing, and diff parsing.

**Key files:** `backend/tools/__init__.py`, `backend/tools/ast_utils.py`, `backend/tools/code_skeleton.py`, `backend/tools/dep_audit.py`, `backend/tools/diff_utils.py`, `backend/tools/eslint_runner.py`, `backend/tools/generic_scan.py`, `backend/tools/git_utils.py`, `backend/tools/ruff_runner.py`, `backend/tools/semgrep_runner.py`

**Patterns / conventions:**
- Tool-specific wrappers and utilities ("the LLM proposes, these verify")

**Design decisions:**
- `code_skeleton.py` extracts a language-agnostic structural skeleton (imports + class/function names + LOC) via tree-sitter, with Python handled by stdlib `ast` (`ast_utils.python_skeleton`) — so raw file bodies never reach the LLM.
- `dep_audit.py` audits declared dependencies for CVEs: Python pins via the OSV.dev API, JS via `npm audit`.
- The `web_research.py` module has been removed — there is no web search.

### `data`
Holds sample repositories and diffs for testing and demonstration purposes.

**Key files:** `data/README.md`, `data/sample_repo/auth.py`, `data/sample_repo/utils.py`

**Patterns / conventions:**
- Sample data for testing

**Design decisions:**
- Provides controlled inputs for consistent testing.

### `deployment`
Contains deployment-related configurations and documentation.

**Key files:** `deployment/README.md`

**Patterns / conventions:**
- Deployment documentation

**Design decisions:**
- Appears to target Docker-based deployment.

### `evals`
Contains test data and evaluation scripts for validating the system's performance.

**Key files:** `evals/__init__.py`, `evals/expected.json`, `evals/README.md`, `evals/score.py`

**Patterns / conventions:**
- Planted-issue test set

**Design decisions:**
- Appears to focus on precision/recall evaluation.

### `frontend/src`
Implements the user interface for inputting repositories/diffs and viewing review reports.

**Key files:** `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/src/components/GlassBox.jsx`, `frontend/src/components/Report.jsx`, `frontend/src/main.jsx`, `frontend/src/styles.css`

**Patterns / conventions:**
- React (Vite) for frontend development

**Design decisions:**
- Updated the GlassBox component to include the Architecture & Design agent in the workflow visualization.
- Enhanced the Report component to display KB-grounded findings with a distinct visual indicator.

### `prompts`
Stores LLM prompt templates for various agents.

**Key files:** `prompts/code_quality.md`, `prompts/generic_review.md`, `prompts/knowledge_extractor.md`, `prompts/report.md`, `prompts/security.md`, `prompts/architecture.md`, `prompts/test_review.md`, `prompts/standards.md`

**Patterns / conventions:**
- Prompt engineering

**Design decisions:**
- The Architecture prompt grounds evidence in the KB and the `best_practices.json` corpus only — no web research.
- `test_review.md` drives the Test Coverage agent toward actionable test suggestions.
- `standards.md` synthesizes verified findings into repo-specific DO/DON'T rules for SKILL.md.
