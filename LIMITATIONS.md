# LIMITATIONS.md — Scout (Research-Aware Code Review)

Honest statement of what Scout does not do and where it can fail. (Stating these scores.)

## Out of scope (by design — see the roadmap in DESIGN.md §10)
- **Not all files are reviewed by default.** A file cap applies (`SCOUT_MAX_FILES`,
  default 80) to bound cost; larger repos are sampled. Raise it for deeper (more
  expensive) reviews.
- **Grounding depth varies by language.** Python (ruff + ast) and JS/TS/React/Vue
  (eslint) are deeply tool-grounded. Other languages (Go/Java/Ruby/PHP/C…) rely on
  semgrep — and the generic LLM reviewer is opt-in only (`SCOUT_GENERIC_REVIEW=1`), so by
  default code-quality coverage for those languages is whatever semgrep reports.
- **Curated mini-corpus** (~13 best-practice entries), not full academic literature.
- **Proposes fixes; does NOT auto-merge** or open PRs.
- No inline PR line comments; no "learns team preferences"; no PDF export.

## Known weaknesses
- **semgrep is poor on native Windows** (limited native support). Where semgrep is the
  only quality tool for a language (i.e. non-Python/JS), code-quality coverage there can be
  thin until semgrep runs in a Linux/Docker environment. Python security still comes from
  ruff's bandit (`S`) rules + AST.
- **eslint needs a one-time `npm install`.** Until its env in `backend/tools/eslint_env`
  is installed, JS/TS files get no eslint ground truth.
- **Dependency audit is pin/lockfile dependent.** Python is checked only for exact `==`
  pins in `requirements*.txt` (queried against OSV.dev); ranges/unpinned deps are skipped.
  npm audit needs a lockfile (`package-lock.json`/`npm-shrinkwrap.json`) present.
- **Architecture review reasons over skeletons.** The Architecture and Test-Review agents
  see structural skeletons (imports, class/function signatures, docstrings) — not raw file
  bodies — so they cannot see implementation logic inside function bodies.
- **LLM is still used for architecture/test reasoning.** Those agents can err; the risk is
  mitigated by the Critic, which drops findings it can't re-verify at `file:line`.
- **Logic bugs are best-effort.** Scout is strongest on security, style, complexity, dead
  code, dependency CVEs, and missing-docstring/test signals — not deep semantic correctness.
- **Diff mode reviews reconstructed new-file content**, so cross-file context and
  whole-program analysis are limited.

## How we reduce hallucination
1. **No codebase is sent to the LLM** — architecture/test reason over structural skeletons
   (ast/tree-sitter) + docstrings; code-quality/security send tool findings + tiny snippets.
2. No finding without a verifiable `file:line` (Critic drops the rest).
3. Tool facts (ruff/ast/semgrep/eslint/OSV/npm-audit) are ground truth; LLM opinion is
   separated and low-confidence.
4. Every finding cites a best-practice from the corpus.
5. The Critic loop removes false positives and re-checks before the report.

## What we'd fix with more time
See the 2-week roadmap in [DESIGN.md](DESIGN.md) §10.
