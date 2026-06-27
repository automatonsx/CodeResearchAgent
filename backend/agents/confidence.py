
"""Multi-factor confidence scoring for Scout findings and analysis quality.

Per-finding confidence replaces the flat 0.5 / 1.0 values with a weighted score
derived from observable evidence signals:

  tool_grounded      → deterministic scanner output (strongest signal)
  critic_verified    → file:line confirmed by Critic; quote matched
  has_web_citation   → real URL returned by web search and cited
  has_corpus_citation→ ChromaDB best-practice entry cited
  kb_grounded        → finding references a known KB module

Analysis quality aggregates per-finding signals into a review-level health report
with a letter grade so the consumer can judge whether to trust the output.
"""

from __future__ import annotations

from ..state import ReviewState

# ─── Per-finding scoring ──────────────────────────────────────────────────────

# Base scores by evidence tier
_BASE_TOOL    = 0.82   # deterministic scanner found it
_BASE_LINE    = 0.38   # LLM judgment anchored to a line (Critic will verify quote)
_BASE_FILE    = 0.42   # LLM judgment at file level (architecture / design / testing)

# Evidence bonuses (cumulative, capped at 1.0)
_BONUS = {
    "critic_verified":    0.08,
    "has_web_citation":   0.12,
    "has_corpus_citation":0.06,
    "kb_grounded":        0.10,
    "dual_grounded":      0.05,  # tool_grounded AND has_web_citation
}


def _has_web_citation(f: dict) -> bool:
    for field in ("research_basis", "research_refs"):
        for r in (f.get(field) or []):
            s = r if isinstance(r, str) else r.get("url", "")
            if "http" in s:
                return True
    return False


def _has_corpus_citation(f: dict) -> bool:
    for r in (f.get("research_basis") or []):
        if isinstance(r, str) and "http" not in r and r.strip():
            return True
    return False


def score_finding(f: dict, *, critic_verified: bool = True) -> tuple[float, dict]:
    """Compute confidence and a human-readable breakdown for one finding.

    Returns:
        (confidence, breakdown) where breakdown is a dict of boolean signals
        and intermediate score components — stored on the finding for display.
    """
    tool_grounded     = bool(f.get("tool_grounded"))
    kb_grounded       = bool(f.get("kb_grounded"))
    ftype             = f.get("type", "")
    web_citation      = _has_web_citation(f)
    corpus_citation   = _has_corpus_citation(f)

    # Base score by evidence tier
    if tool_grounded:
        base = _BASE_TOOL
    elif ftype in ("architecture", "design", "testing"):
        base = _BASE_FILE
    else:
        base = _BASE_LINE

    # Accumulate bonuses
    bonus = 0.0
    signals: list[str] = []

    if critic_verified:
        bonus += _BONUS["critic_verified"]
        signals.append("critic-verified")
    if web_citation:
        bonus += _BONUS["has_web_citation"]
        signals.append("web-cited")
        if tool_grounded:
            bonus += _BONUS["dual_grounded"]
    if corpus_citation:
        bonus += _BONUS["has_corpus_citation"]
        signals.append("corpus-cited")
    if kb_grounded:
        bonus += _BONUS["kb_grounded"]
        signals.append("kb-grounded")
    if tool_grounded:
        signals.insert(0, "tool-grounded")

    confidence = round(min(1.0, base + bonus), 2)

    breakdown = {
        "tool_grounded":      tool_grounded,
        "kb_grounded":        kb_grounded,
        "critic_verified":    critic_verified,
        "has_web_citation":   web_citation,
        "has_corpus_citation":corpus_citation,
        "base_score":         round(base, 2),
        "bonus":              round(bonus, 2),
        "signals":            signals,          # list shown in the report
    }
    return confidence, breakdown


# ─── Analysis quality ─────────────────────────────────────────────────────────

