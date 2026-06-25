"""Install Scout git hooks into a target repository.

Works whether Scout was pip-installed (backend is on sys.path) or run from source.
Called by backend/cli.py and backend/mcp_server.py — no dependency on scripts/.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

# The hook script uses a try/except import so it works both when Scout is
# pip-installed (backend already on sys.path) and when run from a source checkout
# (backend not on sys.path — we walk up from .git to find the Scout root).
_PRE_COMMIT_SCRIPT = """\
#!/usr/bin/env python3
# Scout pre-commit hook — installed by scout-review
# Do not edit manually; re-run: scout install-hooks
import sys
try:
    from backend.hooks.pre_commit import main
except ImportError:
    import pathlib
    # Source checkout: .git/hooks/../../ is the repo root, not Scout's root.
    # Scout root is stored at install time in the line below (replaced on write).
    _scout = pathlib.Path(__SCOUT_ROOT__)
    if str(_scout) not in sys.path:
        sys.path.insert(0, str(_scout))
    from backend.hooks.pre_commit import main
sys.exit(main())
"""

_PRE_PUSH_SCRIPT = """\
#!/usr/bin/env python3
# Scout pre-push hook — installed by scout-review
import sys, subprocess, pathlib
try:
    from backend.tools.ruff_runner import run_ruff
    from backend.tools.generic_scan import generic_scan
except ImportError:
    _scout = pathlib.Path(__SCOUT_ROOT__)
    if str(_scout) not in sys.path:
        sys.path.insert(0, str(_scout))
    from backend.tools.ruff_runner import run_ruff
    from backend.tools.generic_scan import generic_scan

data = sys.stdin.read().strip()
if not data:
    sys.exit(0)
parts = data.split()
if len(parts) < 4:
    sys.exit(0)
local_sha, remote_sha = parts[1], parts[3]
ZERO = "0" * 40
range_arg = f"{remote_sha}..{local_sha}" if remote_sha != ZERO else local_sha
result = subprocess.run(
    ["git", "diff", "--name-only", "--diff-filter=ACMR", range_arg],
    capture_output=True, text=True,
)
files = [str(pathlib.Path(f).resolve()) for f in result.stdout.splitlines() if f.strip()]
if not files:
    sys.exit(0)
py_files = [f for f in files if f.endswith(".py")]
issues = (run_ruff(py_files, select="S") if py_files else []) + generic_scan(files)
critical = [i for i in issues if i.get("severity") == "critical"]
if critical:
    print("\\033[31mScout pre-push: CRITICAL issues — push blocked\\033[0m")
    for i in critical:
        p = pathlib.Path(i.get("file", "?"))
        print(f"  {p.name}:{i.get('line','?')}  [{i.get('code','?')}]  {i.get('message','')}")
    sys.exit(1)
sys.exit(0)
"""


def _scout_root() -> str:
    """Return the Scout package root — works for both pip installs and source runs."""
    # backend/hooks/installer.py → backend/hooks/ → backend/ → scout root
    return str(Path(__file__).resolve().parent.parent.parent)


def _write_hook(hooks_dir: Path, name: str, content: str) -> Path:
    path = hooks_dir / name
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if "Scout" in existing:
            pass  # overwrite our own hook
        else:
            # Chain after any existing non-Scout hook
            content = existing.rstrip() + "\n\n# === Scout (appended) ===\n" + content
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def install(repo_path: str, pre_push: bool = False) -> list[str]:
    """Write Scout hooks into *repo_path*/.git/hooks/. Returns installed paths."""
    root = Path(repo_path).resolve()

    # Resolve the actual .git directory (handles worktrees and nested repos).
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            capture_output=True, text=True, check=True,
        )
        git_dir = Path(result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
    except subprocess.CalledProcessError:
        return []

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    scout = _scout_root()
    pre_commit_content = _PRE_COMMIT_SCRIPT.replace("__SCOUT_ROOT__", repr(scout))
    pre_push_content   = _PRE_PUSH_SCRIPT.replace("__SCOUT_ROOT__", repr(scout))

    installed: list[str] = []
    installed.append(str(_write_hook(hooks_dir, "pre-commit", pre_commit_content)))
    if pre_push:
        installed.append(str(_write_hook(hooks_dir, "pre-push", pre_push_content)))

    return installed


def uninstall(repo_path: str) -> list[str]:
    """Remove Scout hooks from *repo_path*. Returns removed paths."""
    root = Path(repo_path).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            capture_output=True, text=True, check=True,
        )
        git_dir = Path(result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
    except subprocess.CalledProcessError:
        return []

    removed = []
    for name in ("pre-commit", "pre-push"):
        path = git_dir / "hooks" / name
        if path.exists() and "Scout" in path.read_text(encoding="utf-8"):
            path.unlink()
            removed.append(str(path))
    return removed
