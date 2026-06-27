"""Dependency audit — known-vulnerability checks on declared dependencies.

Tool-grounded, no LLM. Two sources:
  - Python: parse pinned versions from requirements*.txt and query the OSV.dev
    advisory database directly (no venv / no dependency resolution, so it works
    even on old or conflicting pins — unlike `pip-audit -r`).
  - JS: `npm audit --json` (reads the lockfile; no install).

Both are best-effort: no network / no manifest / no lockfile → []. Findings are
deterministic facts (a CVE id + fix version), so this step costs zero tokens and
cannot hallucinate.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "vendor", "build"}
_NPM_SEV = {"critical": "critical", "high": "major", "moderate": "minor", "low": "suggestion"}

# Matches "name==version" (optionally with [extras]); ignores ranges/markers/options.
_PIN = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9._!+-]+)")
_OSV_URL = "https://api.osv.dev/v1/query"


def _find_manifests(repo_path: str, names: set[str]) -> list[Path]:
    out: list[Path] = []
    root = Path(repo_path)
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_dir() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.name in names:
            out.append(p)
    return out


# ── Python via OSV ──────────────────────────────────────────────────────────

def _parse_pins(path: Path) -> list[tuple[str, str]]:
    """Extract (name, version) for exact (==) pins; skip ranges/unpinned/options."""
    pins: list[tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return pins
    for line in lines:
        line = line.split("#")[0].split(";")[0].strip()
        if not line or line.startswith("-"):
            continue
        m = _PIN.match(line)
        if m:
            pins.append((m.group(1), m.group(2)))
    return pins


def _osv_query(name: str, version: str, ecosystem: str = "PyPI") -> dict:
    body = json.dumps({"version": version, "package": {"name": name, "ecosystem": ecosystem}}).encode()
    req = urllib.request.Request(_OSV_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def _osv_fix(vuln: dict) -> str:
    fixes: set[str] = set()
    for aff in vuln.get("affected", []) or []:
        for rng in aff.get("ranges", []) or []:
            for ev in rng.get("events", []) or []:
                if "fixed" in ev:
                    fixes.add(ev["fixed"])
    return ", ".join(sorted(fixes)) or "see advisory"


def run_pip_audit(repo_path: str) -> list[dict]:
    """Audit pinned Python deps against OSV.dev. [] on no network/no manifest."""
    pins: list[tuple[str, Path]] = []
    for req in _find_manifests(
        repo_path, {"requirements.txt", "requirements-dev.txt", "requirements-prod.txt"}
    ):
        for name, version in _parse_pins(req):
            pins.append(((name, version), req))

    if not pins:
        return []

    def _check(item):
        (name, version), req = item
        try:
            data = _osv_query(name, version, "PyPI")
        except Exception:
            return []
        out = []
        for v in data.get("vulns", []) or []:
            vid = v.get("id", "VULN")
            out.append({
                "tool": "osv", "code": vid, "file": str(req), "line": 0, "severity": "major",
                "message": f"{name} {version} has known vulnerability {vid} — fix: {_osv_fix(v)}",
            })
        return out

    findings: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for res in pool.map(_check, pins):
            findings.extend(res)
    return findings


# ── JS via npm audit ────────────────────────────────────────────────────────

def npm_audit_available() -> bool:
    return shutil.which("npm") is not None


def run_npm_audit(repo_path: str) -> list[dict]:
    """Run `npm audit --json` where a package.json + lockfile exist. [] otherwise."""
    exe = shutil.which("npm")
    if not exe:
        return []
    findings: list[dict] = []
    for pkg in _find_manifests(repo_path, {"package.json"}):
        d = pkg.parent
        if not ((d / "package-lock.json").exists() or (d / "npm-shrinkwrap.json").exists()):
            continue
        try:
            proc = subprocess.run(
                [exe, "audit", "--json"], cwd=str(d),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
            )
            data = json.loads(proc.stdout or "{}")
        except Exception:
            continue
        for name, info in (data.get("vulnerabilities") or {}).items():
            sev = _NPM_SEV.get(str(info.get("severity", "")).lower(), "minor")
            fix = "fix available" if info.get("fixAvailable") else "no direct fix"
            findings.append({
                "tool": "npm-audit", "code": f"npm:{name}", "file": str(pkg), "line": 0,
                "severity": sev,
                "message": f"{name} ({info.get('severity', '?')}) vulnerable: {info.get('range', '')} — {fix}",
            })
    return findings


def run_dependency_audit(repo_path: str) -> list[dict]:
    """All dependency-vulnerability findings for a repo (Python via OSV + JS via npm)."""
    return run_pip_audit(repo_path) + run_npm_audit(repo_path)
