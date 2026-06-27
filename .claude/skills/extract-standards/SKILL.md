---
name: extract-standards
description: Run Scout in standards mode on any repo — generates a repo-specific SKILL.md with DO/DON'T rules derived from actual findings, and installs a pre-commit hook that blocks critical violations at commit time. Use when onboarding a new repo to Scout.
---

# extract-standards

Analyze any codebase — local path or GitHub URL — and generate two artifacts:

1. A **SKILL.md** injected into every Claude Code session in that repo — so the LLM automatically follows the project's verified coding standards, complete with KB citations, when writing or editing code.
2. A **pre-commit hook** that runs fast tool checks (ruff + secret scanner) on every `git commit` and blocks critical violations without an LLM call.

## Quick Start — one command does everything

```bash
# GitHub URL (clones, analyzes, writes SKILL.md, installs hooks)
python scripts/onboard_repo.py https://github.com/owner/repo

# Local repo
python scripts/onboard_repo.py /path/to/repo

# With pre-push hook + save the full review report
python scripts/onboard_repo.py https://github.com/owner/repo --pre-push --save-report
```

`onboard_repo.py` runs all Scout agents in order, then writes the SKILL.md and installs the hooks. That's the only command most users need.

---

## What happens inside (all agents, in order)

```
GitHub URL / local path
        │
        ▼
  1. context_node      — detect language, frameworks, entry points
        │
        ▼
  2. code_quality_node — AST analysis: complexity, dead code, style
        │
        ▼
  3. security_node     — ruff (S/B rules), secret scan, shell injection
        │
        ▼
  4. architecture_node — design patterns, layering, SOLID via KB
        │
        ▼
  5. test_review_node  — coverage gaps, missing assertions
        │
        ▼
  6. grounding_node    — attach best-practice citations (ChromaDB RAG)
        │
        ▼
  7. critic_node       — verify findings, drop low-confidence ones
        │
        ▼
  8. report_node       — score, grade (A–D), structured findings
        │
        ▼
  9. standards_node    — synthesize DO/DON'T rules with citations
        │
        ▼
 10. save_skill()      → <repo>/.claude/skills/code-standards/SKILL.md
 11. install_hooks.py  → <repo>/.git/hooks/pre-commit  (+ pre-push)
```

---

## Step-by-step (if you need granular control)

### 1. Generate SKILL.md only

```bash
# Local repo
python -m backend.graph <repo-path> repo --standards --save

# GitHub URL
python -m backend.graph <github-url> github --standards --save
```

Output: `<repo>/.claude/skills/code-standards/SKILL.md`

### 2. Install hooks separately

```bash
# Pre-commit only (default)
python scripts/install_hooks.py <repo-path>

# Pre-commit + pre-push
python scripts/install_hooks.py <repo-path> --pre-push

# Remove hooks
python scripts/install_hooks.py <repo-path> --uninstall
```

The pre-commit hook:
- Runs in **<1 second** — no LLM call, deterministic tool checks only
- Blocks commits with **CRITICAL** security issues (hardcoded secrets, SQL injection, eval)
- **Warns** (non-blocking) on MAJOR issues
- Bypass with `git commit --no-verify` (use sparingly)

### 3. Commit the SKILL.md into the target repo

```bash
cd <repo>
git add .claude/skills/code-standards/SKILL.md
git commit -m "chore: add Scout coding standards skill"
```

Once committed, every developer who opens Claude Code in that repo gets the standards
injected automatically — no per-developer setup required.

### 4. Keep standards fresh

Re-run after major changes. The skill file is a snapshot of the last analysis run.

```bash
python scripts/onboard_repo.py <repo-path>          # refresh everything
# or just the standards part:
python -m backend.graph <repo-path> repo --standards
```

---

## What the generated SKILL.md contains

Derived entirely from verified findings in the actual codebase — not generic advice.
Each rule includes the KB citation that grounds it.

| Section | Source |
|---------|--------|
| 🚫 Never Do | CRITICAL/MAJOR security findings (tool-grounded) |
| ✅ Always Do | Correct patterns from those findings, with citations |
| 🏗️ Architecture | Design findings from KB + web research |
| 🧪 Testing | Missing test coverage findings |
| 🔒 Pre-commit Guardian | Hook-enforced rules with tool codes |

## Best-practices knowledge base

All citations in generated SKILL.md files come from the curated KB:

- **Source file:** `backend/corpus/best_practices.json` (53 entries)
- **Human-readable reference:** `docs/best_practices.md` (full citations + examples)
- **Vector store:** ChromaDB index built from the JSON; queried by the grounding agent

To add a new practice: update both JSON and MD, then rebuild:
```bash
python backend/corpus/build_index.py
```

## Example generated rule (with citation)

```markdown
## 🚫 Never Do

- 🔴 **Never use string formatting to build SQL queries** _(hook-enforced)_
  - _Why:_ SQL injection — any username value can exfiltrate or destroy the database
  - _Ref:_ Use parameterized queries — OWASP Top 10 A03:2021 — Injection
  - _Never:_
    ```
    cur.execute("SELECT * FROM users WHERE name = '%s'" % username)
    ```
  - _Instead:_
    ```
    cur.execute('SELECT * FROM users WHERE name = ?', (username,))
    ```
```
