"""Post Scout's findings as an inline GitHub PR review (line-anchored comments).

Runs the review on a PR diff, maps each finding to a comment on its changed line,
and submits ONE review (summary + all inline comments) via the GitHub API.

Used by the CI workflow:
    python -m backend.notify.github_review            # posts the review
    python -m backend.notify.github_review --dry-run  # prints what it would post

Env: GITHUB_REPOSITORY (owner/repo), PR_NUMBER, GH_TOKEN (or GITHUB_TOKEN),
     PR_DIFF_FILE (default: pr.diff).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ..graph import build_graph
from ..state import initial_state
from ..report_md import report_to_markdown

_API = "https://api.github.com"


def review_pr_diff(diff_text: str):
    """Run the review and return (report, inline_comments).

    A finding becomes an inline comment only if it sits on a line the PR changed
    (GitHub rejects the whole review if any comment is off-diff).
    """
    final = build_graph().invoke(initial_state(diff_text, "pr_diff"), {"recursion_limit": 50})
    report = final.get("final_report", {})
    ctx = final.get("context", {})
    root = ctx.get("review_path", "")

    # Authoritative changed-line map, keyed by basename (robust across tool paths).
    files_by_base: dict[str, dict] = {}
    for k, lines in ctx.get("changed_lines", {}).items():
        rel = os.path.relpath(k, root).replace("\\", "/") if root else os.path.basename(k)
        files_by_base[os.path.basename(k)] = {"rel": rel, "lines": set(lines)}

    comments = []
    for f in report.get("recommendations", []):
        info = files_by_base.get(os.path.basename(f.get("file", "")))
        line = int(f.get("line") or 0)
        if not info or line not in info["lines"]:
            continue
        comments.append({
            "path": info["rel"],
            "line": line,
            "side": "RIGHT",
            "body": _comment_body(f),
        })
    return report, comments


def _comment_body(f: dict) -> str:
    sev = f.get("severity", "")
    parts = [f"**[{sev}] {f.get('type', '')}** — {f.get('issue', '')}"]
    if f.get("suggestion"):
        parts.append(f"**Fix:** {f['suggestion']}")
    if f.get("example"):
        parts.append(f"```\n{str(f['example']).strip()}\n```")
    evidence = f.get("tool_evidence") or "LLM judgment (Critic-verified)"
    tail = f"🔧 `{evidence}`"
    if f.get("research_basis"):
        tail += " · 📚 " + "; ".join(f["research_basis"])
    parts.append(tail)
    return "\n\n".join(parts)


def _summary_body(report: dict, n_inline: int) -> str:
    score = report.get("score")
    score_str = "n/a" if score is None else f"{score}/10"
    n_total = len(report.get("recommendations", []))
    return (
        "## 🛡️ Scout AI Review\n\n"
        f"**Verdict:** {report.get('verdict')} · **Score:** {score_str}\n\n"
        f"{report.get('summary', '')}\n\n"
        f"_{n_inline} inline comment(s) on changed lines · {n_total} finding(s) total · "
        "tool-grounded + Critic-verified. Advisory only — Scout never merges._"
    )


def post_review(owner: str, repo: str, pr: int, report: dict, comments: list, token: str) -> dict:
    """Submit one PR review with all inline comments. Falls back COMMENT if needed."""
    verdict = report.get("verdict")
    event = "REQUEST_CHANGES" if verdict == "request_changes" else "COMMENT"
    body = _summary_body(report, len(comments))
    url = f"{_API}/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "scout-review",
        "Content-Type": "application/json",
    }

    def _send(payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=40) as resp:
            return {"ok": True, "status": resp.status, "event": payload["event"]}

    payload = {"event": event, "body": body, "comments": comments}
    try:
        return _send(payload)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        # Can't REQUEST_CHANGES on your own PR, etc. → retry as a plain COMMENT.
        if event != "COMMENT":
            try:
                payload["event"] = "COMMENT"
                return _send(payload)
            except urllib.error.HTTPError as exc2:
                detail = exc2.read().decode("utf-8", errors="ignore")[:300]
        return {"ok": False, "error": f"{exc.code}: {detail}"}


def main() -> None:
    dry = "--dry-run" in sys.argv
    diff_path = os.environ.get("PR_DIFF_FILE", "pr.diff")
    diff_text = Path(diff_path).read_text(encoding="utf-8")

    report, comments = review_pr_diff(diff_text)
    # Always write the Markdown report for the CI artifact.
    Path("scout-review.md").write_text(report_to_markdown(report, "PR diff"), encoding="utf-8")

    if dry:
        print(json.dumps({
            "verdict": report.get("verdict"),
            "score": report.get("score"),
            "total_findings": len(report.get("recommendations", [])),
            "inline_comments": len(comments),
            "sample": comments[:3],
        }, indent=2))
        return

    repo_full = os.environ["GITHUB_REPOSITORY"]
    owner, repo = repo_full.split("/", 1)
    pr = int(os.environ.get("PR_NUMBER") or sys.argv[1])
    token = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]
    print(post_review(owner, repo, pr, report, comments, token))


if __name__ == "__main__":
    main()
