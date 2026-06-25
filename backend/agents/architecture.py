"""Architecture & Design agent — KB-grounded + web-research-enriched review.

Flow:
  1. Build architecture-specific search queries from the review context.
  2. Run web research in parallel (Tavily → Semantic Scholar + ArXiv fallback).
  3. Load the project KB for the reviewed files (may be empty for external repos).
  4. Pass file content + KB + web research to the LLM.
  5. Validate and annotate findings with KB and web-research citations.

Unlike the original implementation, this node runs for *any* repo — not just ones that
match the internal KB. For repos without a KB match, findings are grounded solely in the
file content and web research.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..state import ReviewState
from ..llm import chat_json, load_prompt
from ..knowledge.retrieve import relevant_kb
from ..tools.web_research import research_for_architecture, build_architecture_queries

_MAX_FILES = 12
_MAX_CHARS = 2500
_MAX_WEB_RESULTS = 9   # cap passed to LLM to keep prompt size reasonable


def architecture_node(state: ReviewState) -> ReviewState:
    ctx = state.get("context", {})
    review_path = ctx.get("review_path") or ""
    files = ctx.get("files", [])
    if not files or not review_path:
        return {}

    # ------------------------------------------------------------------ #
    # 1. Build rel-path → abs-path mapping                               #
    # ------------------------------------------------------------------ #
    rel_to_abs: dict[str, str] = {}
    for f in files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    # ------------------------------------------------------------------ #
    # 2. Read file content (capped)                                       #
    # ------------------------------------------------------------------ #
    reviewed: list[dict] = []
    for rel, absf in list(rel_to_abs.items())[:_MAX_FILES]:
        try:
            content = Path(absf).read_text(encoding="utf-8", errors="ignore")[:_MAX_CHARS]
        except Exception:
            content = ""
        reviewed.append({"file": rel, "content": content})

    # ------------------------------------------------------------------ #
    # 3. Web research — run before KB lookup so we can skip if both empty #
    # ------------------------------------------------------------------ #
    queries = build_architecture_queries(ctx, reviewed)
    web_results = research_for_architecture(queries, max_per_query=3)
    # Trim to keep LLM prompt manageable
    web_results_for_prompt = web_results[:_MAX_WEB_RESULTS]

    # ------------------------------------------------------------------ #
    # 4. Project knowledge base (optional)                                #
    # ------------------------------------------------------------------ #
    kb = relevant_kb(list(rel_to_abs.keys()))
    has_kb = bool(kb.get("modules"))

    # Skip if we have neither KB nor web research — nothing to ground on
    if not has_kb and not web_results_for_prompt:
        return {}

    # ------------------------------------------------------------------ #
    # 5. Build LLM payload and call                                       #
    # ------------------------------------------------------------------ #
    payload: dict = {
        "reviewed_files": reviewed,
        "web_research": web_results_for_prompt,
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

    # ------------------------------------------------------------------ #
    # 6. Validate, annotate, and return findings                          #
    # ------------------------------------------------------------------ #
    valid_rel = set(rel_to_abs)
    web_url_set = {r["url"] for r in web_results if r.get("url")}

    findings: list[dict] = []
    for r in recs:
        rel = (r.get("file") or "").replace("\\", "/")
        if rel not in valid_rel:
            continue  # must reference a real reviewed file

        r["file"] = rel_to_abs[rel]
        r["line"] = 0                   # module/file-level; not line-anchored
        r.setdefault("type", "design")
        r.setdefault("severity", "suggestion")
        r.setdefault("effort", "medium")
        r.setdefault("confidence", 0.5)
        r["category"] = "design"
        r["tool_evidence"] = ""
        r["tool_grounded"] = False
        r["kb_grounded"] = has_kb and bool(r.get("kb_module"))

        # Build research_basis from KB and web citations
        basis: list[str] = []
        if r.get("kb_module") and has_kb:
            basis.append(f"KB: {r['kb_module']}")

        # Validate web citations — only keep refs whose URLs actually appeared in results
        safe_refs = [
            ref for ref in (r.get("research_refs") or [])
            if isinstance(ref, dict) and ref.get("url") in web_url_set
        ]
        for ref in safe_refs:
            basis.append(f"{ref.get('title', 'Web ref')} — {ref['url']}")
        r["research_refs"] = safe_refs
        r["research_basis"] = basis if basis else r.get("research_basis", [])

        findings.append(r)

    other = [f for f in state.get("findings", []) if f.get("category") != "design"]
    return {
        "findings": other + findings,
        "web_research": web_results,   # persist full result set in state for the report
    }
