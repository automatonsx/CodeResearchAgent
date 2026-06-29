"""Render the final review report as a polished, self-contained HTML document.

Produces a single .html file (inline CSS, no external assets) styled in the
AutomatonsX brand — written next to scout-report.md so the report can be opened
in a browser or shared/printed to PDF. Mirrors report_md.py's data structure.
"""

from __future__ import annotations

import html
from pathlib import Path

_VERDICT = {
    "approve": ("Approve", "ok"),
    "discuss": ("Discuss", "warn"),
    "request_changes": ("Request Changes", "bad"),
}
_CATEGORY_META = {
    "security":   ("Security",              "mag"),
    "dependency": ("Dependencies",          "navy"),
    "code":       ("Code Quality",          "sky"),
    "design":     ("Architecture & Design", "mag"),
    "testing":    ("Test Coverage",         "lime"),
}
_CAT_ORDER = ["security", "dependency", "design", "testing", "code"]
_GRADE_CLASS = {"A": "gA", "B": "gB", "C": "gC", "D": "gD"}
# Severity → color, in priority order (matches the finding-card accents).
_SEV_ORDER = [("critical", "#d12b2b"), ("major", "#e07b18"),
              ("minor", "#c9a227"), ("suggestion", "#4FB6FF")]

# AutomatonsX A^X logo (inline SVG)
_LOGO = (
    '<svg viewBox="0 0 100 100" width="40" height="40" aria-hidden="true">'
    '<path d="M22 84 L46 24 L70 84" fill="none" stroke="#fff" stroke-width="5" '
    'stroke-linejoin="round" stroke-linecap="round"/>'
    '<path d="M34 64 L58 64" stroke="#fff" stroke-width="5" stroke-linecap="round"/>'
    '<path d="M70 16 L92 40 M92 16 L70 40" stroke="#C301B1" stroke-width="7" stroke-linecap="round"/>'
    '</svg>'
)


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _short_path(file: str, source: str) -> str:
    try:
        if source and Path(source).is_dir():
            return Path(file).resolve().relative_to(Path(source).resolve()).as_posix()
    except Exception:
        pass
    return Path(file).name


def _pct(v) -> str:
    try:
        return f"{float(v):.0%}"
    except Exception:
        return "—"


def _finding_html(f: dict, source: str) -> str:
    sev = f.get("severity", "minor")
    short = _short_path(f.get("file", ""), source)
    loc = f"{short}:{f['line']}" if f.get("line") else short

    parts = [f'<div class="finding sev-{_esc(sev)}">']
    parts.append(
        f'<div class="f-head"><span class="sev sev-{_esc(sev)}">{_esc(sev)}</span>'
        f'<code class="loc">{_esc(loc)}</code></div>'
    )
    parts.append(f'<p class="issue">{_esc(f.get("issue", ""))}</p>')
    if f.get("suggestion"):
        parts.append(f'<p class="fix"><span class="lbl">Fix</span>{_esc(f.get("suggestion"))}</p>')
    if f.get("example"):
        parts.append(f'<pre class="example"><code>{_esc(str(f.get("example")).strip())}</code></pre>')

    ev = f.get("tool_evidence") or "LLM judgment (Critic-verified)"
    meta = [f'<span class="ev">{_esc(ev)}</span>']
    if f.get("research_basis"):
        cites = " · ".join(_esc(c) for c in f.get("research_basis"))
        meta.append(f'<span class="cite">{cites}</span>')
    conf = f.get("confidence", "?")
    conf_str = _pct(conf) if isinstance(conf, float) else _esc(conf)
    signals = (f.get("confidence_breakdown", {}) or {}).get("signals", [])
    sig = f' · {_esc(", ".join(signals))}' if signals else ""
    meta.append(f'<span class="conf">Effort: {_esc(f.get("effort", "?"))} · Confidence: {conf_str}{sig}</span>')
    parts.append('<div class="f-meta">' + "".join(meta) + "</div>")
    parts.append("</div>")
    return "".join(parts)


