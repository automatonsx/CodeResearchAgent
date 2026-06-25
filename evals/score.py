"""Planted-issue evaluation for Scout.

Runs the review pipeline on a labelled target and reports:
  - RECALL  — how many planted issues we caught
  - The CRITIC ABLATION — findings before vs. after the Critic (its precision effect)

Run from the repo root:
    python -m evals.score
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.state import initial_state
from backend.agents import (
    context_node, code_quality_node, security_node,
    architecture_node, test_review_node,
    grounding_node, critic_node,
)

_ROOT = Path(__file__).resolve().parent.parent


def _basename(p: str) -> str:
    return p.replace("\\", "/").split("/")[-1]


def _matches(finding: dict, label: dict) -> bool:
    return (_basename(finding.get("file", "")) == label["file"]
            and abs(int(finding.get("line", 0)) - label["line"]) <= 2)


def _run_pipeline(target: str, input_type: str):
    """Single pass (no loop) so we can inspect findings before/after the Critic."""
    s = initial_state(target, input_type)
    s.update(context_node(s))
    s.update(code_quality_node(s))
    s.update(security_node(s))
    s.update(architecture_node(s))
    s.update(test_review_node(s))
    s.update(grounding_node(s))
    pre = list(s.get("findings", []))
    s.update(critic_node(s))
    post = list(s.get("findings", []))
    return pre, post, s.get("critique", {})


def _recall(findings: list[dict], labels: list[dict]):
    hits = []
    for lab in labels:
        if any(_matches(f, lab) for f in findings):
            hits.append(lab)
    return hits


def main() -> None:
    spec = json.loads((_ROOT / "evals" / "expected.json").read_text(encoding="utf-8"))
    labels = spec["labels"]
    target = str(_ROOT / spec["target"])

    pre, post, critique = _run_pipeline(target, spec.get("input_type", "repo"))

    pre_hits = _recall(pre, labels)
    post_hits = _recall(post, labels)
    dropped = critique.get("dropped", [])

    print(f"Target: {spec['target']}  ({len(labels)} planted issues)")
    print("-" * 60)
    print("CRITIC ABLATION")
    print(f"  findings before Critic : {len(pre)}  (recall {len(pre_hits)}/{len(labels)})")
    print(f"  findings after  Critic : {len(post)}  ({len(dropped)} dropped, "
          f"recall {len(post_hits)}/{len(labels)})")
    for d in dropped:
        print(f"    - dropped: {d.get('reason')}  ({str(d.get('issue',''))[:48]})")
    print("-" * 60)
    print("RECALL on planted issues")
    print(f"  caught {len(post_hits)}/{len(labels)} = {len(post_hits)/len(labels):.0%}")
    caught = {(_b['file'], _b['line']) for _b in post_hits}
    for lab in labels:
        mark = "OK " if (lab["file"], lab["line"]) in caught else "MISS"
        print(f"    [{mark}] {lab['file']}:{lab['line']}  {lab['what']}")
    print("-" * 60)
    print("FINDINGS BY AGENT / CATEGORY")
    by_cat: dict[str, list] = {}
    for f in post:
        cat = f.get("category", f.get("type", "unknown"))
        by_cat.setdefault(cat, []).append(f)
    for cat, findings in sorted(by_cat.items()):
        tool_n = sum(1 for f in findings if f.get("tool_grounded"))
        web_n  = sum(1 for f in findings if any(
            "http" in str(r) for r in (f.get("research_basis") or [])
        ))
        print(f"  {cat:<12} {len(findings):2} finding(s)  "
              f"tool-grounded: {tool_n}  web-cited: {web_n}")
    print("-" * 60)
    grounded = sum(1 for f in post if f.get("tool_grounded"))
    conf_avg = (sum(float(f.get("confidence", 0)) for f in post) / len(post)) if post else 0
    print(f"Tool-grounded findings (high-precision): {grounded}/{len(post)}")
    print(f"Average confidence (all kept findings)  : {conf_avg:.2f}")
    print("Note: all kept findings are file:line-verified by the Critic; precision is "
          "reported as the tool-grounded ratio + Critic drops, since labels target the "
          "planted critical issues rather than every lint nit.")


if __name__ == "__main__":
    main()
