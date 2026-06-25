# Architecture Knowledge Base — Scout

> Auto-maintained from merges to `main`. Source of truth: [`architecture.json`](architecture.json). Edits here are regenerated — change the JSON or let a merge update it.

_Last updated: 2026-06-25_

## Overview

Scout is a research-aware code review assistant designed to analyze repositories or pull request diffs and produce a prioritized, cited review report. Its architecture is centered around a multi-agent graph that includes context extraction, code-quality analysis, security checks, grounding findings in a best-practices corpus, and a Critic loop for verification and re-checking. The Architecture & Design agent has been enhanced to include web-research-enriched reviews, expanding its applicability to external repositories. A new Test Coverage agent has been introduced to identify missing tests and suggest actionable test cases. The system now integrates web research across multiple agents, enabling recommendations grounded in both the project's knowledge base and external resources. The report generation process has been updated to include categorized findings and web research sources.

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
Implements the core agents for context extraction, code quality, security, grounding, critique, architecture/design review, test coverage, and report generation.

**Key files:** `backend/agents/__init__.py`, `backend/agents/_generic.py`, `backend/agents/_snippet.py`, `backend/agents/_structure.py`, `backend/agents/code_quality.py`, `backend/agents/context.py`, `backend/agents/critic.py`, `backend/agents/grounding.py`, `backend/agents/report.py`, `backend/agents/security.py`, `backend/agents/architecture.py`, `backend/agents/test_review.py`

**Patterns / conventions:**
- Agent-based modular design
- Separation of concerns

**Design decisions:**
- Introduced a new Test Coverage agent to identify missing tests and suggest actionable test cases.
- Enhanced the Architecture & Design agent to include web-research-enriched reviews, making it applicable to external repositories.
- Appears to use a graph-based orchestration for agent communication.

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
- Added the Test Coverage agent to the graph, positioned after the Architecture agent and before the Grounding agent.
- Updated the Architecture agent's description to reflect its web-research-enriched capabilities.

### `backend/knowledge`
Manages the project's knowledge base, including retrieval of relevant modules for reviews.

**Key files:** `backend/knowledge/__init__.py`, `backend/knowledge/extractor.py`, `backend/knowledge/store.py`, `backend/knowledge/update.py`, `backend/knowledge/retrieve.py`

**Patterns / conventions:**
- Knowledge base management

**Design decisions:**
- Added a retrieval mechanism (`retrieve.py`) to identify relevant KB modules for reviewed files.
- Supports direct module lookup for KB-grounded reviews.

### `backend/report_md.py`
Generates a final review report in Markdown format, including categorized findings and web research sources.

**Key files:** `backend/report_md.py`

**Patterns / conventions:**
- Markdown rendering for reports

**Design decisions:**
- Added categorized sections for findings (e.g., security, design, testing).
- Included a dedicated section for web research sources in the final report.
- Enhanced finding blocks with severity badges and detailed evidence.

### `backend/requirements.txt`
Specifies Python dependencies for the backend.

**Key files:** `backend/requirements.txt`

**Patterns / conventions:**
- Dependency management

**Design decisions:**
- Added `tavily-python` as an optional dependency for high-quality web research.
- Documented fallback mechanisms for web research when Tavily is unavailable.

### `backend/state.py`
Defines the shared state structure for the multi-agent workflow.

**Key files:** `backend/state.py`

**Patterns / conventions:**
- Shared state management

**Design decisions:**
- Added a `web_research` field to the state to store web research results for reuse across agents.

### `backend/tools`
Provides utility functions and tool integrations for static analysis, diff parsing, and web research.

**Key files:** `backend/tools/__init__.py`, `backend/tools/ast_utils.py`, `backend/tools/diff_utils.py`, `backend/tools/eslint_runner.py`, `backend/tools/generic_scan.py`, `backend/tools/git_utils.py`, `backend/tools/ruff_runner.py`, `backend/tools/semgrep_runner.py`, `backend/tools/web_research.py`

**Patterns / conventions:**
- Tool-specific wrappers and utilities

**Design decisions:**
- Introduced a new `web_research.py` module to fetch web and research resources for agents.
- Supports integration with Tavily, Semantic Scholar, and ArXiv for web research.
- Appears to detect frameworks and generate targeted queries for web research.

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

**Key files:** `prompts/code_quality.md`, `prompts/generic_review.md`, `prompts/knowledge_extractor.md`, `prompts/report.md`, `prompts/security.md`, `prompts/architecture.md`, `prompts/test_review.md`

**Patterns / conventions:**
- Prompt engineering

**Design decisions:**
- Updated the Architecture prompt to include web research as an evidence base alongside the KB.
- Added a new prompt template (`test_review.md`) tailored for the Test Coverage agent, emphasizing actionable test suggestions.
