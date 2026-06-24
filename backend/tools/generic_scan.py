"""Language-agnostic ground-truth scanner.

High-precision regex checks that work for any language: hardcoded secrets, private
keys, and a few dangerous calls (eval, innerHTML, document.write). Each hit is a
verifiable file:line, so these are ground truth even where we have no linter.
"""

from __future__ import annotations

import re
from pathlib import Path

# (code, type, severity, compiled regex, message)
_PATTERNS = [
    ("SCAN-AWS-KEY", "security", "critical",
     re.compile(r"AKIA[0-9A-Z]{16}"), "Possible AWS access key id"),
    ("SCAN-PRIVATE-KEY", "security", "critical",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
     "Private key committed in source"),
    ("SCAN-SLACK-TOKEN", "security", "critical",
     re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"), "Possible Slack token"),
    ("SCAN-SECRET-ASSIGN", "security", "major",
     re.compile(r"""(?i)(?:api[_-]?key|secret|passwd|password|token|access[_-]?key)\s*[:=]\s*['"][^'"]{8,}['"]"""),
     "Possible hardcoded secret/credential"),
    ("SCAN-EVAL", "security", "major",
     re.compile(r"\beval\s*\("), "Use of eval() — code-injection risk"),
    ("SCAN-INNERHTML", "security", "major",
     re.compile(r"\.innerHTML\s*="), "Assignment to innerHTML — XSS risk"),
    ("SCAN-DOC-WRITE", "security", "minor",
     re.compile(r"\bdocument\.write\s*\("), "document.write — XSS / perf risk"),
    ("SCAN-MD5", "security", "minor",
     re.compile(r"(?i)\b(md5|sha1)\s*\("), "Weak hash function (MD5/SHA1)"),
]

# Avoid scanning obvious noise.
_SKIP_SUBSTR = (".min.", ".bundle.", "node_modules", "vendor/")


def _scan_file(path: Path) -> list[dict]:
    if any(s in str(path).replace("\\", "/") for s in _SKIP_SUBSTR):
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    out = []
    for i, line in enumerate(lines, 1):
        if len(line) > 1000:  # likely minified
            continue
        for code, ftype, sev, rx, msg in _PATTERNS:
            if rx.search(line):
                out.append({"tool": "scan", "code": code, "type": ftype,
                            "severity": sev, "file": str(path), "line": i, "message": msg})
    return out


def generic_scan(target) -> list[dict]:
    """Scan a file/dir/list for secrets and risky patterns (any language)."""
    if isinstance(target, (list, tuple)):
        files = [Path(f) for f in target]
    else:
        p = Path(target)
        files = [p] if p.is_file() else list(p.rglob("*"))
    out: list[dict] = []
    for f in files:
        if f.is_file():
            out.extend(_scan_file(f))
    return out
