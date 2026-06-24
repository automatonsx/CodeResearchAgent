"""ruff runner — ground-truth Python linting (quality + bandit security rules).

ruff bundles flake8-bandit (the ``S`` rules), so we get security ground-truth even
without semgrep (which has poor native-Windows support).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# Rule families we surface. S = bandit security; C90 = complexity; B = bugbear.
_SELECT = "E,F,W,C90,S,B"

# Map ruff rule prefixes to our finding "type".
_TYPE_BY_PREFIX = {
    "S": "security",
    "C90": "code",
    "B": "code",
    "E": "style",
    "W": "style",
    "F": "code",
}


def _ruff_exe() -> str | None:
    """Locate the ruff executable (venv Scripts dir, then PATH)."""
    local = Path(sys.executable).parent / ("ruff.exe" if sys.platform == "win32" else "ruff")
    if local.exists():
        return str(local)
    return shutil.which("ruff")


def _classify(code: str) -> str:
    for prefix, kind in _TYPE_BY_PREFIX.items():
        if code.startswith(prefix):
            return kind
    return "code"


def run_ruff(target, select: str = _SELECT) -> list[dict]:
    """Run ruff over a path or an explicit list of files; return tool findings.

    Each: {tool, code, type, file, line, message}. Returns [] if ruff is missing
    or there's no Python to check.
    """
    exe = _ruff_exe()
    if not exe:
        return []
    paths = [str(p) for p in target] if isinstance(target, (list, tuple)) else [str(target)]
    paths = [p for p in paths if Path(p).exists()]
    if not paths:
        return []
    try:
        proc = subprocess.run(
            [exe, "check", "--output-format", "json", "--select", select, "--quiet", *paths],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        return []

    out = proc.stdout.strip()
    if not out:
        return []
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return []

    findings = []
    for item in raw:
        code = item.get("code") or ""
        loc = item.get("location") or {}
        findings.append(
            {
                "tool": "ruff",
                "code": code,
                "type": _classify(code),
                "file": item.get("filename", ""),
                "line": loc.get("row", 0),
                "message": item.get("message", ""),
            }
        )
    return findings
