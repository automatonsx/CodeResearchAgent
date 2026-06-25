"""LangGraph wiring for Scout (research-aware code review).

  Context -> Code-Quality -> Security -> Grounding -> Critic --(recheck)--> Code-Quality
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
    grounding_node,
    critic_node,
    critic_router,
    report_node,
)


def _count_iteration(state: ReviewState) -> ReviewState:
    """Increment the loop guard before each re-check pass."""
    return {"iterations": state.get("iterations", 0) + 1}


def build_graph():
    """Construct and compile the Scout review graph."""
    g = StateGraph(ReviewState)

    g.add_node("context", context_node)
    g.add_node("code_quality", code_quality_node)
    g.add_node("security", security_node)
    g.add_node("architecture", architecture_node)   # KB-grounded design review
    g.add_node("grounding", grounding_node)
    g.add_node("critic", critic_node)
    g.add_node("recheck", _count_iteration)   # increments the loop guard
    g.add_node("report", report_node)

    g.add_edge(START, "context")
    g.add_edge("context", "code_quality")
    g.add_edge("code_quality", "security")
    g.add_edge("security", "architecture")
    g.add_edge("architecture", "grounding")
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
    """Run the full review graph synchronously and return the final report."""
    graph = build_graph()
    final = graph.invoke(initial_state(source, input_type), {"recursion_limit": 50})
    return final.get("final_report", {})


if __name__ == "__main__":
    import json
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "data/sample_repo"
    itype = sys.argv[2] if len(sys.argv) > 2 else "repo"
    report = run(src, itype)
    print(json.dumps(report, indent=2))
    if "--save" in sys.argv:
        from .report_md import save_report

        print(f"\nSaved Markdown report to: {save_report(report, src)}")
