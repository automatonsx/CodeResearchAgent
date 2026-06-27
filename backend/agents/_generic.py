"""Language-agnostic LLM reviewer for files with no dedicated linter.

Sends numbered source to the LLM, which must quote the offending line. The Critic
later verifies each quote against the file, so hallucinated findings get dropped.

Files are split into size-bounded batches and reviewed concurrently so large repos
no longer overflow the model context window.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..llm import chat_json, load_prompt
from ._batch import batch_by_size, map_batches

_MAX_LINES = 400  # per-file line ceiling (batching handles total size)
_MAX_LINE_CHARS = 300  # trim pathologically long lines (minified/blobs) — see _snippet.py


def _clip(text: str) -> str:
    return text[:_MAX_LINE_CHARS] + " …[truncated]" if len(text) > _MAX_LINE_CHARS else text


def generic_review(files: list[str], critique: dict | None = None) -> list[dict]:
    """Return structured findings for non-Python source files (judgment, Critic-verified)."""
    # Build one payload entry per file with a stable global id so results from any
    # batch can be mapped back to the right file after merging.
    entries: list[dict] = []
    idmap: dict[int, str] = {}
    for i, f in enumerate(files):
        try:
            lines = Path(f).read_text(encoding="utf-8", errors="ignore").splitlines()[:_MAX_LINES]
        except Exception:
            continue
        if not lines:
            continue
        idmap[i] = f
        numbered = "\n".join(f"{j + 1}: {_clip(ln)}" for j, ln in enumerate(lines))
        entries.append({"id": i, "file": Path(f).name,
                        "language": Path(f).suffix.lstrip("."), "code": numbered})
    if not entries:
        return []

    prompt_template = load_prompt("generic_review")
    dropped = (critique or {}).get("dropped") if critique else None

    def _review_batch(batch: list[dict]) -> list[dict]:
        prompt = prompt_template + "\n\nFILES:\n" + json.dumps(batch, indent=2)
        if dropped:
            prompt += "\n\nDo NOT re-emit these dropped items:\n" + json.dumps(
                dropped, indent=2
            )
        # Let errors propagate — map_batches bisects and retries a failing batch.
        data = chat_json("You are a precise multi-language code reviewer.", prompt)
        return data.get("recommendations") or data.get("findings") or []

    batches = batch_by_size(entries, lambda e: len(e["code"]))
    recs = map_batches(batches, _review_batch, label="generic_review")

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
