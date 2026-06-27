"""Render Scout standards as a Claude Code SKILL.md and save it to the target repo.

The generated file goes to:
    <target_repo>/.claude/skills/code-standards/SKILL.md

Claude Code automatically discovers skills under .claude/skills/ — so once this file
is committed to the repo, every developer using Claude Code in that repo gets the
project standards injected into their session without any manual setup.
"""

from __future__ import annotations

import datetime
from pathlib import Path


_SEV_ICON = {"critical": "🔴", "major": "🟠", "minor": "🟡", "suggestion": "🔵"}

_CATEGORY_LABELS = {
    "security":      ("🔐", "Security"),
    "code":          ("⚙️",  "Code Quality"),
    "design":        ("🏗️", "Architecture & Design"),
    "testing":       ("🧪", "Testing"),
    "observability": ("📊", "Observability"),
    "api":           ("🔌", "API Design"),
}


def _indent_code(text: str, prefix: str = "    ") -> str:
    """Indent every line of a code example so it renders correctly inside a fenced block."""
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _rule_block(rule: dict) -> str:
    sev = rule.get("severity", "minor")
    icon = _SEV_ICON.get(sev, "•")
    hook_tag = " _(hook-enforced)_" if rule.get("enforced_by_hook") else ""
    lines = [f"- {icon} **{rule.get('rule', '')}**{hook_tag}"]
    if rule.get("why"):
        lines.append(f"  - _Why:_ {rule['why']}")
    if rule.get("citation"):
        lines.append(f"  - _Ref:_ {rule['citation']}")
    if rule.get("bad_example"):
        code = _indent_code(rule["bad_example"])
        lines.append(f"  - _Never:_\n    ```\n{code}\n    ```")
    if rule.get("good_example"):
        code = _indent_code(rule["good_example"])
        lines.append(f"  - _Instead:_\n    ```\n{code}\n    ```")
    return "\n".join(lines)


