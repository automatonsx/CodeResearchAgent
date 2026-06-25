"""Knowledge Extractor — distills architecture facts from a diff or a repo snapshot."""

from __future__ import annotations

import json

from ..llm import chat_json, load_prompt


def _extract(current_kb: dict, mode: str, payload: dict) -> dict:
    prompt = (
        load_prompt("knowledge_extractor")
        + f"\n\nMODE: {mode}\n\nCURRENT KB:\n"
        + json.dumps(current_kb, indent=2, ensure_ascii=False)
        + f"\n\n{mode.upper()} INPUT:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )
    try:
        data = chat_json("You are a precise software architecture analyst.", prompt)
    except Exception:
        data = {}
    data.setdefault("modules", {})
    data.setdefault("change_summary", "")
    return data


def extract_from_diff(current_kb: dict, diff_text: str) -> dict:
    """Update the KB from a merged diff. Returns {overview?, modules, change_summary}."""
    if not diff_text.strip():
        return {"modules": {}, "change_summary": "No diff content."}
    # Keep the prompt bounded for very large merges.
    return _extract(current_kb, "diff", {"diff": diff_text[:60000]})


def extract_seed(repo_map: str, docs: dict) -> dict:
    """Bootstrap the KB from the current repo (file tree + README/DESIGN)."""
    return _extract({}, "seed", {"repo_map": repo_map, "docs": docs})
