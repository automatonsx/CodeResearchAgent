"""Shared: turn raw tool findings into structured findings via the LLM.

The LLM does NOT get to invent issues freely — it structures the provided tool
findings (ground truth) and may add at most a couple of judgment findings, but only
if it quotes the offending code. The Critic later re-verifies every finding.
"""

from __future__ import annotations

import json

from ..llm import chat_json, load_prompt
from ._snippet import read_snippet
from ._batch import batch_by_size, map_batches
from ..corpus.rule_map import citation_for


def structure_findings(
    prompt_name: str, category: str, raw: list[dict], critique: dict | None = None
) -> list[dict]:
    """Return structured findings (schema §7) grounded in ``raw`` tool findings.

    On a re-check pass, ``critique`` carries the Critic's dropped/low-confidence
    notes so the LLM avoids re-emitting false positives.
    """
    if not raw:
        return []

    # Build the LLM payload (enriched) and a SEPARATE (file,line)->snippet index.
    # The snippet is NOT duplicated into the payload — sending it once halves the
    # snippet tokens; the index keeps it available for downstream reattachment.
    enriched = []
    snippet_index: dict[tuple[str, int], str] = {}
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
            }
        )
        if snippet:
            snippet_index[(r.get("file") or "", r.get("line") or 0)] = snippet

    prompt_template = load_prompt(prompt_name)
    critic_suffix = ""
    if critique and (critique.get("dropped") or critique.get("low_confidence")):
        critic_suffix = (
            "\n\nCRITIC FEEDBACK FROM THE LAST PASS — do NOT re-emit dropped items; "
            "strengthen or remove low-confidence ones:\n" + json.dumps(
                {"dropped": critique.get("dropped", []),
                 "low_confidence": critique.get("low_confidence", []),
                 "notes": critique.get("notes", [])},
                indent=2,
            )
        )

    def _structure_batch(batch: list[dict]) -> list[dict]:
        # Let LLM/parse errors propagate — map_batches bisects and retries a failing
        # batch, so a bad item costs at most itself, never the whole batch.
        prompt = (
            prompt_template
            + "\n\nTOOL FINDINGS (ground truth):\n"
            + json.dumps(batch, indent=2)
            + critic_suffix
        )
        data = chat_json(f"You are a precise {category} code reviewer.", prompt)
        return data.get("recommendations") or data.get("findings") or []

    # Findings expand on output (the LLM writes issue/recommendation/example per
    # item), so cap by COUNT — ~8 findings fit comfortably under the 4k output-token
    # limit, so replies never truncate (truncation is what triggered the retry/split
    # cascade). Fewer, fuller batches = fewer requests.
    batches = batch_by_size(
        enriched, lambda e: len(json.dumps(e)), max_chars=12000, max_items=8
    )
    findings = map_batches(batches, _structure_batch, label=f"structure:{prompt_name}")

    # Backfill required fields and tag the source category.
    valid_codes = {r.get("code") for r in raw}
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
        # Deterministic citation: if the rule code maps to a best practice, attach it
        # immediately — the grounding node will skip this finding (already has research_basis).
        if f["tool_grounded"] and not f.get("research_basis"):
            citation = citation_for(f.get("tool_evidence") or "")
            if citation:
                f["research_basis"] = [citation]
        out.append(f)
    return out
