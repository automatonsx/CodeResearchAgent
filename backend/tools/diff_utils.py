"""Unified-diff parsing for PR-diff mode.

Extracts changed files and the set of added/modified line numbers (new-file side)
so the review can focus on changed code and write the diff to a temp tree for the
tools to analyze.
"""

from __future__ import annotations

import re

_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff(diff_text: str) -> dict:
    """Parse a unified diff.

    Returns {files: {path: {added_lines: set[int], content: str}}}, where ``content``
    is the reconstructed new-file side (added + context lines) so tools can lint it.
    """
    files: dict[str, dict] = {}
    current: dict | None = None
    new_lineno = 0

    for line in diff_text.splitlines():
        m = _FILE_RE.match(line)
        if m:
            path = m.group(1).strip()
            current = {"added_lines": set(), "lines": []}
            files[path] = current
            continue
        if current is None:
            continue
        h = _HUNK_RE.match(line)
        if h:
            new_lineno = int(h.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current["added_lines"].add(new_lineno)
            current["lines"].append((new_lineno, line[1:]))
            new_lineno += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue  # removed line — not on the new side
        elif line.startswith(" "):
            current["lines"].append((new_lineno, line[1:]))
            new_lineno += 1

    # Reconstruct new-file content per file.
    for path, info in files.items():
        ordered = sorted(info["lines"], key=lambda t: t[0])
        info["content"] = "\n".join(text for _, text in ordered)
        del info["lines"]
    return {"files": files}
