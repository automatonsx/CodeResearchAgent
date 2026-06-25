"""Scout CLI — `scout setup` installs Scout as a global MCP tool in Claude Code.

After running `pip install git+https://github.com/<you>/scout` once:

    scout setup          # stores API keys, registers MCP globally, builds corpus
    scout onboard        # onboard the current repo (SKILL.md + report + hook)
    scout review         # review the current repo, print report, write nothing
    scout onboard <path> # onboard a specific local path or GitHub URL
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_SCOUT_ROOT = Path(__file__).resolve().parent.parent
_SCOUT_ENV  = Path.home() / ".scout" / ".env"
_CLAUDE_JSON = Path.home() / ".claude.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    full_prompt = f"  {prompt}{suffix}: "
    if secret:
        import getpass
        val = getpass.getpass(full_prompt)
    else:
        val = input(full_prompt).strip()
    return val.strip() or default


def _ok(msg: str)   -> None: print(f"  \033[32m✓\033[0m {msg}")
def _warn(msg: str) -> None: print(f"  \033[33m!\033[0m {msg}")
def _err(msg: str)  -> None: print(f"  \033[31m✗\033[0m {msg}", file=sys.stderr)


# ── scout setup ───────────────────────────────────────────────────────────────

def cmd_setup(_args) -> None:
    """Store API keys, register Scout MCP globally, build the corpus."""
    print("\n\033[1mScout — one-time setup\033[0m")
    print("─" * 50)

    # ── 1. Collect credentials ────────────────────────────────────────────────
    print("\nAzure OpenAI credentials (required):")
    api_key    = _ask("AZURE_OPENAI_API_KEY", secret=True)
    endpoint   = _ask("AZURE_OPENAI_ENDPOINT", "https://YOUR-RESOURCE.openai.azure.com/")
    deployment = _ask("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    model      = _ask("AZURE_OPENAI_MODEL", deployment)
    api_ver    = _ask("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    print("\nOptional (press Enter to skip):")
    tavily = _ask("TAVILY_API_KEY (better web research in Architecture agent)", "")

    if not api_key or "YOUR-RESOURCE" in endpoint:
        _err("API key and endpoint are required. Aborting.")
        sys.exit(1)

    # ── 2. Save to ~/.scout/.env ──────────────────────────────────────────────
    _SCOUT_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"AZURE_OPENAI_API_KEY={api_key}",
        f"AZURE_OPENAI_ENDPOINT={endpoint}",
        f"AZURE_OPENAI_DEPLOYMENT={deployment}",
        f"AZURE_OPENAI_MODEL={model}",
        f"AZURE_OPENAI_API_VERSION={api_ver}",
    ]
    if tavily:
        lines.append(f"TAVILY_API_KEY={tavily}")
    _SCOUT_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ok(f"Credentials saved → {_SCOUT_ENV}")

    # ── 3. Register MCP in ~/.claude.json (user-level, all repos) ────────────
    cfg: dict = {}
    if _CLAUDE_JSON.exists():
        try:
            cfg = json.loads(_CLAUDE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    cfg.setdefault("mcpServers", {})
    cfg["mcpServers"]["scout"] = {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "backend.mcp_server"],
        "cwd": str(_SCOUT_ROOT),
        # Pass the global env file path so llm.py can load it from anywhere.
        "env": {"SCOUT_ENV": str(_SCOUT_ENV)},
    }
    _CLAUDE_JSON.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    _ok(f"Scout MCP registered globally → {_CLAUDE_JSON}")
    print("     \033[2m(active in every Claude Code session, any repo)\033[0m")

    # ── 4. Build ChromaDB corpus ──────────────────────────────────────────────
    print("\n  Building best-practices corpus (ChromaDB) …", end=" ", flush=True)
    r = subprocess.run(
        [sys.executable, "-m", "backend.corpus.build_index"],
        cwd=str(_SCOUT_ROOT),
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        print("\033[32m✓\033[0m")
    else:
        print("\033[33m⚠\033[0m")
        _warn("Corpus build failed — grounding falls back to keyword search.")
        if r.stderr.strip():
            print(f"     {r.stderr.strip()[:200]}")

    # ── 5. Done ───────────────────────────────────────────────────────────────
    print()
    print("─" * 50)
    print("\033[1mScout is ready.\033[0m")
    print()
    print("Open Claude Code in any repo and say:")
    print('  \033[36m"Scout, onboard this repo"\033[0m')
    print()
    print("Claude will run the full review and write into your repo:")
    print("  .claude/skills/code-standards/SKILL.md  ← auto-loaded by Claude Code")
    print("  .claude/scout-report.md                  ← full findings + citations")
    print("  .git/hooks/pre-commit                    ← blocks CRITICAL on every commit")
    print()
    print("Or from the terminal:")
    print(f"  scout onboard              # current directory")
    print(f"  scout onboard /path/to/repo")
    print(f"  scout onboard https://github.com/owner/repo")
    print()


# ── scout onboard ─────────────────────────────────────────────────────────────

def cmd_onboard(args) -> None:
    """Run the full pipeline on a path/URL and write SKILL.md + report + hook."""
    _load_env()
    from backend.graph import run_standards
    from backend.hooks.installer import install as install_hooks

    target = args.target or "."
    is_github = target.startswith(("https://", "http://", "git@"))
    itype = "github" if is_github else "repo"

    print(f"\n\033[1mScout — Onboarding\033[0m  {target}")
    print("─" * 50)

    result = run_standards(source=target, input_type=itype, output_dir=None)

    repo_path     = result.get("review_path", "")
    skill_path    = result.get("skill_saved_to", "")
    report_path   = result.get("report_saved_to", "")
    final_report  = result.get("final_report", {})
    findings      = final_report.get("recommendations", [])

    by_sev: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "?")
        by_sev[s] = by_sev.get(s, 0) + 1

    print(f"\n  Findings : {len(findings)}  —  " +
          "  ".join(f"{s}: {n}" for s, n in sorted(by_sev.items())))
    print(f"  Score    : {final_report.get('score', 'n/a')}/10  |  "
          f"Grade: {final_report.get('stats', {}).get('grade', '?')}")
    print()

    if skill_path:
        _ok(f"SKILL.md        → {skill_path}")
    if report_path:
        _ok(f"scout-report.md → {report_path}")

    if not args.skip_hooks and repo_path:
        installed = install_hooks(repo_path)
        if installed:
            _ok(f"pre-commit hook → {installed[0]}")
        else:
            _warn("Hook install failed — run: scout install-hooks")

    print()
    print("Commit these artefacts so the whole team gets them:")
    if repo_path:
        print(f"  cd {repo_path}")
    print("  git add .claude/")
    print("  git commit -m 'chore: add Scout coding standards and review report'")
    print()


# ── scout review ──────────────────────────────────────────────────────────────

def cmd_review(args) -> None:
    """Run review only — print report, write nothing."""
    _load_env()
    from backend.graph import run
    from backend.report_md import report_to_markdown, save_report

    target = args.target or "."
    is_github = target.startswith(("https://", "http://", "git@"))
    itype = "github" if is_github else "repo"

    print(f"\n\033[1mScout — Review\033[0m  {target}\n")
    report = run(source=target, input_type=itype)
    md = report_to_markdown(report, target)
    print(md)

    if args.save:
        path = save_report(report, target)
        _ok(f"Report saved → {path}")


# ── scout install-hooks ────────────────────────────────────────────────────────

def cmd_install_hooks(args) -> None:
    """Install pre-commit (and optionally pre-push) hook into a repo."""
    from backend.hooks.installer import install as install_hooks
    target = args.target or "."
    installed = install_hooks(target, pre_push=args.pre_push)
    for path in installed:
        _ok(f"hook → {path}")
    if not installed:
        _err("Could not install hooks — is the target a git repository?")


# ── env loader ────────────────────────────────────────────────────────────────

def _load_env() -> None:
    """Load credentials: local .env first, then ~/.scout/.env as fallback."""
    from dotenv import load_dotenv
    local = Path(".env")
    if local.exists():
        load_dotenv(local)
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        scout_env = os.environ.get("SCOUT_ENV") or str(_SCOUT_ENV)
        if Path(scout_env).exists():
            load_dotenv(scout_env)
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        _err("No Azure OpenAI credentials found. Run: scout setup")
        sys.exit(1)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scout",
        description="Scout — research-aware AI code review",
    )
    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Store API keys and register Scout MCP globally")

    # onboard
    p_on = sub.add_parser("onboard", help="Full onboarding: SKILL.md + report + hook")
    p_on.add_argument("target", nargs="?", default=".",
                      help="Local path or GitHub URL (default: current directory)")
    p_on.add_argument("--skip-hooks", action="store_true",
                      help="Write SKILL.md and report but do not install hooks")

    # review
    p_rev = sub.add_parser("review", help="Review only — print report, write nothing")
    p_rev.add_argument("target", nargs="?", default=".",
                       help="Local path or GitHub URL (default: current directory)")
    p_rev.add_argument("--save", action="store_true",
                       help="Also save the report to reports/")

    # install-hooks
    p_hooks = sub.add_parser("install-hooks", help="Install pre-commit hook into a repo")
    p_hooks.add_argument("target", nargs="?", default=".",
                         help="Repo path (default: current directory)")
    p_hooks.add_argument("--pre-push", action="store_true",
                         help="Also install the pre-push hook")

    args = parser.parse_args()

    dispatch = {
        "setup":         cmd_setup,
        "onboard":       cmd_onboard,
        "review":        cmd_review,
        "install-hooks": cmd_install_hooks,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(0)
    fn(args)


if __name__ == "__main__":
    main()
