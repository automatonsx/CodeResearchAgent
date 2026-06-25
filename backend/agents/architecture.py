"""Architecture & Design agent — KB + best_practices corpus grounded review.

Flow:
  1. Read file content (capped per file).
  2. Load project KB for the reviewed files.
  3. Query ChromaDB (best_practices.json) for architecture best practices relevant
     to the detected language/patterns — no web search.
  4. Pass file content + KB + corpus practices to the LLM.
  5. Validate findings against actually reviewed files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..state import ReviewState
from ..llm import chat_json, load_prompt
from ..knowledge.retrieve import relevant_kb
from ..corpus.build_index import retrieve as corpus_retrieve

_MAX_FILES = 12
_MAX_CHARS = 2500
_MAX_CORPUS_HITS = 8


def _corpus_for_architecture(language: str, file_names: list[str]) -> list[dict]:
    """Query best_practices.json corpus for architecture-relevant practices."""
    queries = [
        f"{language} architecture design patterns",
        "separation of concerns module structure",
        "code organization maintainability",
    ]
    seen: set[str] = set()
    hits: list[dict] = []
    for q in queries:
        for h in corpus_retrieve(q, k=4, category="design"):
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


def architecture_node(state: ReviewState) -> ReviewState:
    ctx = state.get("context", {})
    review_path = ctx.get("review_path") or ""
    files = ctx.get("files", [])
    language = ctx.get("language", "unknown")
    if not files or not review_path:
        return {}

    # ── 1. Build rel-path → abs-path mapping ─────────────────────────────
    rel_to_abs: dict[str, str] = {}
    for f in files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    # ── 2. Read file content (capped) ────────────────────────────────────
    reviewed: list[dict] = []
    for rel, absf in list(rel_to_abs.items())[:_MAX_FILES]:
        try:
            raw = Path(absf).read_text(encoding="utf-8", errors="ignore")
            truncated = len(raw) > _MAX_CHARS
            content = raw[:_MAX_CHARS]
        except Exception:
            content = ""
            truncated = False
        entry: dict = {"file": rel, "content": content}
        if truncated:
            import sys
            print(
                f"[Scout/architecture] {rel} truncated to {_MAX_CHARS} chars "
                f"(full size: {len(raw)} chars) — review may be incomplete.",
                file=sys.stderr,
            )
            entry["truncated"] = True
        reviewed.append(entry)

    # ── 3. Project KB (optional) ─────────────────────────────────────────
    kb = relevant_kb(list(rel_to_abs.keys()))
    has_kb = bool(kb.get("modules"))

    # ── 4. Corpus best practices (best_practices.json via ChromaDB) ───────
    corpus_hits = _corpus_for_architecture(language, list(rel_to_abs.keys()))

    # Skip if nothing to ground on
    if not has_kb and not corpus_hits:
        return {}

    # ── 5. Collect prior findings to avoid duplication ───────────────────
    prior_findings = state.get("findings", [])
    already_reported = []
    for f in prior_findings:
        try:
            rel = os.path.relpath(f.get("file", ""), review_path).replace("\\", "/")
        except Exception:
            rel = ""
        issue_text = (f.get("issue") or "")[:100]
        if issue_text:
            already_reported.append({
                "file": rel,
                "category": f.get("category", ""),
                "issue": issue_text,
            })

    # ── 6. Build LLM payload ──────────────────────────────────────────────
    payload: dict = {
        "reviewed_files": reviewed,
        "corpus_best_practices": corpus_hits,
        "already_reported_issues": already_reported,
    }
    if has_kb:
        payload["overview"] = kb.get("overview", "")
        payload["kb_modules"] = kb["modules"]

    prompt = load_prompt("architecture") + "\n\nINPUT:\n" + json.dumps(
        payload, indent=2, ensure_ascii=False
    )
    try:
        data = chat_json("You are a senior software architect.", prompt)
        recs = data.get("recommendations") or []
    except Exception:
        recs = []

    # ── 7. Validate and annotate findings ────────────────────────────────
    valid_rel = set(rel_to_abs)
    corpus_ids = {h["practice_id"] for h in corpus_hits}

    findings: list[dict] = []
    for r in recs:
        rel = (r.get("file") or "").replace("\\", "/")
        if rel not in valid_rel:
            continue

        r["file"] = rel_to_abs[rel]
        r["line"] = 0
        r.setdefault("type", "design")
        r.setdefault("severity", "suggestion")
        r.setdefault("effort", "medium")
        r.setdefault("confidence", 0.5)
        r["category"] = "design"
        r["tool_evidence"] = ""
        r["tool_grounded"] = False
        r["kb_grounded"] = has_kb and bool(r.get("kb_module"))

        # Build research_basis from KB and corpus citations only
        basis: list[str] = []
        if r.get("kb_module") and has_kb:
            basis.append(f"KB: {r['kb_module']}")
        # Validate corpus refs — only keep ones that were actually in the lookup
        for ref in (r.get("research_refs") or []):
            if isinstance(ref, dict):
                pid = ref.get("practice_id", "")
                if pid in corpus_ids:
                    basis.append(f"{ref.get('title', pid)} — {ref.get('source', '')}")
        r["research_basis"] = basis if basis else r.get("research_basis", [])
        r.pop("research_refs", None)

        findings.append(r)

    other = [f for f in state.get("findings", []) if f.get("category") != "design"]
    return {"findings": other + findings}
