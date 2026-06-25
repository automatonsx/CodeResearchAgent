"""Report Generator — prioritize, score, and format the final review report."""

from __future__ import annotations

import json

from ..state import ReviewState, SEVERITY_ORDER
from ..llm import chat_json, load_prompt

# Score penalty per severity (out of 10).
_PENALTY = {"critical": 4.0, "major": 2.0, "minor": 0.7, "suggestion": 0.2}


def _score(findings: list[dict]) -> float:
    score = 10.0
    for f in findings:
        score -= _PENALTY.get(f.get("severity", "minor"), 0.5)
    return round(max(0.0, score), 1)


def _verdict(findings: list[dict]) -> str:
    sev = {f.get("severity") for f in findings}
    if "critical" in sev or "major" in sev:
        return "request_changes"
    if "minor" in sev:
        return "discuss"
    return "approve"


def report_node(state: ReviewState) -> ReviewState:
    """Build ``final_report`` = {summary, recommendations, verdict, score}."""
    ctx_error = state.get("context", {}).get("error")
    if ctx_error:
        return {
            "final_report": {
                "summary": f"Could not review the input: {ctx_error}",
                "recommendations": [],
                "verdict": "discuss",
                "score": 0.0,
                "stats": {"verified": 0, "dropped": 0, "iterations": 0, "language": "unknown",
                          "error": ctx_error},
            }
        }

    ctx = state.get("context", {})
    counts = ctx.get("counts", {})
    reviewed = counts.get("reviewed", len(ctx.get("py_files", [])))
    skipped = counts.get("skipped", 0)

    # No source code at all — don't fake an "approve". Be explicit about coverage.
    if reviewed == 0:
        return {
            "final_report": {
                "summary": (
                    "No source-code files were found to review (only assets/binaries or an "
                    "empty input). Point at a repo/subdir that contains code."
                ),
                "recommendations": [],
                "verdict": "discuss",
                "score": None,
                "stats": {"verified": 0, "dropped": 0, "iterations": 0,
                          "language": ctx.get("language", "unknown"), **counts},
            }
        }

    findings = sorted(
        state.get("findings", []),
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", "minor"), 9),
    )
    score = _score(findings)
    verdict = _verdict(findings)
    # Partial coverage with a clean result is "discuss", not a green approve.
    coverage_note = ""
    if not findings and skipped > 0:
        verdict = "discuss"
        score = None  # don't imply a perfect score on partial coverage
        coverage_note = (
            f" Note: {reviewed} file(s) were analyzed but {skipped} more were skipped by "
            "the size cap — a clean result here is not a full approval."
        )

    # LLM writes the executive summary; everything else is deterministic.
    summary = ""
    if findings:
        payload = {
            "findings": findings,
            "verdict": verdict,
            "score": score,
            "dropped_by_critic": state.get("critique", {}).get("dropped", []),
        }
        prompt = load_prompt("report") + "\n\nINPUT:\n" + json.dumps(payload, indent=2)
        try:
            data = chat_json("You are a senior reviewer writing a PR summary.", prompt)
            summary = data.get("summary", "") if isinstance(data, dict) else str(data)
        except Exception:
            summary = ""
    if not summary:
        n = len(findings)
        summary = (
            f"Review complete: {n} verified finding(s). Verdict: {verdict}, score {score}/10."
            if n else f"No issues found in the {reviewed} source file(s) reviewed."
        )
    summary += coverage_note

    # Deduplicate web research sources for the report
    seen_urls: set[str] = set()
    web_sources: list[dict] = []
    for r in state.get("web_research", []):
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            web_sources.append({
                "title": r.get("title", ""),
                "url": url,
                "source_type": r.get("source_type", "web"),
                "query": r.get("query", ""),
            })

    return {
        "final_report": {
            "summary": summary,
            "recommendations": findings,
            "verdict": verdict,
            "score": score,
            "web_research_sources": web_sources,
            "stats": {
                "verified": len(findings),
                "dropped": len(state.get("critique", {}).get("dropped", [])),
                "iterations": state.get("iterations", 0),
                "language": ctx.get("language", "unknown"),
                "reviewed": reviewed,
                "skipped": skipped,
                "web_sources": len(web_sources),
            },
        }
    }
