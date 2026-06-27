"""semgrep runner — multi-language ground-truth (security + code quality).

semgrep covers many languages (JS/TS, Java, Go, Ruby, PHP, C#, …) with one tool and
no per-language toolchain, so it's the cheap, findings-based alternative to sending
raw file bodies to the LLM (generic_review).

Best-effort: semgrep has poor native-Windows support, so if it isn't installed,
``run_semgrep`` returns [] and callers fall back (ruff/AST for security; generic_review
for code quality when explicitly enabled).
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


def run_semgrep(target, config: str = "p/python") -> list[dict]:
    """Run semgrep on a path or a list of files; return normalized findings, else [].

    Args:
        target: a directory/file path (str) OR a list of file paths.
        config: semgrep ruleset — e.g. "p/python", "p/javascript", or "auto"
                (auto-detects language; needs network/login for the registry).

    Findings are type-neutral (no "type"/"category" set) — the calling agent tags
    them as security or code so the same runner serves both.
    """
    if not semgrep_available():
        return []

    if isinstance(target, (list, tuple)):
        paths = [str(p) for p in target if Path(p).exists()]
    else:
        paths = [target] if target and Path(target).exists() else []
    if not paths:
        return []

    try:
        proc = subprocess.run(
            ["semgrep", "--config", config, "--json", "--quiet", *paths],
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
                "file": r.get("path", paths[0]),
                "line": (r.get("start") or {}).get("line", 0),
                "message": (r.get("extra") or {}).get("message", ""),
            }
        )
    return findings
