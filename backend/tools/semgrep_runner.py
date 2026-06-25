"""semgrep runner — optional security ground-truth.

semgrep has poor native-Windows support, so this is best-effort: if semgrep isn't
installed/available, ``run_semgrep`` returns [] and the Security agent falls back to
ruff's bandit (S) rules + AST checks.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def semgrep_available() -> bool:
    return shutil.which("semgrep") is not None


def run_semgrep(path: str, config: str = "p/python") -> list[dict]:
    """Run semgrep if available; return normalized findings, else []."""
    if not semgrep_available() or not Path(path).exists():
        return []
    try:
        proc = subprocess.run(
            ["semgrep", "--config", config, "--json", "--quiet", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        raw = json.loads(proc.stdout or "{}")
    except Exception:
        return []

    findings = []
    for r in raw.get("results", []):
        findings.append(
            {
                "tool": "semgrep",
                "code": r.get("check_id", ""),
                "type": "security",
                "file": r.get("path", path),
                "line": (r.get("start") or {}).get("line", 0),
                "message": (r.get("extra") or {}).get("message", ""),
            }
        )
    return findings
