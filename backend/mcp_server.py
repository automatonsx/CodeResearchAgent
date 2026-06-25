"""Scout MCP server — exposes Scout's review pipeline as Claude-callable tools.

Tools:
  review_repo   — full review of a local path or GitHub URL → Markdown report
  review_pr     — review a GitHub PR URL (changed lines only) → Markdown report
  onboard_repo  — full pipeline: SKILL.md + scout-report.md + pre-commit hook

Transport: stdio (default) — Claude Code / Claude Desktop spawn this as a subprocess.

Usage (manual):
    python -m backend.mcp_server
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "scout",
    instructions=(
        "Scout is a research-aware AI code-review tool. "
        "Use review_repo to audit any repo, review_pr for pull-request diffs, "
        "and onboard_repo to write a SKILL.md, a full report, and a pre-commit hook "
        "directly into a repository."
    ),
)

_SCOUT_ROOT = Path(__file__).resolve().parent.parent


# ── helpers ───────────────────────────────────────────────────────────────────

def _input_type(source: str) -> str:
    if source.strip().lower().startswith(("https://", "http://", "git@")):
        if "/pull/" in source:
            return "pr_url"
        return "github"
    return "repo"


def _sev_summary(findings: list[dict]) -> str:
    by_sev: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "unknown")
        by_sev[s] = by_sev.get(s, 0) + 1
    if not by_sev:
        return "no findings"
    return "  ".join(f"{s}: {n}" for s, n in sorted(by_sev.items()))


def _install_hooks(repo_path: str, pre_push: bool = False) -> list[str]:
    hooks_script = _SCOUT_ROOT / "scripts" / "install_hooks.py"
    if not hooks_script.exists():
        return []
    cmd = [sys.executable, str(hooks_script), repo_path]
    if pre_push:
        cmd.append("--pre-push")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    installed = [str(Path(repo_path) / ".git" / "hooks" / "pre-commit")]
    if pre_push:
        installed.append(str(Path(repo_path) / ".git" / "hooks" / "pre-push"))
    return installed


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def review_repo(path_or_url: str) -> str:
    """Run Scout's full code-review pipeline on a local repo path or GitHub URL.

    Runs all agents (context → code-quality → security → architecture →
    test-review → grounding → critic → report) and returns a prioritised,
    cited Markdown report. Does NOT write any files — use onboard_repo for that.

    Args:
        path_or_url: Absolute local path (e.g. /home/user/myrepo) or GitHub
                     URL (e.g. https://github.com/owner/repo).
    """
    from backend.graph import run
    from backend.report_md import report_to_markdown

    itype = _input_type(path_or_url)
    report = run(source=path_or_url, input_type=itype)
    return report_to_markdown(report, path_or_url)


@mcp.tool()
def review_pr(pr_url: str) -> str:
    """Review a GitHub Pull Request — analyses only the changed lines in the diff.

    Returns a prioritised Markdown report with security, code-quality, and
    architecture findings, each grounded in tool evidence or web research.

    Args:
        pr_url: Full GitHub PR URL, e.g. https://github.com/owner/repo/pull/42
    """
    from backend.graph import run
    from backend.report_md import report_to_markdown

    report = run(source=pr_url, input_type="pr_url")
    return report_to_markdown(report, pr_url)


@mcp.tool()
def onboard_repo(
    path_or_url: str = ".",
    install_hooks: bool = True,
    install_pre_push: bool = False,
) -> str:
    """Fully onboard a repository with Scout.

    Runs all review agents, then writes three artefacts into the repo:

      1. <repo>/.claude/skills/code-standards/SKILL.md
         Project-specific DO/DON'T rules derived from actual findings.
         Claude Code auto-loads this on every session in the repo.

      2. <repo>/.claude/scout-report.md
         Full review report (findings, citations, analysis quality grade).

      3. <repo>/.git/hooks/pre-commit  (unless install_hooks=False)
         Deterministic hook — no LLM, <1 s — blocks CRITICAL issues at commit time.

    Source files (.py, .js, .java, …) are NEVER modified — only the above
    three paths are written.

    Args:
        path_or_url:      Absolute local path or GitHub URL. Defaults to "." which
                          means the repository the user currently has open in Claude Code.
                          Use the workspace root path from context if known.
        install_hooks:    Write the pre-commit hook (default True).
        install_pre_push: Also write the pre-push hook (default False).
    """
    from backend.graph import run_standards

    itype = _input_type(path_or_url)
    result = run_standards(source=path_or_url, input_type=itype, output_dir=None)

    review_path   = result.get("review_path", "")
    skill_path    = result.get("skill_saved_to", "")
    report_path   = result.get("report_saved_to", "")
    final_report  = result.get("final_report", {})
    standards     = result.get("standards", {})

    # ── install hooks ─────────────────────────────────────────────────────────
    hooks_installed: list[str] = []
    hook_error = ""
    if install_hooks and review_path:
        hooks_installed = _install_hooks(review_path, pre_push=install_pre_push)
        if not hooks_installed:
            hook_error = " (hook installation failed — run scripts/install_hooks.py manually)"

    # ── build summary ─────────────────────────────────────────────────────────
    stats    = final_report.get("stats", {})
    findings = final_report.get("recommendations", [])
    rules    = standards.get("rules", {})
    n_rules  = sum(len(v) for v in rules.values() if isinstance(v, list))

    lines = [
        "## Scout Onboarding Complete",
        "",
        f"**Repository:** `{review_path}`",
        f"**Findings:** {len(findings)}  —  {_sev_summary(findings)}",
        f"**Score:** {final_report.get('score', 'n/a')}/10  |  "
        f"**Grade:** {stats.get('grade', '?')}  |  "
        f"**Verdict:** {final_report.get('verdict', '?')}",
        f"**Standards extracted:** {n_rules} project-specific rules",
        "",
        "### Artefacts Written",
    ]

    if skill_path:
        lines.append(f"- **SKILL.md** → `{skill_path}`")
        lines.append("  _Auto-loaded by Claude Code on every session in this repo_")
    else:
        lines.append("- **SKILL.md** → _(not written — check stderr)_")

    if report_path:
        lines.append(f"- **scout-report.md** → `{report_path}`")
        lines.append("  _Full findings with citations and analysis quality grade_")
    else:
        lines.append("- **scout-report.md** → _(not written — check stderr)_")

    if install_hooks:
        for h in hooks_installed:
            lines.append(f"- **pre-commit hook** → `{h}`")
            lines.append("  _Blocks CRITICAL issues on every `git commit` — no LLM, <1 s_")
        if hook_error:
            lines.append(f"- **pre-commit hook** → _{hook_error}_")
        if install_pre_push and hooks_installed:
            lines.append(f"- **pre-push hook** → `{str(Path(review_path) / '.git' / 'hooks' / 'pre-push')}`")

    lines += [
        "",
        "### Next Steps",
        "",
        f"1. Commit the Scout artefacts so every developer gets them automatically:",
        f"   ```bash",
        f"   cd {review_path}",
        f"   git add .claude/",
        f"   git commit -m 'chore: add Scout coding standards and review report'",
        f"   ```",
        "",
        "2. Each developer installs the hook on their own checkout:",
        f"   ```bash",
        f"   python {_SCOUT_ROOT / 'scripts' / 'install_hooks.py'} {review_path}",
        f"   ```",
        "",
        "3. Re-run Scout any time to refresh standards and the report:",
        f"   Call `onboard_repo` again with the same path.",
    ]

    return "\n".join(lines)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
