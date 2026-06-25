"""Knowledge-base store: structured JSON (truth) + rendered Markdown + changelog.

Files live in ``ai/knowledge/`` so they're versioned, diffable, and reviewable in
git — the vector index is derived from them, never the other way around.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
KB_DIR = _ROOT / "ai" / "knowledge"
ARCH_JSON = KB_DIR / "architecture.json"
ARCH_MD = KB_DIR / "ARCHITECTURE.md"
CHANGELOG = KB_DIR / "CHANGELOG.md"


def _empty_kb() -> dict:
    return {"project": "Scout", "updated": str(date.today()), "overview": "", "modules": {}}


def load_kb() -> dict:
    if ARCH_JSON.exists():
        try:
            return json.loads(ARCH_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return _empty_kb()


def merge_update(kb: dict, update: dict) -> dict:
    """Merge an extractor update into the KB.

    Affected modules are *replaced* (the LLM rewrote them with the change folded in),
    untouched modules are kept — so the KB reconciles instead of endlessly appending.
    """
    if update.get("overview"):
        kb["overview"] = update["overview"]
    modules = kb.setdefault("modules", {})
    for name, entry in (update.get("modules") or {}).items():
        entry["last_updated"] = str(date.today())
        modules[name] = entry
    kb["updated"] = str(date.today())
    return kb


def render_md(kb: dict) -> str:
    lines = [
        "# Architecture Knowledge Base — Scout",
        "",
        "> Auto-maintained from merges to `main`. Source of truth: "
        "[`architecture.json`](architecture.json). Edits here are regenerated — change the "
        "JSON or let a merge update it.",
        "",
        f"_Last updated: {kb.get('updated', '')}_",
        "",
        "## Overview",
        "",
        kb.get("overview", "_(none yet)_"),
        "",
        "## Modules",
        "",
    ]
    for name, m in sorted(kb.get("modules", {}).items()):
        lines.append(f"### `{name}`")
        if m.get("purpose"):
            lines.append(f"{m['purpose']}")
        if m.get("key_files"):
            lines.append("")
            lines.append("**Key files:** " + ", ".join(f"`{f}`" for f in m["key_files"]))
        if m.get("patterns"):
            lines.append("")
            lines.append("**Patterns / conventions:**")
            lines += [f"- {p}" for p in m["patterns"]]
        if m.get("decisions"):
            lines.append("")
            lines.append("**Design decisions:**")
            lines += [f"- {d}" for d in m["decisions"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_kb(kb: dict) -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    ARCH_JSON.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding="utf-8")
    ARCH_MD.write_text(render_md(kb), encoding="utf-8")


def append_changelog(summary: str, source: str = "") -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    header = "# Knowledge-Base Changelog\n\n" if not CHANGELOG.exists() else ""
    entry = f"## {date.today()}{f' · {source}' if source else ''}\n\n{summary.strip()}\n\n"
    with CHANGELOG.open("a", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.write(entry)
