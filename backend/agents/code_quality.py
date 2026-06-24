"""Code-Quality Agent — smells, complexity, dead code, missing tests.

Ground truth: ruff (style/bug/complexity rules) + AST checks. The LLM structures
these into actionable, scored findings.
"""

from __future__ import annotations

from ..state import ReviewState
from ..tools import run_ruff, ast_findings
from ._structure import structure_findings
from ._generic import generic_review


def code_quality_node(state: ReviewState) -> ReviewState:
    """Review code quality for any language.

    Python is tool-grounded (ruff + ast); other languages are reviewed by the
    quote-grounded generic LLM reviewer (Critic-verified).
    """
    ctx = state.get("context", {})
    py_files = ctx.get("py_files", [])
    other_files = ctx.get("other_files", [])
    critique = state.get("critique")

    # Python: ground-truth tools.
    raw = []
    py_findings = []
    if py_files:
        raw = run_ruff(py_files, select="E,F,W,C90,B") + ast_findings(py_files)
        for r in raw:
            r["category"] = "code"
        py_findings = structure_findings("code_quality", "code", raw, critique)

    # Any other language: generic LLM reviewer.
    other_findings = generic_review(other_files, critique) if other_files else []

    findings = py_findings + other_findings

    # Replace this category's results (idempotent across re-check loops).
    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "code"]
    other_finds = [f for f in state.get("findings", []) if f.get("category") != "code"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
    }
