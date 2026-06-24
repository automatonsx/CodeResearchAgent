"""Clone a public repo by URL so we can review it without a manual checkout.

Supports plain repo URLs and GitHub ``/tree/<branch>/<subdir>`` links (reviews just
that subfolder). Shallow-clones into a temp dir.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

# https://github.com/owner/repo            -> base, branch=None, subdir=""
# https://github.com/owner/repo/tree/main/pkg/sub -> base, branch="main", subdir="pkg/sub"
_GH_RE = re.compile(
    r"^(https?://github\.com/[^/\s]+/[^/\s]+?)(?:\.git)?"
    r"(?:/tree/([^/\s]+)(?:/(.*?))?)?/?$"
)


def parse_repo_url(url: str) -> tuple[str, str | None, str]:
    """Return (clone_url, branch_or_None, subdir). Falls back to the raw URL."""
    url = url.strip()
    m = _GH_RE.match(url)
    if m:
        base, branch, subdir = m.group(1), m.group(2), m.group(3) or ""
        return base + ".git", branch, subdir.strip("/")
    return url, None, ""


def clone_repo(url: str) -> dict:
    """Shallow-clone ``url`` into a temp dir.

    Returns {path, subdir, clone_url} on success, or {error} on failure.
    """
    clone_url, branch, subdir = parse_repo_url(url)
    dest = tempfile.mkdtemp(prefix="scout_clone_")
    try:
        from git import Repo

        kwargs = {"depth": 1}
        if branch:
            kwargs["branch"] = branch
        Repo.clone_from(clone_url, dest, **kwargs)
    except Exception as exc:  # network down, bad URL, private repo, no git, etc.
        return {"error": f"clone failed for {clone_url}: {exc}"}

    target = Path(dest) / subdir if subdir else Path(dest)
    if not target.exists():
        return {"error": f"subdir '{subdir}' not found in {clone_url}"}
    return {"path": str(target), "subdir": subdir, "clone_url": clone_url}
