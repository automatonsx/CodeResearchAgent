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

_SOURCE_ICON = {"paper": "📄", "preprint": "📝", "web": "🌐"}


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
    lines.append(f"*Effort: {f.get('effort', '?')} · Confidence: {f.get('confidence', '?')}*")
    lines.append("")
    return lines


def report_to_markdown(report: dict, source: str = "") -> str:
    score = report.get("score")
    score_str = "n/a" if score is None else f"{score}/10"
    stats = report.get("stats", {})
    web_sources = report.get("web_research_sources", [])
    all_findings = report.get("recommendations", [])

    lines = [
        "# Scout — Research-Aware Code Review Report",
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
        if stats.get("web_sources"):
            parts.append(f"{stats['web_sources']} web sources consulted")
        lines.append("**Coverage:** " + " · ".join(parts))
    lines += ["", "---", "", "## Executive Summary", "", report.get("summary", ""), "", "---", ""]

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

    # Web research sources
    if web_sources:
        lines += ["## 🔍 Web Research Sources", ""]
        lines.append(
            "The following papers, articles, and resources were retrieved and used to "
            "ground architectural, security, and testing recommendations:"
        )
        lines.append("")
        by_type: dict[str, list[dict]] = {}
        for s in web_sources:
            by_type.setdefault(s.get("source_type", "web"), []).append(s)

        for stype in ("paper", "preprint", "web"):
            items = by_type.get(stype, [])
            if not items:
                continue
            icon = _SOURCE_ICON.get(stype, "🌐")
            label = {"paper": "Academic Papers", "preprint": "Preprints (ArXiv)", "web": "Articles & Guides"}.get(stype, stype.title())
            lines.append(f"### {icon} {label}")
            lines.append("")
            for s in items:
                title = s.get("title", "Untitled")
                url = s.get("url", "")
                query = s.get("query", "")
                link = f"[{title}]({url})" if url else title
                lines.append(f"- {link}" + (f" *(query: {query})*" if query else ""))
            lines.append("")

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
