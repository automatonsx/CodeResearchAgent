"""Test Coverage agent — identify missing tests and suggest concrete test cases.

Scans source files for untested functions/classes, runs web research on testing
best practices for the detected stack, and asks the LLM to produce actionable,
runnable test suggestions grounded in the actual code.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from ..state import ReviewState
from ..llm import chat_json, load_prompt
from ..tools.web_research import research_for_tests, detect_frameworks

_MAX_SOURCE_FILES = 12
_MAX_CHARS = 2000
_MAX_WEB_RESULTS = 9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_test_file(path: str) -> bool:
    p = Path(path)
    name = p.name.lower()
    parts = [part.lower() for part in p.parts]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
        or "tests" in parts
        or "test" in parts
        or "__tests__" in parts
    )


def _extract_python_functions(file_path: str) -> list[str]:
    """Return public function and method names via AST (Python only)."""
    try:
        src = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    names.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    names.append(node.name)
        return names[:30]
    except Exception:
        return []


def _extract_js_functions(content: str) -> list[str]:
    """Rough function-name extraction for JS/TS via regex."""
    patterns = [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(",
        r"class\s+(\w+)",
    ]
    names: list[str] = []
    for pat in patterns:
        names += re.findall(pat, content)
    return list(dict.fromkeys(names))[:30]  # deduplicate, preserve order


def _extract_functions(file_path: str, language: str) -> list[str]:
    if language == "python":
        return _extract_python_functions(file_path)
    content = ""
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    if language in ("javascript", "typescript"):
        return _extract_js_functions(content)
    return []


def _test_names(file_path: str, language: str) -> list[str]:
    """Extract test function names from a test file."""
    if language == "python":
        return [n for n in _extract_python_functions(file_path) if n.startswith("test")]
    content = ""
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return re.findall(r"(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]", content)[:30]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def test_review_node(state: ReviewState) -> ReviewState:
    ctx = state.get("context", {})
    language = (ctx.get("language") or "python").lower()
    review_path = ctx.get("review_path") or ""
    files = ctx.get("files", [])

    if not files or not review_path:
        return {}

    # Split into test vs source files
    test_files = [f for f in files if _is_test_file(f)]
    source_files = [f for f in files if not _is_test_file(f)]

    if not source_files:
        return {}

    # Build rel-path → abs-path for source files
    rel_to_abs: dict[str, str] = {}
    for f in source_files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    # Read source content + extract function signatures
    source_content: list[dict] = []
    for rel, absf in list(rel_to_abs.items())[:_MAX_SOURCE_FILES]:
        try:
            content = Path(absf).read_text(encoding="utf-8", errors="ignore")[:_MAX_CHARS]
        except Exception:
            content = ""
        funcs = _extract_functions(absf, language)
        source_content.append({"file": rel, "content": content, "functions": funcs})

    # Summarise existing tests (just file + what they test)
    existing_tests: list[dict] = []
    for tf in test_files[:6]:
        rel = os.path.basename(tf)
        tests = _test_names(tf, language)
        existing_tests.append({"test_file": rel, "tests_defined": tests})

    # Web research for testing patterns
    frameworks = detect_frameworks(source_content)
    web_results = research_for_tests(language, frameworks)
    web_results_for_prompt = web_results[:_MAX_WEB_RESULTS]

    # Build LLM payload
    payload = {
        "language": language,
        "source_files": source_content,
        "existing_tests": existing_tests,
        "has_any_tests": bool(test_files),
        "web_research": web_results_for_prompt,
    }
    prompt = (
        load_prompt("test_review")
        + "\n\nINPUT:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )
    try:
        data = chat_json("You are a senior test engineer.", prompt)
        recs = data.get("test_recommendations") or []
    except Exception:
        recs = []

    # Validate and annotate
    valid_rel = set(rel_to_abs)
    web_url_set = {r["url"] for r in web_results if r.get("url")}

    findings: list[dict] = []
    for r in recs:
        rel = (r.get("file") or "").replace("\\", "/")
        if rel not in valid_rel:
            continue

        r["file"] = rel_to_abs[rel]
        r["line"] = r.get("line", 0)
        r.setdefault("type", "testing")
        r.setdefault("severity", "minor")
        r.setdefault("effort", "medium")
        r.setdefault("confidence", 0.7)
        r["category"] = "testing"
        r["tool_evidence"] = ""
        r["tool_grounded"] = False
        r["kb_grounded"] = False

        safe_refs = [
            ref for ref in (r.get("research_refs") or [])
            if isinstance(ref, dict) and ref.get("url") in web_url_set
        ]
        r["research_refs"] = safe_refs
        r["research_basis"] = [
            f"{ref.get('title', 'Web ref')} — {ref['url']}" for ref in safe_refs
        ]
        findings.append(r)

    other = [f for f in state.get("findings", []) if f.get("category") != "testing"]

    # Merge web research from previous nodes
    seen = {r["url"] for r in state.get("web_research", []) if r.get("url")}
    merged_web = list(state.get("web_research", [])) + [
        r for r in web_results if r.get("url") and r["url"] not in seen
    ]

    return {"findings": other + findings, "web_research": merged_web}
