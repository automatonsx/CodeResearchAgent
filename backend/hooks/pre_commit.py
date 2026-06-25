"""Scout pre-commit hook — fast tool-only check, no LLM, runs in <1 second.

Blocks commits that introduce CRITICAL security issues.
Warns (non-blocking) on MAJOR issues.

Install via:
    python scripts/install_hooks.py               # current repo
    python scripts/install_hooks.py /path/to/repo # another repo
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _staged_files() -> list[str]:
    """Return absolute paths of staged, non-deleted files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [str(Path(f).resolve()) for f in result.stdout.splitlines() if f.strip()]


def _print_issue(i: dict, color: str) -> None:
    p = Path(i.get("file", "unknown"))
    code = i.get("code") or i.get("tool_evidence") or "?"
    msg = i.get("message", "")
    print(f"  {color}{p.name}:{i.get('line', '?')}  [{code}]  {msg}\033[0m")


def main() -> int:
    staged = _staged_files()
    if not staged:
        return 0

    try:
        from backend.tools.ruff_runner import run_ruff
        from backend.tools.generic_scan import generic_scan
    except ImportError:
        print(
            "[Scout hook] Scout is not on sys.path — skipping pre-commit check.\n"
            "  Set PYTHONPATH or install Scout to activate the hook.",
            file=sys.stderr,
        )
        return 0  # don't block commits when Scout isn't set up

    py_files = [f for f in staged if f.endswith(".py")]
    all_issues: list[dict] = []
    if py_files:
        # S = security/bandit, E722 = bare except, B006 = mutable default, F841 = unused var
        all_issues += run_ruff(py_files, select="S,E722,B006,F841")
    all_issues += generic_scan(staged)

    critical = [i for i in all_issues if i.get("severity") == "critical"]
    major    = [i for i in all_issues if i.get("severity") == "major"]

    if major:
        print("\n\033[33m⚠  Scout: major issues detected (non-blocking)\033[0m")
        for i in major[:5]:
            _print_issue(i, "\033[33m")
        if len(major) > 5:
            print(f"\033[33m  … and {len(major) - 5} more. Run: python -m evals.score\033[0m")
        print()

    if critical:
        print("\n\033[31m🚫  Scout pre-commit: CRITICAL issues — commit blocked\033[0m")
        for i in critical:
            _print_issue(i, "\033[31m")
        print(
            "\n\033[31m  Fix these issues before committing.\033[0m\n"
            "  Bypass (use sparingly): git commit --no-verify"
        )
        return 1

    total = len(all_issues)
    if total:
        print(f"\033[32m✓  Scout: {total} issue(s) noted (none critical) — commit allowed\033[0m")

    return 0


if __name__ == "__main__":
    sys.exit(main())
