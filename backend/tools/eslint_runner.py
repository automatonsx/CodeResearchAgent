"""eslint runner — ground-truth linting for JS/TS.

Optional, like semgrep: uses an isolated eslint install under
``backend/tools/eslint_env`` with a bundled flat config. If that env isn't set up
(``npm install`` there), returns [] and the generic LLM reviewer handles JS instead.

Setup:
    cd backend/tools/eslint_env && npm install
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

_ENV = Path(__file__).resolve().parent / "eslint_env"
_CONFIG = _ENV / "eslint.config.mjs"
_JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"}
_MAX_BYTES = 200_000  # skip large/minified files
_SECURITY_RULES = {"no-eval", "no-implied-eval", "no-new-func"}


@lru_cache(maxsize=1)
def _eslint_bin() -> str | None:
    bindir = _ENV / "node_modules" / ".bin"
    for name in (("eslint.cmd", "eslint") if sys.platform == "win32" else ("eslint",)):
        cand = bindir / name
        if cand.exists():
            return str(cand)
    return None


def eslint_available() -> bool:
    return _eslint_bin() is not None


def run_eslint(target) -> list[dict]:
    """Lint JS/TS files and return normalized findings; [] if eslint isn't set up."""
    exe = _eslint_bin()
    if not exe:
        return []

    files = target if isinstance(target, (list, tuple)) else [target]
    files = [
        f for f in files
        if Path(f).suffix.lower() in _JS_EXT
        and Path(f).is_file()
        and Path(f).stat().st_size <= _MAX_BYTES
    ]
    if not files:
        return []

    # eslint (flat config) only lints files under its base path = cwd.
    try:
        base = os.path.commonpath([str(Path(f).resolve()) for f in files])
        if Path(base).is_file():
            base = str(Path(base).parent)
    except Exception:
        base = str(Path(files[0]).resolve().parent)

    try:
        proc = subprocess.run(
            [exe, "--no-config-lookup", "--config", str(_CONFIG), "-f", "json",
             *[str(Path(f).resolve()) for f in files]],
            capture_output=True, text=True, cwd=base, timeout=180,
        )
        results = json.loads(proc.stdout or "[]")
    except Exception:
        return []

    findings = []
    for res in results:
        path = res.get("filePath", "")
        for m in res.get("messages", []):
            rule = m.get("ruleId")
            if rule is None or m.get("line") is None:
                continue  # parse/ignore notices, not real findings
            findings.append({
                "tool": "eslint",
                "code": rule,
                "type": "security" if rule in _SECURITY_RULES else "code",
                "file": path,
                "line": m.get("line", 0),
                "message": m.get("message", ""),
            })
    return findings
