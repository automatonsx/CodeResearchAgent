"""Scout — one-command repo onboarding.

Usage:
    python scripts/onboard_repo.py <github-url-or-local-path> [options]

What it does, in order:
  1. Clones the repo (or uses an existing local path)
  2. Runs all Scout agents (context → code-quality → security → architecture
     → test-review → grounding → critic → report)
  3. Extracts project-specific coding standards from the findings
  4. Generates a SKILL.md in <repo>/.claude/skills/code-standards/
  5. Installs pre-commit (and optionally pre-push) git hooks into the repo
  6. Prints a summary of every artefact produced

Options:
    --output-dir <path>   Clone GitHub repos here instead of ./repos/<name>
    --pre-push            Also install the pre-push hook
    --skip-hooks          Generate SKILL.md but do not install hooks
    --save-report         Save the Markdown review report alongside SKILL.md
    --dry-run             Show what would happen without writing anything
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import textwrap
from pathlib import Path

# Ensure Unicode output works on Windows terminals (cp1252 can't print ✓, →, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── project root on sys.path ───────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── ANSI helpers ───────────────────────────────────────────────────────────────
def _c(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"

def green(t: str) -> str:  return _c(t, "32")
def yellow(t: str) -> str: return _c(t, "33")
def cyan(t: str) -> str:   return _c(t, "36")
def bold(t: str) -> str:   return _c(t, "1")
def dim(t: str) -> str:    return _c(t, "2")


# ── step printer ───────────────────────────────────────────────────────────────
def _step(n: int, total: int, msg: str) -> None:
    prefix = bold(f"[{n}/{total}]")
    print(f"\n{prefix} {msg}")


# ── git clone ──────────────────────────────────────────────────────────────────
def _is_github_url(source: str) -> bool:
    return source.startswith(("https://github.com", "git@github.com", "http://github.com"))


def _clone(url: str, output_dir: str | None, dry_run: bool) -> str:
    """Shallow-clone *url* and return the local path."""
    import subprocess

    name = url.rstrip("/").rstrip(".git").split("/")[-1]
    dest = output_dir or str(Path("repos") / name)
    dest = str(Path(dest).resolve())

    if Path(dest).exists():
        print(f"  {yellow('!')} {dest} already exists — using existing checkout")
        return dest

    print(f"  Cloning into {cyan(dest)} …")
    if dry_run:
        print(f"  {dim('(dry-run: skipped)')}")
        return dest

    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, dest],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  {_c('git clone failed', '31')}")
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    return dest


# ── install hooks ──────────────────────────────────────────────────────────────
def _install_hooks(repo_path: str, pre_push: bool, dry_run: bool) -> list[str]:
    """Run install_hooks.py targeting *repo_path*. Returns list of installed paths."""
    import subprocess

    hooks_script = str(_REPO_ROOT / "scripts" / "install_hooks.py")
    if not Path(hooks_script).exists():
        print(f"  {yellow('!')} install_hooks.py not found — skipping hook installation")
        return []

    label = "pre-commit + pre-push hooks" if pre_push else "pre-commit hook"
    print(f"  Installing {label} …", end=" ", flush=True)

    if dry_run:
        print(dim("(dry-run: skipped)"))
        installed = [str(Path(repo_path) / ".git" / "hooks" / "pre-commit")]
        if pre_push:
            installed.append(str(Path(repo_path) / ".git" / "hooks" / "pre-push"))
        return installed

    cmd = [sys.executable, hooks_script, repo_path]
    if pre_push:
        cmd.append("--pre-push")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(green("✓"))
        installed = [str(Path(repo_path) / ".git" / "hooks" / "pre-commit")]
        if pre_push:
            installed.append(str(Path(repo_path) / ".git" / "hooks" / "pre-push"))
    else:
        print(yellow("⚠ (non-fatal)"))
        if result.stderr:
            print(f"    {dim(result.stderr.strip())}", file=sys.stderr)
        installed = []

    return installed


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scout: one-command repo onboarding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/onboard_repo.py https://github.com/owner/repo
              python scripts/onboard_repo.py /path/to/local/checkout --skip-hooks
              python scripts/onboard_repo.py https://github.com/org/svc --output-dir ~/projects/svc
        """),
    )
    parser.add_argument("source", help="GitHub URL or local repo path")
    parser.add_argument("--output-dir", metavar="PATH",
                        help="Where to clone the repo (default: ./repos/<name>)")
    parser.add_argument("--pre-push", action="store_true",
                        help="Also install the pre-push hook")
    parser.add_argument("--skip-hooks", action="store_true",
                        help="Generate SKILL.md but do not install git hooks")
    parser.add_argument("--save-report", action="store_true",
                        help="Save the Markdown review report next to SKILL.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without writing anything")
    args = parser.parse_args()

    source = args.source
    dry_run = args.dry_run
    is_github = _is_github_url(source)

    STEPS = 5 if not args.skip_hooks else 4
    print()
    print(bold("Scout — Repository Onboarding"))
    print(dim(f"  source  : {source}"))
    print(dim(f"  dry-run : {dry_run}"))

    # ── 1. Resolve local path ─────────────────────────────────────────────────
    _step(1, STEPS, "Resolving repository")
    if is_github:
        repo_path = _clone(source, args.output_dir, dry_run)
        input_type = "github"
    else:
        repo_path = str(Path(source).resolve())
        if not Path(repo_path).is_dir():
            print(f"  {_c('Error', '31')}: path not found: {repo_path}", file=sys.stderr)
            sys.exit(1)
        input_type = "repo"
        print(f"  Using local path: {cyan(repo_path)}")

    # ── 2. Run all Scout agents ───────────────────────────────────────────────
    _step(2, STEPS, "Running Scout review pipeline (this may take a minute) …")

    if dry_run:
        print(f"  {dim('(dry-run: skipping pipeline)')}")
        result = {
            "final_report": {"summary": "dry-run", "score": 0},
            "standards": {"rules": {}, "tooling": {}},
            "skill_saved_to": str(Path(repo_path) / ".claude" / "skills" / "code-standards" / "SKILL.md"),
            "review_path": repo_path,
        }
    else:
        from backend.graph import run_standards
        # SKILL.md is written into <repo>/.claude/skills/code-standards/ so Claude Code
        # discovers it automatically.  Source files are never modified (guard enforced).
        result = run_standards(
            source=repo_path,
            input_type=input_type,
            output_dir=repo_path,
        )

    skill_path = result.get("skill_saved_to", "")
    standards = result.get("standards", {})
    final_report = result.get("final_report", {})

    # Count findings for summary
    findings = final_report.get("findings", []) or final_report.get("recommendations", [])
    by_sev: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "unknown")
        by_sev[sev] = by_sev.get(sev, 0) + 1

    agents_exec = final_report.get("stats", {}).get("agents_executed", [])
    print(f"  {green('✓')} Pipeline complete — {len(findings)} findings across {len(agents_exec)} agents")
    if by_sev:
        sev_str = "  ".join(f"{s}: {n}" for s, n in sorted(by_sev.items()))
        print(f"    {dim(sev_str)}")

    # ── 3. SKILL.md written into repo ────────────────────────────────────────
    _step(3, STEPS, "Coding standards extracted")
    rules = standards.get("rules", {})
    n_rules = sum(len(v) for v in rules.values() if isinstance(v, list))
    print(f"  {green('✓')} {n_rules} project-specific rules extracted")
    if skill_path:
        rel = os.path.relpath(skill_path, repo_path) if os.path.isabs(skill_path) else skill_path
        print(f"  {green('✓')} SKILL.md → {cyan(rel)}")
        print(f"  {dim('     Claude Code will auto-load this on every session in the repo')}")
    else:
        print(f"  {yellow('!')} SKILL.md was not saved (check stderr for errors)")

    # ── 3b. Optional Markdown report ─────────────────────────────────────────
    report_path = ""
    if args.save_report and not dry_run:
        try:
            from backend.report_md import save_report
            report_path = save_report(final_report, repo_path)
            rel = os.path.relpath(report_path, repo_path)
            print(f"  {green('✓')} Markdown report → {cyan(rel)}")
        except Exception as exc:
            print(f"  {yellow('!')} Could not save report: {exc}")

    # ── 4. Hook installation ──────────────────────────────────────────────────
    installed_hooks: list[str] = []
    if not args.skip_hooks:
        _step(4, STEPS, "Installing git hooks")
        installed_hooks = _install_hooks(repo_path, pre_push=args.pre_push, dry_run=dry_run)
        if installed_hooks:
            print(f"  {dim('     Hook fires on every git commit — no LLM, < 1 second')}")
            print(f"  {dim('     Blocks CRITICAL issues; warns on MAJOR')}")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    _step(STEPS, STEPS, "Done")
    print()
    print(bold("─" * 60))
    print(bold("Scout Onboarding Summary"))
    print(bold("─" * 60))
    print(f"  Repository  : {cyan(repo_path)}")
    if skill_path:
        rel = os.path.relpath(skill_path, repo_path) if os.path.isabs(skill_path) else skill_path
        print(f"  SKILL.md    : {green(rel)}")
    if report_path:
        rel = os.path.relpath(report_path, repo_path)
        print(f"  Report      : {green(rel)}")
    if installed_hooks:
        for h in installed_hooks:
            rel = os.path.relpath(h, repo_path) if os.path.isabs(h) else h
            print(f"  Hook        : {green(rel)}")
    print()

    grade = final_report.get("stats", {}).get("grade", "")
    score = final_report.get("score", "")
    if grade:
        print(f"  Analysis grade : {bold(grade)}")
    if score:
        print(f"  Review score   : {bold(str(score))}")

    print()
    print(bold("Next steps:"))
    print()
    if skill_path:
        skill_rel = os.path.relpath(skill_path, repo_path) if os.path.isabs(skill_path) else skill_path
        print(f"  1. Commit the SKILL.md so every developer gets it automatically:")
        print(f"       cd {dim(repo_path)}")
        print(f"       git add {dim(skill_rel)}")
        print(f"       git commit -m 'chore: add Scout coding standards skill'")
        print()
    print(f"  2. Each developer installs hooks on their own checkout:")
    print(f"       python scripts/install_hooks.py {dim(repo_path)}")
    print()
    print(f"  3. Re-run Scout any time to refresh standards:")
    print(f"       python scripts/onboard_repo.py {dim(source)}")
    print()

    if dry_run:
        print(yellow("  (dry-run: no files were actually written)"))
        print()


if __name__ == "__main__":
    main()