def _quality_html(aq: dict) -> str:
    grade = aq.get("grade", "?")
    g = aq.get("grounding", {})
    cov = aq.get("coverage", {})
    hall = aq.get("hallucination", {})
    kept = aq.get("findings_kept", 0)
    total = kept + aq.get("findings_dropped", 0)
    files_rev = cov.get("files_reviewed", 0)
    files_tot = files_rev + cov.get("files_skipped", 0)

    def metric(label, value, sub):
        return (f'<div class="metric"><div class="m-val">{value}</div>'
                f'<div class="m-lab">{_esc(label)}</div><div class="m-sub">{_esc(sub)}</div></div>')

    metrics = "".join([
        metric("Overall confidence", _pct(aq.get("overall_confidence", 0)), "weighted per-finding"),
        metric("Critic verification", _pct(aq.get("verification_rate", 0)), f"{kept}/{total} survived"),
        metric("Tool-grounded", _pct(g.get("tool_grounded_pct", 0)), f"{g.get('tool_grounded', 0)} findings"),
        metric("Corpus citations", _pct(g.get("citation_rate", 0)), "with a best-practice cite"),
        metric("File coverage", _pct(cov.get("coverage_pct", 0)), f"{files_rev}/{files_tot} files"),
        metric("Hallucinations caught", str(hall.get("count", 0)), f"{_pct(hall.get('rate', 0))} of LLM findings"),
    ])
    return (
        '<section class="quality"><div class="q-head">'
        f'<span class="grade {_GRADE_CLASS.get(grade, "")}">{_esc(grade)}</span>'
        f'<div><h2>Analysis quality</h2><p>{_esc(aq.get("grade_rationale", ""))}</p></div>'
        '</div><div class="metrics">' + metrics + '</div>'
        '<p class="q-note">The grade reflects how much of the analysis is anchored in real tool output and '
        'citations rather than pure model judgment — not whether the code is good. A/B = trustworthy; '
        'C = review borderline items; D = treat model findings as suggestions.</p></section>'
    )


def _severity_chart_html(findings: list[dict]) -> str:
    """A self-contained donut (CSS conic-gradient) of findings by severity + legend."""
    counts = {k: 0 for k, _ in _SEV_ORDER}
    for f in findings:
        s = f.get("severity", "minor")
        counts[s if s in counts else "minor"] += 1
    total = sum(counts.values())
    if total == 0:
        return ""

    segs, start = [], 0.0
    for sev, color in _SEV_ORDER:
        n = counts[sev]
        if n == 0:
            continue
        end = start + n / total * 360
        segs.append(f"{color} {start:.2f}deg {end:.2f}deg")
        start = end
    grad = "conic-gradient(" + ", ".join(segs) + ")"

    legend = []
    for sev, color in _SEV_ORDER:
        n = counts[sev]
        pct = n / total * 100
        legend.append(
            f'<li><span class="sw" style="background:{color}"></span>'
            f'<span class="ln">{sev}</span><span class="lc">{n}</span>'
            f'<span class="lp">{pct:.0f}%</span></li>'
        )
    return (
        '<section class="sevcard"><h2>Findings by severity</h2><div class="sevwrap">'
        f'<div class="donut" style="background:{grad}"><div class="hole">'
        f'<span class="tot">{total}</span><span class="tl">findings</span></div></div>'
        '<ul class="sevleg">' + "".join(legend) + "</ul></div></section>"
    )


def report_to_html(report: dict, source: str = "") -> str:
    stats = report.get("stats", {})
    findings = report.get("recommendations", [])
    verdict_label, verdict_cls = _VERDICT.get(report.get("verdict"), (report.get("verdict", "—"), "warn"))

    cov_parts = []
    if stats:
        cov_parts = [
            f"{stats.get('verified', 0)} findings verified",
            f"{stats.get('dropped', 0)} dropped by Critic",
            f"{stats.get('reviewed', '?')} file(s) reviewed",
            f"language: {_esc(stats.get('language', '?'))}",
        ]

    by_cat: dict[str, list[dict]] = {}
    for f in findings:
        by_cat.setdefault(f.get("category", "code"), []).append(f)

    sections = []
    for cat in _CAT_ORDER:
        items = by_cat.get(cat, [])
        if not items:
            continue
        label, accent = _CATEGORY_META.get(cat, (cat.title(), "mag"))
        body = "".join(_finding_html(f, source) for f in items)
        n = len(items)
        sections.append(
            f'<section class="cat cat-{accent}"><h2 class="cat-h">{_esc(label)}'
            f'<span class="count">{n} finding{"s" if n != 1 else ""}</span></h2>{body}</section>'
        )

    sev_chart = _severity_chart_html(findings)
    aq_html = _quality_html(report["analysis_quality"]) if report.get("analysis_quality") else ""
    grade = stats.get("grade", "")
    grade_badge = (f'<span class="grade-pill {_GRADE_CLASS.get(grade, "")}">Grade {_esc(grade)}</span>'
                   if grade else "")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scout Code Review Report</title>
