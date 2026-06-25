"""LangGraph wiring for Scout (research-aware code review).

  Context -> Code-Quality -> Security -> Architecture -> Test-Review
          -> Grounding -> Critic --(recheck)--> Code-Quality
                              \--(validated)--> Report -> END

The Critic -> re-check loop is the agentic twist; capped at MAX_ITERATIONS (state.py).
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from .state import ReviewState, initial_state
from .agents import (
    context_node,
    code_quality_node,
    security_node,
    architecture_node,
    test_review_node,
    grounding_node,
    critic_node,
    critic_router,
    report_node,
)


_SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".go", ".rb", ".php", ".cs",
    ".c", ".h", ".cpp", ".cc", ".hpp", ".rs", ".swift",
    ".sh", ".bash", ".sql",
}


def _dirty_source_files(review_path: str) -> set[str]:
    """Return the set of source files with uncommitted changes in *review_path*.

    Returns an empty set if review_path has no .git, git is unavailable, or the
    command times out.
    """
    import subprocess
    from pathlib import Path

    if not review_path:
        return set()
    root = Path(review_path)
    if not (root / ".git").exists():
        return set()
    try:
        result = subprocess.run(
            ["git", "-C", review_path, "diff", "--name-only"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {
        f.strip() for f in result.stdout.splitlines()
        if any(f.strip().endswith(ext) for ext in _SOURCE_EXTENSIONS)
    }


def _assert_repo_unmodified(review_path: str, pre_run: set[str] | None = None) -> None:
    """Raise RuntimeError only if Scout itself modified source files during the run.

    Compares the dirty-file set before and after the pipeline. Files that were
    already modified before Scout ran (pre-existing uncommitted changes) are
    excluded — only *new* modifications introduced by the pipeline are flagged.

    Only active when review_path has its own .git directory.
    """
    post_run = _dirty_source_files(review_path)
    new_modifications = post_run - (pre_run or set())
    if new_modifications:
        raise RuntimeError(
            "[Scout] READ-ONLY VIOLATION — the analysis pipeline modified source "
            f"file(s) in {review_path}:\n  " + "\n  ".join(sorted(new_modifications))
        )


def _track(name: str, node_fn):
    """Wrap a node so its name is appended to agents_executed on success."""
    def _wrapped(state: ReviewState) -> ReviewState:
        result = node_fn(state)
        executed = list(state.get("agents_executed", []))
        if name not in executed:
            executed.append(name)
        return {**(result or {}), "agents_executed": executed}
    _wrapped.__name__ = name
    return _wrapped


def _count_iteration(state: ReviewState) -> ReviewState:
    """Increment the loop guard before each re-check pass."""
    return {"iterations": state.get("iterations", 0) + 1}


def build_graph():
    """Construct and compile the Scout review graph."""
    g = StateGraph(ReviewState)

    g.add_node("context",      _track("context",      context_node))
    g.add_node("code_quality", _track("code_quality", code_quality_node))
    g.add_node("security",     _track("security",     security_node))
    g.add_node("architecture", _track("architecture", architecture_node))
    g.add_node("test_review",  _track("test_review",  test_review_node))
    g.add_node("grounding",    _track("grounding",    grounding_node))
    g.add_node("critic",       _track("critic",       critic_node))
    g.add_node("recheck", _count_iteration)
    g.add_node("report",       _track("report",       report_node))

    g.add_edge(START, "context")
    g.add_edge("context", "code_quality")
    g.add_edge("code_quality", "security")
    g.add_edge("security", "architecture")
    g.add_edge("architecture", "test_review")
    g.add_edge("test_review", "grounding")
    g.add_edge("grounding", "critic")

    # Conditional Critic loop: re-check flagged findings, or finalize the report.
    g.add_conditional_edges(
        "critic",
        critic_router,
        {"recheck": "recheck", "report": "report"},
    )
    g.add_edge("recheck", "code_quality")
    g.add_edge("report", END)

    return g.compile()


def run(source: str, input_type: str = "repo") -> dict:
    """Run the full review graph synchronously and return the final report.

    The pipeline is READ-ONLY on the target repo — no source files are modified.
    """
    import os
    from pathlib import Path
    # Snapshot dirty files before the pipeline so pre-existing uncommitted changes
    # are not misattributed to Scout.
    pre_run_path = str(Path(source).resolve()) if os.path.isdir(source) else ""
    pre_run = _dirty_source_files(pre_run_path)

    graph = build_graph()
    final = graph.invoke(initial_state(source, input_type), {"recursion_limit": 50})
    review_path = final.get("context", {}).get("review_path", "")
    _assert_repo_unmodified(review_path, pre_run=pre_run)
    return final.get("final_report", {})


def run_standards(
    source: str,
    input_type: str = "repo",
    output_dir: str | None = None,
) -> dict:
    """Run the full pipeline + extract coding standards → save SKILL.md.

    The analysis pipeline is READ-ONLY on the target repo — no source files are
    modified.  SKILL.md is written to *output_dir* (Scout's own output/ folder by
    default) so the target repo is never touched.  The developer manually copies
    the generated SKILL.md into their repo when they are ready.

    Returns a dict with:
      final_report   — the normal Scout review report
      standards      — the extracted standards object
      skill_saved_to — absolute path of the generated SKILL.md (in output_dir)
      review_path    — local path of the repo that was analyzed (read-only)
    """
    import os
    from pathlib import Path
    from .agents.standards import standards_node
    from .standards_skill import save_skill

    # Snapshot dirty files before the pipeline so pre-existing uncommitted changes
    # in the target repo are not misattributed to Scout.
    pre_run_path = str(Path(source).resolve()) if os.path.isdir(source) else ""
    pre_run = _dirty_source_files(pre_run_path)

    graph = build_graph()
    final = graph.invoke(initial_state(source, input_type), {"recursion_limit": 50})

    # ── Read-only integrity guard ─────────────────────────────────────────────
    # Only fails if Scout itself modified source files — pre-existing uncommitted
    # changes in the repo are excluded via the pre_run snapshot.
    review_path = final.get("context", {}).get("review_path", "")
    _assert_repo_unmodified(review_path, pre_run=pre_run)

    std_update = standards_node(final)
    standards = std_update.get("standards", {})

    # Derive a clean repo name from the source URL/path.
    repo_name = (
        os.path.basename(source.rstrip("/\\").rstrip(".git"))
        or os.path.basename(review_path.rstrip("/\\"))
        or "repo"
    )

    # SKILL.md goes into the target repo under .claude/skills/code-standards/
    # so Claude Code discovers it automatically on every session in that repo.
    # Callers can override with output_dir for custom placement.
    dest = output_dir or review_path or (source if os.path.isdir(source) else ".")

    skill_path = save_skill(
        standards,
        repo_name=repo_name,
        output_dir=dest,
        source_path=source,
    )

    # Save the full review report into <repo>/.claude/scout-report.md so it lives
    # alongside SKILL.md and is committed with the repo.
    from .report_md import save_report_to_dir
    report_path = save_report_to_dir(
        final.get("final_report", {}),
        dest_dir=str(Path(dest) / ".claude"),
        source=source,
    )

    return {
        "final_report": final.get("final_report", {}),
        "standards": standards,
        "skill_saved_to": skill_path,
        "report_saved_to": report_path,
        "review_path": dest,
    }


if __name__ == "__main__":
    import json
    import sys

    src   = sys.argv[1] if len(sys.argv) > 1 else "data/sample_repo"
    itype = sys.argv[2] if len(sys.argv) > 2 else "repo"

    if "--standards" in sys.argv:
        result = run_standards(src, itype)
        print(json.dumps(result["standards"], indent=2))
        print(f"\nSKILL.md saved to: {result['skill_saved_to']}")
        if "--install-hooks" in sys.argv:
            import subprocess as _sp
            hook_target = result.get("review_path") or src
            _sp.run([sys.executable, "scripts/install_hooks.py", hook_target], check=False)
        if "--save" in sys.argv:
            from .report_md import save_report
            print(f"Report saved to: {save_report(result['final_report'], src)}")
    else:
        report = run(src, itype)
        print(json.dumps(report, indent=2))
        if "--save" in sys.argv:
            from .report_md import save_report
            print(f"\nSaved Markdown report to: {save_report(report, src)}")
