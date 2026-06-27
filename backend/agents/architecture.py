"""Architecture & Design agent — KB + best_practices corpus grounded review.

Flow:
  1. Read every reviewed file (each bounded to a per-file ceiling).
  2. Load project KB for the reviewed files.
  3. Query ChromaDB (best_practices.json) for architecture best practices relevant
     to the detected language/patterns — no web search.
  4. Split files into size-bounded batches; pass each batch + KB + corpus practices
     to the LLM concurrently, then merge findings.
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
from ..tools import code_skeleton
from ._batch import batch_by_size, map_batches

# Fallback when a file's language isn't supported by the skeleton extractor: send a
# small head (imports/declarations usually sit at the top), not the whole body.
_HEAD_CHARS = 1500
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

    # ── 1. Build rel-path → abs-path mapping (ALL reviewed files) ─────────
    rel_to_abs: dict[str, str] = {}
    for f in files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    # ── 2. Build a compact structural skeleton per file (NOT raw bodies) ──
    # Any supported language → skeleton (imports + class/function names + LOC) via
    # ast (Python) or tree-sitter (JS/TS/Java/Go/…). Unsupported → small text head.
    # This carries the structure an architect needs at a fraction of the tokens.
    reviewed: list[dict] = []
    for rel, absf in rel_to_abs.items():
        skel = code_skeleton(absf)
        if skel is not None:
            reviewed.append({"file": rel, "skeleton": skel})
            continue
        try:
            head = Path(absf).read_text(encoding="utf-8", errors="ignore")[:_HEAD_CHARS]
        except Exception:
            continue
        reviewed.append({"file": rel, "head": head})
    if not reviewed:
        return {}

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

    # ── 6. Review each batch of files concurrently ───────────────────────
    prompt_template = load_prompt("architecture")

    def _review_batch(batch: list[dict]) -> list[dict]:
        payload: dict = {
            "reviewed_files": batch,
            "corpus_best_practices": corpus_hits,
            "already_reported_issues": already_reported,
        }
        if has_kb:
            payload["overview"] = kb.get("overview", "")
            payload["kb_modules"] = kb["modules"]
        prompt = prompt_template + "\n\nINPUT:\n" + json.dumps(
            payload, indent=2, ensure_ascii=False
        )
        # Let errors propagate — map_batches bisects and retries a failing batch.
        data = chat_json("You are a senior software architect.", prompt)
        return data.get("recommendations") or []

    # Skeletons are tiny, so pack as many files as fit per call (size-bound, not the
    # small default item cap) → ~1 request for the whole repo, and the LLM sees the
    # cross-file structure it needs. Split only kicks in if a packed call overflows.
    batches = batch_by_size(reviewed, lambda e: len(json.dumps(e)), max_items=200)
    recs = map_batches(batches, _review_batch, label="architecture")

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
