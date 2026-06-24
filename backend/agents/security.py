"""Security Agent — secrets, injection, unsafe calls.

Ground truth: ruff's bandit (S) rules + semgrep when available. The LLM structures
these into scored security findings.
"""

from __future__ import annotations

from ..state import ReviewState
from ..tools import run_ruff, run_semgrep, generic_scan
from ._structure import structure_findings


def security_node(state: ReviewState) -> ReviewState:
    """Security review for any language: ruff S (Python) + semgrep + language-agnostic
    secret/pattern scan over all reviewed files."""
    ctx = state.get("context", {})
    py_files = ctx.get("py_files", [])
    all_files = ctx.get("files", [])
    if not all_files and not py_files:
        return {}

    raw = run_ruff(py_files, select="S") if py_files else []
    raw += run_semgrep(ctx.get("review_path") or "")
    raw += generic_scan(all_files)        # language-agnostic ground truth
    for r in raw:
        r["type"] = "security"
        r["category"] = "security"

    findings = structure_findings("security", "security", raw, state.get("critique"))

    # Replace this category's results (idempotent across re-check loops).
    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "security"]
    other_finds = [f for f in state.get("findings", []) if f.get("category") != "security"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
    }