def analysis_quality(
    state: ReviewState,
    kept: list[dict],
    dropped: list[dict],
) -> dict:
    """Compute review-level analysis quality metrics.

    The result is included in final_report["analysis_quality"] and rendered
    as the "Analysis Quality" section in the Markdown report.
    """
    ctx    = state.get("context", {})
    counts = ctx.get("counts", {})

    total_attempted = len(kept) + len(dropped)

    # ── Grounding signals ────────────────────────────────────────────
    tool_grounded_n  = sum(1 for f in kept if f.get("tool_grounded"))
    web_cited_n      = sum(1 for f in kept if _has_web_citation(f))
    corpus_cited_n   = sum(1 for f in kept if _has_corpus_citation(f))
    kb_grounded_n    = sum(1 for f in kept if f.get("kb_grounded"))
    any_cited_n      = sum(
        1 for f in kept if _has_web_citation(f) or _has_corpus_citation(f)
    )

    grounding_rate   = tool_grounded_n / len(kept) if kept else 0.0
    citation_rate    = any_cited_n / len(kept) if kept else 0.0
    verification_rate= len(kept) / total_attempted if total_attempted else 1.0

    hallucinated_n   = sum(
        1 for d in dropped if "hallucinated" in d.get("reason", "")
    )
    # Hallucination rate relative to total LLM findings attempted (non-tool)
    llm_attempted    = sum(
        1 for d in dropped
        if "hallucinated" in d.get("reason", "") or "quoted" in d.get("reason", "")
    ) + sum(1 for f in kept if not f.get("tool_grounded"))
    hallucination_rate = hallucinated_n / llm_attempted if llm_attempted else 0.0

    # ── Overall confidence (weighted: tool findings count 1.5×) ─────
    total_w = 0.0
    weighted_conf = 0.0
    for f in kept:
        w = 1.5 if f.get("tool_grounded") else 1.0
        weighted_conf += float(f.get("confidence", 0.5)) * w
        total_w += w
    overall_confidence = round(weighted_conf / total_w, 2) if total_w else 0.0

    # ── Coverage ─────────────────────────────────────────────────────
    files_reviewed = counts.get("reviewed", len(ctx.get("py_files", [])))
    files_skipped  = counts.get("skipped", 0)
    total_files    = files_reviewed + files_skipped
    coverage_pct   = files_reviewed / total_files if total_files else 1.0

    # ── Grade ────────────────────────────────────────────────────────
    grade, rationale = _grade(
        overall_confidence, grounding_rate, verification_rate,
        citation_rate, coverage_pct, hallucination_rate,
    )

    return {
        "grade":               grade,
        "grade_rationale":     rationale,
        "overall_confidence":  overall_confidence,
        "findings_kept":       len(kept),
        "findings_dropped":    len(dropped),
        "verification_rate":   round(verification_rate, 2),
        "grounding": {
            "tool_grounded":   tool_grounded_n,
            "tool_grounded_pct": round(grounding_rate, 2),
            "web_cited":       web_cited_n,
            "corpus_cited":    corpus_cited_n,
            "kb_grounded":     kb_grounded_n,
            "citation_rate":   round(citation_rate, 2),
        },
        "hallucination": {
            "count":           hallucinated_n,
            "rate":            round(hallucination_rate, 2),
        },
        "coverage": {
            "files_reviewed":  files_reviewed,
            "files_skipped":   files_skipped,
            "coverage_pct":    round(coverage_pct, 2),
        },
    }


def _grade(
    confidence: float,
    grounding: float,
    verification: float,
    citation: float,
    coverage: float,
    hallucination: float,
) -> tuple[str, str]:
    """Weighted composite grade (A–D) with a one-sentence rationale."""
    composite = (
        confidence   * 0.30
        + grounding  * 0.28
        + verification * 0.18
        + citation   * 0.12
        + coverage   * 0.12
        - hallucination * 0.20   # penalty: high hallucination rate pulls grade down
    )
    composite = max(0.0, min(1.0, composite))

    if composite >= 0.78:
        grade = "A"
    elif composite >= 0.62:
        grade = "B"
    elif composite >= 0.46:
        grade = "C"
    else:
        grade = "D"

    issues: list[str] = []
    strengths: list[str] = []

    if confidence >= 0.75:
        strengths.append("high per-finding confidence")
    elif confidence < 0.55:
        issues.append("low per-finding confidence")

    if grounding >= 0.65:
        strengths.append("majority tool-grounded")
    elif grounding < 0.40:
        issues.append(f"only {int(grounding*100)}% tool-grounded")

    if verification >= 0.80:
        strengths.append("Critic verified most findings")
    elif verification < 0.60:
        issues.append("Critic dropped many findings")

    if hallucination > 0.25:
        issues.append(f"{int(hallucination*100)}% LLM hallucination rate")

    if coverage < 0.70:
        issues.append(f"only {int(coverage*100)}% of files reviewed")

    if issues:
        rationale = "Weaknesses: " + "; ".join(issues) + "."
    elif strengths:
        rationale = "Strengths: " + "; ".join(strengths) + "."
    else:
        rationale = "Analysis completed with standard confidence."

    return grade, rationale
