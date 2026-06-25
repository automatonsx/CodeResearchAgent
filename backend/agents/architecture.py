"""Architecture & Design agent — KB-grounded, higher-level review.

Activates only when the reviewed files map to known KB modules (i.e. a review of this
project). Produces architecture/design suggestions grounded in the project's own
knowledge base; stays quiet for unrelated external repos.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..state import ReviewState
from ..llm import chat_json, load_prompt
from ..knowledge.retrieve import relevant_kb

_MAX_FILES = 12
_MAX_CHARS = 2500


def architecture_node(state: ReviewState) -> ReviewState:
    ctx = state.get("context", {})
    review_path = ctx.get("review_path") or ""
    files = ctx.get("files", [])
    if not files or not review_path:
        return {}

    rel_to_abs = {}
    for f in files:
        try:
            rel = os.path.relpath(f, review_path).replace("\\", "/")
        except Exception:
            rel = os.path.basename(f)
        rel_to_abs[rel] = f

    kb = relevant_kb(list(rel_to_abs.keys()))
    if not kb["modules"]:
        return {}  # KB doesn't describe this code → skip the KB-aware lens

    reviewed = []
    for rel, absf in list(rel_to_abs.items())[:_MAX_FILES]:
        try:
            content = Path(absf).read_text(encoding="utf-8", errors="ignore")[:_MAX_CHARS]
        except Exception:
            content = ""
        reviewed.append({"file": rel, "content": content})

    payload = {"overview": kb["overview"], "kb_modules": kb["modules"], "reviewed_files": reviewed}
    prompt = load_prompt("architecture") + "\n\nINPUT:\n" + json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        data = chat_json("You are a senior software architect.", prompt)
        recs = data.get("recommendations") or []
    except Exception:
        recs = []

    valid_rel = set(rel_to_abs)
    findings = []
    for r in recs:
        rel = (r.get("file") or "").replace("\\", "/")
        if rel not in valid_rel:
            continue  # must reference a real reviewed file
        r["file"] = rel_to_abs[rel]
        r["line"] = 0                       # module/file-level, not line-anchored
        r.setdefault("type", "design")
        r.setdefault("severity", "suggestion")
        r.setdefault("effort", "medium")
        r.setdefault("confidence", 0.5)
        r["category"] = "design"
        r["tool_evidence"] = ""
        r["tool_grounded"] = False
        r["kb_grounded"] = True
        if r.get("kb_module"):
            r["research_basis"] = [f"KB: {r['kb_module']}"]
        findings.append(r)

    other = [f for f in state.get("findings", []) if f.get("category") != "design"]
    return {"findings": other + findings}
