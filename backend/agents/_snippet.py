"""Shared helper: read a verifiable code snippet around a file:line."""

from __future__ import annotations

from pathlib import Path

# Cap on a single line's length when fed to the LLM. Pathologically long lines
# (minified JS, base64 blobs, big data literals) can push gpt-4o into a
# degenerate repetition loop that fills the entire output-token budget and fails
# to parse. Trimming them keeps snippets verifiable without that risk.
_MAX_LINE_CHARS = 300


def _clip(text: str) -> str:
    if len(text) > _MAX_LINE_CHARS:
        return text[:_MAX_LINE_CHARS] + " …[line truncated]"
    return text


def read_snippet(file: str, line: int, context: int = 2) -> str:
    """Return the line plus +/- context lines (1-indexed). '' if unreadable."""
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    if not line or line < 1:
        return "\n".join(_clip(ln) for ln in lines[:5])
    lo = max(0, line - 1 - context)
    hi = min(len(lines), line + context)
    out = []
    for i in range(lo, hi):
        marker = ">>" if i == line - 1 else "  "
        out.append(f"{marker}{i + 1}: {_clip(lines[i])}")
    return "\n".join(out)