<style>
:root{{--magenta:#C301B1;--navy:#230C60;--sky:#4FB6FF;--lime:#76B82A;--midnight:#0A0A1E;
--paper:#fff;--ink:#230C60;--muted:#6f6a86;--line:#e9e6f2;
--font:"Helvetica Neue",Helvetica,Arial,sans-serif;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:#f6f4fb;color:var(--ink);font-family:var(--font);line-height:1.55;-webkit-font-smoothing:antialiased;}}
.wrap{{max-width:980px;margin:0 auto;padding:0 clamp(1rem,4vw,2rem);}}
a{{color:var(--magenta);}}
/* header */
header{{background:linear-gradient(125deg,var(--magenta) 0%,#6a0f86 45%,var(--navy) 100%);color:#fff;padding:clamp(2rem,5vw,3.2rem) 0;}}
header .top{{display:flex;align-items:center;gap:.6rem;margin-bottom:1.4rem;}}
header .word{{font-weight:700;font-size:1.1rem;}} header .word .x{{color:var(--sky);}}
header h1{{margin:0;font-size:clamp(1.7rem,4vw,2.6rem);letter-spacing:-.02em;}}
.badges{{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1rem;align-items:center;}}
.verdict{{font-weight:700;font-size:.85rem;letter-spacing:.04em;text-transform:uppercase;padding:.4rem .9rem;border-radius:999px;}}
.verdict.bad{{background:#ff5a7a;color:#fff;}} .verdict.warn{{background:var(--sky);color:#04243f;}} .verdict.ok{{background:var(--lime);color:#06270a;}}
.grade-pill{{font-weight:700;font-size:.8rem;padding:.4rem .8rem;border-radius:999px;background:rgba(255,255,255,.16);}}
.coverage{{margin-top:1rem;color:rgba(255,255,255,.85);font-size:.9rem;}}
.coverage .src{{font-family:ui-monospace,Menlo,Consolas,monospace;color:#fff;}}
/* summary */
.summary{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.6rem 1.8rem;margin:-2rem auto 2rem;box-shadow:0 18px 40px -28px rgba(35,12,96,.5);position:relative;}}
.summary h2{{margin:0 0 .5rem;color:var(--magenta);font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;}}
.summary p{{margin:0;font-size:1.08rem;}}
/* quality */
.quality{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.6rem 1.8rem;margin-bottom:2rem;}}
.q-head{{display:flex;gap:1.1rem;align-items:center;margin-bottom:1.2rem;}}
.q-head h2{{margin:0;font-size:1.2rem;color:var(--navy);}} .q-head p{{margin:.2rem 0 0;color:var(--muted);font-size:.92rem;}}
.grade{{width:54px;height:54px;border-radius:14px;display:grid;place-items:center;font-size:1.7rem;font-weight:700;color:#fff;flex:none;}}
.gA{{background:var(--lime);}} .gB{{background:var(--sky);color:#04243f;}} .gC{{background:#e0a52a;}} .gD{{background:#ff5a7a;}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;}}
.metric{{background:#faf9fe;border:1px solid var(--line);border-radius:12px;padding:.9rem 1rem;}}
.m-val{{font-size:1.5rem;font-weight:700;color:var(--navy);font-variant-numeric:tabular-nums;}}
.m-lab{{font-size:.82rem;font-weight:700;color:var(--ink);margin-top:.15rem;}} .m-sub{{font-size:.75rem;color:var(--muted);}}
.q-note{{margin:1.1rem 0 0;font-size:.82rem;color:var(--muted);border-left:3px solid var(--sky);padding-left:.8rem;}}
/* severity donut */
.sevcard{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:1.6rem 1.8rem;margin-bottom:2rem;}}
.sevcard h2{{margin:0 0 1.1rem;font-size:1.2rem;color:var(--navy);}}
.sevwrap{{display:flex;gap:2rem;align-items:center;flex-wrap:wrap;}}
.donut{{width:158px;height:158px;border-radius:50%;position:relative;flex:none;
  -webkit-print-color-adjust:exact;print-color-adjust:exact;box-shadow:0 10px 26px -18px rgba(35,12,96,.45);}}
.hole{{position:absolute;inset:25%;background:#fff;border-radius:50%;display:grid;place-items:center;text-align:center;}}
.hole .tot{{font-size:1.8rem;font-weight:700;color:var(--navy);line-height:1;font-variant-numeric:tabular-nums;}}
.hole .tl{{font-size:.66rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;}}
.sevleg{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.55rem;min-width:220px;flex:1;}}
.sevleg li{{display:flex;align-items:center;gap:.7rem;font-size:.95rem;}}
.sevleg .sw{{width:14px;height:14px;border-radius:4px;flex:none;}}
.sevleg .ln{{flex:1;text-transform:capitalize;color:var(--ink);}}
.sevleg .lc{{font-weight:700;color:var(--navy);font-variant-numeric:tabular-nums;}}
.sevleg .lp{{color:var(--muted);width:46px;text-align:right;font-variant-numeric:tabular-nums;}}
/* category sections */
.cat{{margin-bottom:2rem;}}
.cat-h{{display:flex;align-items:baseline;gap:.7rem;font-size:1.25rem;color:var(--navy);
border-left:5px solid var(--magenta);padding-left:.8rem;margin:0 0 1rem;}}
.cat-navy .cat-h{{border-color:var(--navy);}} .cat-sky .cat-h{{border-color:var(--sky);}}
.cat-lime .cat-h{{border-color:var(--lime);}} .cat-mag .cat-h{{border-color:var(--magenta);}}
.count{{font-size:.78rem;font-weight:700;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;}}
/* finding cards */
.finding{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.25rem;margin-bottom:.9rem;border-left:4px solid var(--line);}}
.finding.sev-critical{{border-left-color:#d12b2b;}} .finding.sev-major{{border-left-color:#e07b18;}}
.finding.sev-minor{{border-left-color:#c9a227;}} .finding.sev-suggestion{{border-left-color:var(--sky);}}
.f-head{{display:flex;align-items:center;gap:.7rem;margin-bottom:.5rem;flex-wrap:wrap;}}
.sev{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:.2rem .55rem;border-radius:999px;}}
.sev-critical{{background:#fdecec;color:#c0392b;}} .sev-major{{background:#fdf0e3;color:#c8731a;}}
.sev-minor{{background:#fbf6df;color:#8a7011;}} .sev-suggestion{{background:#e9f5ff;color:#2b78b8;}}
.loc{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.82rem;color:var(--navy);background:#f3f1f9;padding:.15rem .45rem;border-radius:6px;}}
.issue{{margin:.2rem 0 .5rem;font-weight:600;}}
.fix{{margin:.3rem 0;color:#2c2342;font-size:.95rem;}} .fix .lbl,.f-meta .ev::before{{}}
.lbl{{display:inline-block;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--lime);margin-right:.5rem;}}
.example{{background:var(--midnight);color:#eee;border-radius:10px;padding:.85rem 1rem;overflow-x:auto;font-size:.82rem;margin:.6rem 0;}}
.example code{{font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre;}}
.f-meta{{display:flex;flex-direction:column;gap:.2rem;margin-top:.6rem;font-size:.8rem;color:var(--muted);}}
.f-meta .ev{{color:var(--navy);font-weight:600;}} .f-meta .cite{{color:var(--magenta);}}
/* footer */
footer{{background:var(--midnight);color:#fff;padding:2rem 0;margin-top:2rem;}}
footer .wrap{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.8rem;}}
footer .word{{font-weight:700;}} footer .word .x{{color:var(--magenta);}}
footer .m{{font-size:.8rem;color:rgba(255,255,255,.6);}}
@media print{{body{{background:#fff;}} .summary{{box-shadow:none;}} header{{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}}}
</style></head>
<body>
<header><div class="wrap">
  <div class="top">{_LOGO}<span class="word">Automatons<span class="x">X</span></span></div>
  <h1>Scout Code Review Report</h1>
  <div class="badges"><span class="verdict {verdict_cls}">{_esc(verdict_label)}</span>{grade_badge}</div>
  {"<div class='coverage'>" + " &middot; ".join(cov_parts) + "</div>" if cov_parts else ""}
  {f"<div class='coverage'>Source: <span class='src'>{_esc(source)}</span></div>" if source else ""}
</div></header>

<main class="wrap">
  <section class="summary"><h2>Executive Summary</h2><p>{_esc(report.get("summary", ""))}</p></section>
  {sev_chart}
  {aq_html}
  {"".join(sections)}
</main>

<footer><div class="wrap">
  <span><span class="word">Automatons<span class="x">X</span></span></span>
  <span class="m">Scout &middot; Research-aware code review &middot; automatonsx.com</span>
</div></footer>
</body></html>
"""


def save_report_html_to_dir(report: dict, dest_dir: str, source: str = "") -> str:
    """Write the report as scout-report.html into *dest_dir* and return the path."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "scout-report.html"
    path.write_text(report_to_html(report, source), encoding="utf-8")
    return str(path)
