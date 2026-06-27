"""Render a final review report as sectioned Markdown and save it to reports/."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_REPORTS = _ROOT / "reports"

_VERDICT = {
    "approve": "✅ Approve",
    "discuss": "💬 Discuss",
    "request_changes": "🚫 Request Changes",
}

_CATEGORY_META = {
    "security":     ("🔒", "Security"),
    "code":         ("💻", "Code Quality"),
    "design":       ("🏗️",  "Architecture & Design"),
    "testing":      ("🧪", "Test Coverage"),
}


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "review").lower()).strip("-")
    return base[:50] or "review"


def _short_path(file: str, source: str) -> str:
    try:
        if source and Path(source).is_dir():
            return Path(file).resolve().relative_to(Path(source).resolve()).as_posix()
    except Exception:
        pass
    return Path(file).name


def _sev_badge(sev: str) -> str:
    return {"critical": "🔴 critical", "major": "🟠 major",
            "minor": "🟡 minor", "suggestion": "🔵 suggestion"}.get(sev, sev)


def _confidence_label(f: dict) -> str:
    conf = f.get("confidence", "?")
    breakdown = f.get("confidence_breakdown", {})
    signals = breakdown.get("signals", [])
    conf_str = f"{conf:.0%}" if isinstance(conf, float) else str(conf)
    if signals:
        conf_str += f" _({', '.join(signals)})_"
    return conf_str


def _finding_block(f: dict, source: str) -> list[str]:
    sev = f.get("severity", "?")
    short = _short_path(f.get("file", ""), source)
    loc = f"{short}:{f['line']}" if f.get("line") else short
    lines = [
        f"#### {_sev_badge(sev)} — `{loc}`",
        f"**Issue:** {f.get('issue', '')}",
    ]
    if f.get("suggestion"):
        lines.append(f"**Fix:** {f.get('suggestion')}")
    if f.get("example"):
        ex = str(f.get("example")).strip()
        if "\n" in ex:
            lines.append(f"**Example:**\n```\n{ex}\n```")
        else:
            lines.append(f"**Example:** `{ex}`")
    ev = f.get("tool_evidence") or "LLM judgment (Critic-verified)"
    lines.append(f"**Evidence:** {ev}")
    if f.get("research_basis"):
        lines.append("**Research:** " + " · ".join(f.get("research_basis")))
    lines.append(f"*Effort: {f.get('effort', '?')} · Confidence: {_confidence_label(f)}*")
    lines.append("")
    return lines


_GRADE_ICON = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴"}


def _analysis_quality_section(aq: dict) -> list[str]:
    grade = aq.get("grade", "?")
    icon = _GRADE_ICON.get(grade, "⚪")
    overall_conf = aq.get("overall_confidence", 0.0)
    ver_rate = aq.get("verification_rate", 0.0)
    grounding = aq.get("grounding", {})
    coverage = aq.get("coverage", {})
    hall = aq.get("hallucination", {})
    kept = aq.get("findings_kept", 0)
    total = kept + aq.get("findings_dropped", 0)
    tool_n = grounding.get("tool_grounded", 0)
    files_rev = coverage.get("files_reviewed", 0)
    files_skip = coverage.get("files_skipped", 0)

    lines = [
        "## 📊 Analysis Quality",
        "",
        f"**Grade: {icon} {grade}** — {aq.get('grade_rationale', '')}",
        "",
        "| Metric | Value | Interpretation |",
        "|--------|-------|----------------|",
        f"| Overall Confidence | **{overall_conf:.0%}** | Weighted avg of per-finding scores |",
        f"| Critic Verification Rate | {ver_rate:.0%} | {kept}/{total} findings survived Critic |",
        f"| Tool-Grounded Findings | {tool_n}/{kept} ({grounding.get('tool_grounded_pct', 0):.0%}) | Deterministic scanner output |",
        f"| Corpus Citation Rate | {grounding.get('citation_rate', 0):.0%} | Findings with best-practices corpus citation |",
        f"| File Coverage | {files_rev}/{files_rev + files_skip} ({coverage.get('coverage_pct', 0):.0%}) | Source files actually analyzed |",
        f"| Hallucinations Caught | {hall.get('count', 0)} ({hall.get('rate', 0):.0%} of LLM findings) | Dropped by Critic quote-match check |",
        "",
        "> **How to read this:** The grade reflects how much of the analysis is anchored in",
        "> real tool output and external evidence rather than pure LLM judgment. A or B means",
        "> you can trust the findings; C means review borderline items manually; D means",
        "> treat all LLM findings as suggestions requiring manual confirmation.",
        "",
        "---",
        "",
    ]
    return lines


def report_to_markdown(report: dict, source: str = "") -> str:
    score = report.get("score")
    score_str = "n/a" if score is None else f"{score}/10"
    stats = report.get("stats", {})
    all_findings = report.get("recommendations", [])

    lines = [
        "# Scout Code Review Report",
        "",
        f"**Verdict:** {_VERDICT.get(report.get('verdict'), report.get('verdict'))}  ",
        f"**Score:** {score_str}  ",
    ]
    if source:
        lines.append(f"**Source:** `{source}`  ")
    if stats:
        parts = [
            f"{stats.get('verified', 0)} findings verified",
            f"{stats.get('dropped', 0)} dropped by Critic",
            f"{stats.get('reviewed', '?')} file(s) reviewed",
            f"language: {stats.get('language', '?')}",
        ]
        if stats.get("grade"):
            grade = stats["grade"]
            parts.append(f"analysis grade: {_GRADE_ICON.get(grade, '')} {grade}")
        lines.append("**Coverage:** " + " · ".join(parts))
    lines += ["", "---", "", "## Executive Summary", "", report.get("summary", ""), "", "---", ""]

    aq = report.get("analysis_quality", {})
    if aq:
        lines += _analysis_quality_section(aq)

    # Group findings by category
    by_cat: dict[str, list[dict]] = {}
    for f in all_findings:
        cat = f.get("category", "code")
        by_cat.setdefault(cat, []).append(f)

    cat_order = ["security", "design", "testing", "code"]
    for cat in cat_order:
        findings = by_cat.get(cat, [])
        if not findings:
            continue
        icon, label = _CATEGORY_META.get(cat, ("•", cat.title()))
        lines.append(f"## {icon} {label} ({len(findings)} finding{'s' if len(findings) != 1 else ''})")
        lines.append("")
        for f in findings:
            lines += _finding_block(f, source)
        lines += ["---", ""]

    return "\n".join(lines).rstrip() + "\n"


def _name_for(source: str) -> str:
    s = (source or "").strip()
    if not s:
        return "review"
    if "diff --git" in s[:200] or "\n" in s:
        return "pr-diff"
    last = s.split("?")[0].rstrip("/").replace("\\", "/").split("/")[-1]
    return _slug(last)


def save_report(report: dict, source: str = "") -> str:
    """Write the report as Markdown to reports/<slug>.md and return the path."""
    _REPORTS.mkdir(exist_ok=True)
    path = _REPORTS / f"{_name_for(source)}.md"
    path.write_text(report_to_markdown(report, source), encoding="utf-8")
    return str(path)


def save_report_to_dir(report: dict, dest_dir: str, source: str = "") -> str:
    """Write the report as Markdown into *dest_dir*/scout-report.md and return the path.

    Used by run_standards() to place the report alongside SKILL.md in the target repo's
    .claude/ directory so both artefacts live together in the repo.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "scout-report.md"
    path.write_text(report_to_markdown(report, source), encoding="utf-8")
    return str(path)
