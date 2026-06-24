"""Language-agnostic LLM reviewer for files with no dedicated linter.

Sends numbered source to the LLM, which must quote the offending line. The Critic
later verifies each quote against the file, so hallucinated findings get dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..llm import chat_json, load_prompt

_MAX_FILES = 15
_MAX_LINES = 250


def generic_review(files: list[str], critique: dict | None = None) -> list[dict]:
    """Return structured findings for non-Python source files (judgment, Critic-verified)."""
    files = files[:_MAX_FILES]
    payload, idmap = [], {}
    for i, f in enumerate(files):
        try:
            lines = Path(f).read_text(encoding="utf-8", errors="ignore").splitlines()[:_MAX_LINES]
        except Exception:
            continue
        if not lines:
            continue
        idmap[i] = f
        numbered = "\n".join(f"{j + 1}: {ln}" for j, ln in enumerate(lines))
        payload.append({"id": i, "file": Path(f).name,
                        "language": Path(f).suffix.lstrip("."), "code": numbered})
    if not payload:
        return []

    prompt = load_prompt("generic_review") + "\n\nFILES:\n" + json.dumps(payload, indent=2)
    if critique and critique.get("dropped"):
        prompt += "\n\nDo NOT re-emit these dropped items:\n" + json.dumps(
            critique.get("dropped", []), indent=2
        )
    try:
        data = chat_json("You are a precise multi-language code reviewer.", prompt)
        recs = data.get("recommendations") or data.get("findings") or []
    except Exception:
        recs = []

    out = []
    for r in recs:
        fid = r.get("id")
        if fid not in idmap:
            continue
        r["file"] = idmap[fid]
        r.pop("id", None)
        r.setdefault("type", "code")
        r.setdefault("severity", "minor")
        r.setdefault("effort", "low")
        r.setdefault("confidence", 0.55)
        r["category"] = "code"
        r["tool_evidence"] = ""        # no linter — pure judgment
        r["tool_grounded"] = False
        out.append(r)
    return out
