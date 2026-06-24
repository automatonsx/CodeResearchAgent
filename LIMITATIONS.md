# LIMITATIONS.md — Scout (Research-Aware Code Review)

Honest statement of what Scout does not do and where it can fail. (Stating these scores.)

## Out of scope (by design — see the roadmap in DESIGN.md §10)
- **Grounding depth varies by language.** Python (ruff + ast) and JS/TS (eslint) are
  deeply tool-grounded. Other languages (Go/Java/Ruby/PHP/C…) are reviewed by a
  language-agnostic secret/pattern scanner (ground truth) **plus** an LLM reviewer whose
  findings the Critic verifies by re-checking the quoted code. Per-language linters for
  those (gopls, etc.) are roadmap. eslint is optional — without its env, JS falls back to
  the LLM reviewer.
- **Small/medium repos.** Large repos need chunking (a soft ~40-file cap applies now).
- **Curated mini-corpus** (~13 best-practice entries), not full academic literature.
- **Proposes fixes; does NOT auto-merge** or open PRs.
- No GitHub Action / inline PR comments; no "learns team preferences"; no PDF export.

## Known weaknesses
- **semgrep is optional on Windows** (poor native support). Security ground truth then
  comes from ruff's bandit (`S`) rules + AST — strong, but a narrower ruleset than semgrep.
- **Logic bugs are best-effort.** Scout is strongest on security, style, complexity, dead
  code, and missing-docstring/test signals — not deep semantic correctness.
- **Non-Python findings lean on LLM judgment.** They must quote code that the Critic
  re-verifies at `file:line`, but the *severity/relevance* call is the model's, not a
  linter's — so precision is lower than on Python.
- **LLM-judgment findings** (no tool evidence) can still slip through if they happen to map
  to a valid `file:line`; they're marked low-confidence and re-checked, not guaranteed gone.
- **Scoring is heuristic** (severity penalties), not calibrated to a real defect model.
- **Diff mode reviews reconstructed new-file content**, so cross-file context and
  whole-program analysis are limited.

## How we reduce hallucination
1. No finding without a verifiable `file:line` (Critic drops the rest).
2. Tool facts (ruff/ast/semgrep) are ground truth; LLM opinion is separated and low-confidence.
3. Every finding cites a best-practice from the corpus.
4. The Critic loop removes false positives and re-checks before the report.

## What we'd fix with more time
See the 2-week roadmap in [DESIGN.md](DESIGN.md) §10.
