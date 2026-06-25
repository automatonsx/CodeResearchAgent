"""Rule-code → best-practice mapping, built at import time from best_practices.json tags.

Every tag that looks like a linter rule code (uppercase letters/digits, or SCAN-*/AST-*
prefixes) is treated as a key. Calling lookup("S608") instantly returns the matching
practice dict without touching ChromaDB.

This is used by _structure.py to attach citations to tool-grounded findings
deterministically — no vector search needed when the rule code is an exact match.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _is_rule_code(tag: str) -> bool:
    if tag.startswith(("SCAN-", "AST-")):
        return True
    # Ruff/flake8 codes: one or two uppercase letters followed by digits (E722, S608, B006, F401)
    if len(tag) >= 2 and tag[0].isupper() and any(c.isdigit() for c in tag):
        return True
    return False


@lru_cache(maxsize=1)
def _build() -> dict[str, dict]:
    path = Path(__file__).resolve().parent / "best_practices.json"
    practices = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, dict] = {}
    for p in practices:
        for tag in p.get("tags", []):
            if _is_rule_code(tag):
                mapping[tag] = p
    return mapping


def lookup(rule_code: str) -> dict | None:
    """Return the best practice for a linter rule code, or None if not mapped."""
    return _build().get(rule_code)


def citation_for(rule_code: str) -> str | None:
    """Return a formatted citation string for a rule code, or None."""
    p = lookup(rule_code)
    if p:
        return f"{p['title']} — {p['source']}"
    return None
