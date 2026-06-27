"""Test Coverage agent — identify missing tests and suggest concrete test cases.

Scans source files for untested functions/classes, queries the best_practices
corpus for testing patterns relevant to the detected stack, and asks the LLM to
produce actionable, runnable test suggestions. No web search.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

from ..state import ReviewState
from ..llm import chat_json, load_prompt
from ..corpus.build_index import retrieve as corpus_retrieve
from ._batch import batch_by_size, map_batches

# test_review already extracts the function/class list via AST (see _extract_functions),
# which is what it needs to spot untested code. The file body is only light context, so
# we send a small head — not the whole file. This is the bulk of test_review's token cost.
_PER_FILE_CHARS = 1500
_MAX_CORPUS_HITS = 6


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
    patterns = [
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(",
        r"class\s+(\w+)",
    ]
    names: list[str] = []
    for pat in patterns:
        names += re.findall(pat, content)
    return list(dict.fromkeys(names))[:30]


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
    if language == "python":
        return [n for n in _extract_python_functions(file_path) if n.startswith("test")]
    content = ""
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return re.findall(r"(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]", content)[:30]


def _corpus_for_testing(language: str) -> list[dict]:
    """Query best_practices.json corpus for testing best practices."""
    queries = [
        f"{language} unit testing best practices",
        "test coverage assertions edge cases",
    ]
    seen: set[str] = set()
    hits: list[dict] = []
    for q in queries:
        for h in corpus_retrieve(q, k=4, category="testing"):
            pid = h.get("practice_id") or h.get("title", "")
            if pid and pid not in seen:
                seen.add(pid)
                hits.append({
                    "practice_id": pid,
                    "title": h.get("title", ""),
                    "principle": h.get("principle", ""),
                    "source": h.get("source", ""),
                })
            if len(hits) >= _MAX_CORPUS_HITS:
                break
        if len(hits) >= _MAX_CORPUS_HITS:
            break
    return hits


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

    test_files = [f for f in files if _is_test_file(f)]
    source_files = [f for f in files if not _is_test_file(f)]

    if not source_files:
        return {}

    rel_to_abs: dict[str, str] = {}
    for f in source_files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    source_content: list[dict] = []
    for rel, absf in rel_to_abs.items():
        try:
            content = Path(absf).read_text(encoding="utf-8", errors="ignore")[:_PER_FILE_CHARS]
        except Exception:
            content = ""
        funcs = _extract_functions(absf, language)
        source_content.append({"file": rel, "content": content, "functions": funcs})

    existing_tests: list[dict] = []
    for tf in test_files[:6]:
        rel = os.path.basename(tf)
        tests = _test_names(tf, language)
        existing_tests.append({"test_file": rel, "tests_defined": tests})

    corpus_hits = _corpus_for_testing(language)
    corpus_ids = {h["practice_id"] for h in corpus_hits}

    prompt_template = load_prompt("test_review")

    def _review_batch(batch: list[dict]) -> list[dict]:
        payload = {
            "language": language,
            "source_files": batch,
            "existing_tests": existing_tests,
            "has_any_tests": bool(test_files),
            "corpus_best_practices": corpus_hits,
        }
        prompt = (
            prompt_template
            + "\n\nINPUT:\n"
            + json.dumps(payload, indent=2, ensure_ascii=False)
        )
        # Let errors propagate — map_batches bisects and retries a failing batch.
        data = chat_json("You are a senior test engineer.", prompt)
        return data.get("test_recommendations") or []

    # Pack many files per call (size-bound, not the small default item cap) → few
    # requests. Split only kicks in if a packed call overflows.
    batches = batch_by_size(source_content, lambda e: len(e["content"]), max_items=200)
    recs = map_batches(batches, _review_batch, label="test_review")

    valid_rel = set(rel_to_abs)
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

        # Only keep corpus citations that were actually in the lookup
        basis: list[str] = []
        for ref in (r.get("research_refs") or []):
            if isinstance(ref, dict):
                pid = ref.get("practice_id", "")
                if pid in corpus_ids:
                    basis.append(f"{ref.get('title', pid)} — {ref.get('source', '')}")
        r["research_basis"] = basis if basis else r.get("research_basis", [])
        r.pop("research_refs", None)

        findings.append(r)

    other = [f for f in state.get("findings", []) if f.get("category") != "testing"]
    return {"findings": other + findings}
