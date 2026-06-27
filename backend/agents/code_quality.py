"""Code-Quality Agent — smells, complexity, dead code, missing tests.

Ground truth per language:
  Python  → ruff + ast
  JS/TS    → eslint (when installed)
  other    → semgrep (when installed) — multi-language, findings-based
The LLM only structures these tool findings into scored items.

generic_review (LLM reads raw file bodies) is an expensive last resort — it's
OFF by default and only used when no tool covered a file AND SCOUT_GENERIC_REVIEW=1.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..state import ReviewState
from ..tools import (
    run_ruff, ast_findings, run_eslint, eslint_available,
    run_semgrep, semgrep_available,
)
from ._structure import structure_findings
from ._generic import generic_review

_JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"}

# semgrep ruleset for non-Python/JS files. "auto" auto-detects language (needs
# network for the registry). Override with SCOUT_SEMGREP_CONFIG.
_SEMGREP_CONFIG = os.environ.get("SCOUT_SEMGREP_CONFIG", "auto")
# Expensive LLM fallback for languages no tool covered — opt-in only.
_GENERIC_FALLBACK = os.environ.get("SCOUT_GENERIC_REVIEW", "0") == "1"


def code_quality_node(state: ReviewState) -> ReviewState:
    """Review code quality for any language.

    - Python  → ruff + ast (tool-grounded)
    - JS/TS    → eslint when set up (tool-grounded)
    - other    → semgrep when installed (tool-grounded); else skipped unless
                 SCOUT_GENERIC_REVIEW=1 enables the LLM fallback
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
        # F=pyflakes bugs, B=bugbear, C90=complexity, E7=statement/comparison errors
        # (incl. E722 bare except), E9=syntax errors. Formatting rules (E1/E2/E5 and
        # all W*: whitespace, line-length) are intentionally EXCLUDED — that's a
        # formatter's job, not a reviewer's, and they flood the LLM with noise.
        py_raw = run_ruff(py_files, select="F,B,C90,E7,E9") + ast_findings(py_files)
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

    # Remaining languages (or JS without eslint): semgrep first (cheap, findings-based).
    if llm_files:
        sem_raw = run_semgrep(llm_files, config=_SEMGREP_CONFIG) if semgrep_available() else []
        if sem_raw:
            for r in sem_raw:
                r["category"] = "code"
            raw += sem_raw
            findings += structure_findings("code_quality", "code", sem_raw, critique)
        # Expensive LLM fallback only when no tool covered these files AND opted in.
        elif _GENERIC_FALLBACK:
            findings += generic_review(llm_files, critique)

    # Replace this category's results (idempotent across re-check loops).
    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "code"]
    other_finds = [f for f in state.get("findings", []) if f.get("category") != "code"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
    }
