"""Unified-diff parsing for PR-diff mode.

Extracts changed files and the set of added/modified line numbers (new-file side)
so the review can focus on changed code and write the diff to a temp tree for the
tools to analyze.
"""

from __future__ import annotations

import re
import urllib.request

_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_PR_URL_RE = re.compile(r"^(https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+)")
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

    # Reconstruct the new-file side, line-aligned to real new-file line numbers.
    # Lines from the hunk are placed at their true position; gaps are padded with
    # blanks so a tool reporting "line N" maps to the actual new-file line N
    # (not a sequential index). Changed-line filtering then works on real numbers.
    for path, info in files.items():
        pairs = info["lines"]
        if pairs:
            max_ln = max(n for n, _ in pairs)
            buf = [""] * max_ln
            for n, text in pairs:
                if 1 <= n <= max_ln:
                    buf[n - 1] = text
            info["content"] = "\n".join(buf)
        else:
            info["content"] = ""
        del info["lines"]
    return {"files": files}


def fetch_pr_diff(url: str) -> dict:
    """Fetch a GitHub PR's unified diff from its URL.

    Accepts a PR page URL (…/pull/N) or a …/pull/N.diff URL. Returns {diff} on
    success or {error} on failure (private repo, network down, bad URL).
    """
    m = _PR_URL_RE.match(url.strip())
    if not m:
        return {"error": f"Not a GitHub PR URL (expected …/pull/<number>): {url}"}
    diff_url = m.group(1) + ".diff"
    try:
        req = urllib.request.Request(diff_url, headers={"User-Agent": "scout-review"})
        with urllib.request.urlopen(req, timeout=20) as resp:  # follows redirects
            return {"diff": resp.read().decode("utf-8", errors="ignore")}
    except Exception as exc:  # noqa: BLE001 — surface any fetch failure to the caller
        return {"error": f"Failed to fetch {diff_url}: {exc}"}
