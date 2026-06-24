---
name: review-repo
description: Run Scout's research-aware code-review graph on a target repo folder or PR diff, then save the prioritized, cited report to reports/. Use when the user wants a repo or diff reviewed for security/quality issues with tool evidence and best-practice citations.
---

# review-repo

Run the Scout review graph (Context → Code-Quality → Security → Grounding → Critic ⇄ →
Report) on a repo folder or a PR diff, then save the report.

## Inputs
- **source** (required) — a folder path (repo), a **public GitHub URL** (github; a
  `…/tree/<branch>/<subdir>` link reviews just that subfolder), OR unified-diff text (PR).
- **input_type** (optional, default `repo`) — `repo` | `github` | `pr_diff`.

## Steps
1. Ensure backend deps are installed and `.env` has `AZURE_OPENAI_*`. See `.env.example`.
   (semgrep is optional; ruff's bandit `S` rules + AST are the fallback ground truth.)
2. Run the review graph from the repo root:
   ```bash
   # repo mode
   python -m backend.graph "data/sample_repo" repo
   # github mode (clones a public repo / subfolder)
   python -m backend.graph "https://github.com/PyCQA/bandit/tree/main/examples" github
   # PR-diff mode (pass the diff text/path as the first arg)
   python -m backend.graph "$(cat data/sample.diff)" pr_diff
   ```
   Append `--save` to also write a Markdown report to `reports/<slug>.md`:
   ```bash
   python -m backend.graph "data/sample_repo" repo --save
   ```
   (Or POST to a running API: `POST /review {"source": "...", "input_type": "...", "save": true}`
   — the response includes `saved_to`.)
3. The Markdown report contains: **Verdict + Score · Summary · Findings (severity,
   `file:line`, fix, tool evidence, citation) · Coverage stats**.
4. Print the saved path and a one-line verdict + score.

## Guarantees
- No finding without a verifiable `file:line` (the Critic drops the rest).
- Every finding carries **tool evidence** (ruff/semgrep/ast) and a **best-practice
  citation** from the curated corpus.
- The report ends with a verdict (`approve` / `request_changes` / `discuss`) and a score.
