"""Render a final review report as Markdown and save it to reports/."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_REPORTS = _ROOT / "reports"

_VERDICT = {"approve": "✅ Approve", "discuss": "💬 Discuss",
            "request_changes": "🚫 Request changes"}


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "review").lower()).strip("-")
    return (base[:50] or "review")


def _short_path(file: str, source: str) -> str:
    """Show the path relative to the reviewed repo when possible, else the basename."""
    try:
        if source and Path(source).is_dir():
            return Path(file).resolve().relative_to(Path(source).resolve()).as_posix()
    except Exception:
        pass
    return Path(file).name


def report_to_markdown(report: dict, source: str = "") -> str:
    """Return a Markdown rendering of a final_report dict."""
    score = report.get("score")
    score_str = "n/a" if score is None else f"{score}/10"
    stats = report.get("stats", {})
    lines = [
        "# Scout — Code Review Report",
        "",
        f"**Verdict:** {_VERDICT.get(report.get('verdict'), report.get('verdict'))}  ",
        f"**Score:** {score_str}  ",
    ]
    if source:
        lines.append(f"**Source:** `{source}`  ")
    if stats:
        lines.append(
            f"**Coverage:** {stats.get('verified', 0)} verified · "
            f"{stats.get('dropped', 0)} dropped by Critic · "
            f"{stats.get('iterations', 0)} re-check loop(s) · "
            f"{stats.get('reviewed', '?')} file(s) · {stats.get('language', '?')}"
        )
    lines += ["", "## Summary", "", report.get("summary", ""), "",
              f"## Findings ({len(report.get('recommendations', []))})", ""]

    for f in report.get("recommendations", []):
        sev = f.get("severity", "?")
        short = _short_path(f.get("file", ""), source)
        loc = f"{short}:{f['line']}" if f.get("line") else short
        lines.append(f"### [{sev}] {f.get('type', '')} — `{loc}`")
        lines.append(f"- **Issue:** {f.get('issue', '')}")
        if f.get("suggestion"):
            lines.append(f"- **Fix:** {f.get('suggestion')}")
        if f.get("example"):
            lines.append(f"- **Example:** `{str(f.get('example')).strip()}`")
        ev = f.get("tool_evidence") or "LLM judgment (Critic-verified)"
        lines.append(f"- **Tool evidence:** {ev}")
        if f.get("research_basis"):
            lines.append(f"- **Research basis:** {'; '.join(f.get('research_basis'))}")
        if f.get("effort"):
            lines.append(f"- **Effort:** {f.get('effort')} · **Confidence:** {f.get('confidence')}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _name_for(source: str) -> str:
    """A short, clean slug for the report file name."""
    s = (source or "").strip()
    if not s:
        return "review"
    if "diff --git" in s[:200] or "\n" in s:
        return "pr-diff"
    # repo path or URL → use the last path segment
    last = s.split("?")[0].rstrip("/").replace("\\", "/").split("/")[-1]
    return _slug(last)


def save_report(report: dict, source: str = "") -> str:
    """Write the report as Markdown to reports/<slug>.md and return the path."""
    _REPORTS.mkdir(exist_ok=True)
    path = _REPORTS / f"{_name_for(source)}.md"
    path.write_text(report_to_markdown(report, source), encoding="utf-8")
    return str(path)