def standards_to_skill(
    standards: dict,
    repo_name: str,
    source_path: str = "",
) -> str:
    """Return a SKILL.md string for the given standards dict."""
    date = datetime.date.today().isoformat()
    rules = standards.get("rules", {})
    tooling = standards.get("tooling", {})
    summary = standards.get("summary", "")

    never_rules  = rules.get("never", [])
    always_rules = rules.get("always", [])
    arch_rules   = rules.get("architecture", [])
    test_rules   = rules.get("testing", [])

    hook_enforced = [r for r in (never_rules + always_rules) if r.get("enforced_by_hook")]

    # Build trigger tags for the description: list rule subjects so Claude Code picks up
    # the skill when the developer asks about or writes any of the flagged patterns.
    never_subjects = ", ".join(
        r.get("rule", "")[:60] for r in never_rules[:4] if r.get("rule")
    )
    trigger_hint = (
        f"Trigger when the developer writes or asks about: {never_subjects}. "
        if never_subjects else ""
    )

    lines: list[str] = [
        "---",
        f"name: {repo_name}-standards",
        (
            f"description: Scout-verified coding standards for {repo_name} — "
            "rules extracted from actual findings in this codebase, not generic advice. "
            f"{trigger_hint}"
            "Apply every rule proactively while writing or reviewing code in this repo. "
            "Push back immediately when you see a violation — before the file is saved."
        ),
        "---",
        "",
        f"# {repo_name} — Coding Standards",
        f"> Scout-verified · {date} · rules from actual findings in this codebase",
        f"> Source: `{source_path or repo_name}`",
        "> Regenerate: `python -m backend.graph <path> repo --standards`",
        "",
    ]

    if summary:
        lines += [f"**Profile:** {summary}", ""]

    lines += ["---", ""]

    # ── NEVER DO ─────────────────────────────────────────────────────────────
    if never_rules:
        lines += [
            "## 🚫 Never Do",
            "",
            "These rules are non-negotiable and verified in this codebase. "
            "The pre-commit hook enforces hook-marked rules automatically.",
            "",
        ]
        for r in never_rules:
            lines.append(_rule_block(r))
            lines.append("")

    # ── ALWAYS DO ────────────────────────────────────────────────────────────
    if always_rules:
        lines += ["## ✅ Always Do", ""]
        for r in always_rules:
            lines.append(_rule_block(r))
            lines.append("")

    # ── ARCHITECTURE ─────────────────────────────────────────────────────────
    if arch_rules:
        lines += ["## 🏗️ Architecture & Design", ""]
        for r in arch_rules:
            lines.append(_rule_block(r))
            lines.append("")

    # ── TESTING ──────────────────────────────────────────────────────────────
    if test_rules:
        lines += ["## 🧪 Testing Requirements", ""]
        for r in test_rules:
            lines.append(_rule_block(r))
            lines.append("")

    # ── TOOLING ──────────────────────────────────────────────────────────────
    if tooling.get("linter") or tooling.get("key_rules_active"):
        lines += ["## 🔧 Tooling", ""]
        if tooling.get("linter"):
            lines.append(f"- **Linter:** `{tooling['linter']}`")
        if tooling.get("key_rules_active"):
            codes = ", ".join(f"`{c}`" for c in tooling["key_rules_active"])
            lines.append(f"- **Enforced rules:** {codes}")
        lines.append("")

    # ── PRE-COMMIT GUARDIAN ───────────────────────────────────────────────────
    lines += [
        "## 🔒 Pre-commit Guardian",
        "",
        "The Scout pre-commit hook runs on every `git commit` — no LLM, under 1 second.",
        "",
        "**Rules checked on staged files:**",
    ]
    for r in (hook_enforced or [
        {"severity": "critical", "rule": "No hardcoded secrets or API keys"},
        {"severity": "critical", "rule": "No SQL injection via string formatting (S608)"},
        {"severity": "critical", "rule": "No shell=True in subprocess calls (S602)"},
        {"severity": "critical", "rule": "No eval() on user input (S307 / SCAN-EVAL)"},
    ]):
        icon = _SEV_ICON.get(r.get("severity", "minor"), "•")
        lines.append(f"- {icon} {r.get('rule', '')}")

    lines += [
        "",
        "Critical violations **block the commit**. Major issues warn but allow it.",
        "Bypass sparingly: `git commit --no-verify`",
        "",
        "**Install hooks on a fresh checkout:**",
        "```bash",
        "python scripts/install_hooks.py",
        "```",
    ]

    # ── BEST PRACTICES REFERENCE ──────────────────────────────────────────────
    corpus_practices = standards.get("corpus_practices", [])
    if corpus_practices:
        by_cat: dict[str, list[dict]] = {}
        for p in corpus_practices:
            by_cat.setdefault(p.get("category", "code"), []).append(p)

        lines += [
            "",
            "---",
            "",
            "## 📚 Best Practices for This Stack",
            "",
            "All applicable practices from Scout's curated knowledge base, "
            "matched to this repo's language and frameworks.",
            "",
        ]
        for cat in ["security", "code", "design", "testing", "observability", "api"]:
            cat_practices = by_cat.get(cat, [])
            if not cat_practices:
                continue
            emoji, label = _CATEGORY_LABELS.get(cat, ("•", cat.title()))
            lines += [f"### {emoji} {label}", ""]
            for p in cat_practices:
                lines.append(f"- **{p['title']}**")
                if p.get("principle"):
                    lines.append(f"  {p['principle']}")
                if p.get("source"):
                    lines.append(f"  _Source: {p['source']}_")
                lines.append("")

    return "\n".join(lines)


def save_skill(
    standards: dict,
    repo_name: str,
    output_dir: str,
    source_path: str = "",
) -> str:
    """Write SKILL.md to <output_dir>/.claude/skills/code-standards/SKILL.md.

    Returns the absolute path of the written file.
    """
    skill_dir = Path(output_dir) / ".claude" / "skills" / "code-standards"
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        standards_to_skill(standards, repo_name, source_path),
        encoding="utf-8",
    )
    return str(path)
