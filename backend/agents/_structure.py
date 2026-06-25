"""Shared: turn raw tool findings into structured findings via the LLM.

The LLM does NOT get to invent issues freely — it structures the provided tool
findings (ground truth) and may add at most a couple of judgment findings, but only
if it quotes the offending code. The Critic later re-verifies every finding.
"""

from __future__ import annotations

import json

from ..llm import chat_json, load_prompt
from ._snippet import read_snippet


def structure_findings(
    prompt_name: str, category: str, raw: list[dict], critique: dict | None = None
) -> list[dict]:
    """Return structured findings (schema §7) grounded in ``raw`` tool findings.

    On a re-check pass, ``critique`` carries the Critic's dropped/low-confidence
    notes so the LLM avoids re-emitting false positives.
    """
    if not raw:
        return []

    enriched = []
    for r in raw:
        snippet = read_snippet(r.get("file", ""), r.get("line", 0))
        enriched.append(
            {
                "tool": r.get("tool"),
                "tool_code": r.get("code"),
                "type": r.get("type", category),
                "file": r.get("file"),
                "line": r.get("line"),
                "message": r.get("message"),
                "snippet": snippet,
                # Preserved so downstream nodes (standards_node) can quote the actual bad code
                "_raw_snippet": snippet,
            }
        )

    prompt = load_prompt(prompt_name) + "\n\nTOOL FINDINGS (ground truth):\n" + json.dumps(
        enriched, indent=2
    )
    if critique and (critique.get("dropped") or critique.get("low_confidence")):
        prompt += (
            "\n\nCRITIC FEEDBACK FROM THE LAST PASS — do NOT re-emit dropped items; "
            "strengthen or remove low-confidence ones:\n" + json.dumps(
                {"dropped": critique.get("dropped", []),
                 "low_confidence": critique.get("low_confidence", []),
                 "notes": critique.get("notes", [])},
                indent=2,
            )
        )
    try:
        data = chat_json(f"You are a precise {category} code reviewer.", prompt)
        findings = data.get("recommendations") or data.get("findings") or []
    except Exception as exc:
        import sys
        print(
            f"[Scout] structure_findings({prompt_name!r}) failed — returning empty list. "
            f"Error: {exc}",
            file=sys.stderr,
        )
        findings = []

    # Backfill required fields and tag the source category.
    valid_codes = {r.get("code") for r in raw}
    # Build a (file, line) → snippet index so we can reattach the real bad-code snippet.
    snippet_index: dict[tuple[str, int], str] = {
        (e["file"] or "", e["line"] or 0): e["_raw_snippet"]
        for e in enriched
        if e.get("_raw_snippet")
    }
    out = []
    for f in findings:
        f.setdefault("type", category)
        f.setdefault("severity", "minor")
        f.setdefault("effort", "low")
        f.setdefault("confidence", 0.6)
        f["category"] = category
        # tool_evidence presence => high trust; absence => LLM judgment (Critic verifies).
        f["tool_grounded"] = f.get("tool_evidence") in valid_codes
        # Reattach the real offending snippet from the repo so downstream nodes can quote it.
        key = (f.get("file") or "", f.get("line") or 0)
        if key in snippet_index:
            f.setdefault("_raw_snippet", snippet_index[key])
        out.append(f)
    return out
