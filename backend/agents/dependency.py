"""Dependency Audit agent — known CVEs in declared dependencies.

Ground truth: pip-audit (Python) + npm audit (JS). No LLM — findings are
deterministic facts (CVE id + fix version), so this step is free (zero tokens)
and cannot hallucinate. Each finding cites OWASP A06 (Vulnerable & Outdated
Components).
"""

from __future__ import annotations

from ..state import ReviewState
from ..tools import run_dependency_audit

_CITATION = (
    "Keep dependencies patched — OWASP Top 10 A06:2021 "
    "Vulnerable and Outdated Components"
)


def dependency_node(state: ReviewState) -> ReviewState:
    """Audit declared dependencies for known vulnerabilities (tool-grounded, no LLM)."""
    ctx = state.get("context", {})
    review_path = ctx.get("review_path") or ""
    if not review_path:
        return {}

    raw = run_dependency_audit(review_path)
    for r in raw:
        r["type"] = "dependency"
        r["category"] = "dependency"

    findings = []
    for r in raw:
        findings.append({
            "type": "dependency",
            "category": "dependency",
            "issue": r["message"],
            "suggestion": "Upgrade to a patched version (see the fix note in the issue).",
            "file": r["file"],
            "line": r.get("line", 0),
            "severity": r.get("severity", "major"),
            "effort": "low",
            "confidence": 0.95,
            "tool_evidence": r.get("code", ""),
            "tool_grounded": True,
            "research_basis": [_CITATION],
        })

    other_finds = [f for f in state.get("findings", []) if f.get("category") != "dependency"]
    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "dependency"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
    }
