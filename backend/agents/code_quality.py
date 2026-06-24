"""Code-Quality Agent — smells, complexity, dead code, missing tests.

Ground truth: ruff (style/bug/complexity rules) + AST checks. The LLM structures
these into actionable, scored findings.
"""

from __future__ import annotations

from pathlib import Path

from ..state import ReviewState
from ..tools import run_ruff, ast_findings, run_eslint, eslint_available
from ._structure import structure_findings
from ._generic import generic_review

_JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def code_quality_node(state: ReviewState) -> ReviewState:
    """Review code quality for any language.

    - Python  → ruff + ast (tool-grounded)
    - JS/TS    → eslint when set up (tool-grounded), else the LLM reviewer
    - other    → quote-grounded generic LLM reviewer (Critic-verified)
    """
    ctx = state.get("context", {})
    py_files = ctx.get("py_files", [])
    other_files = ctx.get("other_files", [])
    critique = state.get("critique")

    js_files = [f for f in other_files if Path(f).suffix.lower() in _JS_EXT]
    use_eslint = bool(js_files) and eslint_available()
    # The LLM reviewer covers everything eslint won't (non-JS, or JS if eslint is absent).
    llm_files = [f for f in other_files if f not in js_files] if use_eslint else other_files

    raw = []
    findings = []

    # Python: ground-truth tools.
    if py_files:
        py_raw = run_ruff(py_files, select="E,F,W,C90,B") + ast_findings(py_files)
        for r in py_raw:
            r["category"] = "code"
        raw += py_raw
        findings += structure_findings("code_quality", "code", py_raw, critique)

    # JS/TS: eslint as ground truth.
    if use_eslint:
        js_raw = run_eslint(js_files)
        for r in js_raw:
            r["category"] = "code"
        raw += js_raw
        findings += structure_findings("code_quality", "code", js_raw, critique)

    # Remaining languages (or JS without eslint): LLM reviewer.
    if llm_files:
        findings += generic_review(llm_files, critique)

    # Replace this category's results (idempotent across re-check loops).
    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "code"]
    other_finds = [f for f in state.get("findings", []) if f.get("category") != "code"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
    }
