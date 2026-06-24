"""Shared helper: read a verifiable code snippet around a file:line."""

from __future__ import annotations

from pathlib import Path


def read_snippet(file: str, line: int, context: int = 2) -> str:
    """Return the line plus +/- context lines (1-indexed). '' if unreadable."""
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    if not line or line < 1:
        return "\n".join(lines[:5])
    lo = max(0, line - 1 - context)
    hi = min(len(lines), line + context)
    out = []
    for i in range(lo, hi):
        marker = ">>" if i == line - 1 else "  "
        out.append(f"{marker}{i + 1}: {lines[i]}")
    return "\n".join(out)
