"""Shared LangGraph state for the Scout research-aware code-review engine.

The graph: Context -> Code-Quality -> Security -> Grounding -> Critic (loop) -> Report.
The LLM proposes; tools (ruff/semgrep/ast) and the Critic verify.
"""

from __future__ import annotations

from typing import TypedDict


class ReviewState(TypedDict, total=False):
    input_type: str            # "pr_diff" | "repo"
    source: str                # diff text or repo path
    context: dict              # {language, files, entry_points, changed_lines}
    tool_findings: list        # raw ground-truth from ruff/semgrep/ast
    findings: list             # structured findings (see schema below)
    citations: list            # corpus matches attached per finding
    critique: dict             # {dropped, low_confidence, needs_recheck, notes}
    iterations: int            # loop guard (max 2)
    final_report: dict         # {summary, recommendations, verdict, score}
    agents_executed: list      # ordered list of agent names that ran successfully
    standards: dict            # extracted coding standards (from standards_node)


MAX_ITERATIONS = 2

# Severity ordering for prioritization / scoring.
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "suggestion": 3}


def initial_state(source: str, input_type: str = "repo") -> ReviewState:
    """Build a fresh state for a new review run.

    input_type: "repo" (source = folder path) or "pr_diff" (source = diff text).
    """
    return ReviewState(
        input_type=input_type,
        source=source,
        context={},
        tool_findings=[],
        findings=[],
        citations=[],
        critique={"dropped": [], "low_confidence": [], "needs_recheck": False, "notes": []},
        iterations=0,
        final_report={},
        agents_executed=[],
    )
