"""Critic — verify every finding is real + sourced; drop false positives → loop.

The Critic is the agentic twist: it re-opens each ``file:line`` to confirm the
finding, removes unverifiable/duplicate ones, and flags low-confidence non-tool
findings for a re-check (max 2 loops).
"""

from __future__ import annotations

from pathlib import Path

from ..state import ReviewState, MAX_ITERATIONS

_LOW_CONFIDENCE = 0.5


def _read_lines(file: str) -> list[str] | None:
    try:
        return Path(file).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None


def _line_exists(file: str, line: int) -> bool:
    """True if the file is readable and the line number is in range."""
    lines = _read_lines(file)
    return lines is not None and 1 <= int(line or 0) <= len(lines)


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _quote_matches(file: str, line: int, quote: str) -> bool:
    """True if a meaningful chunk of the LLM's quoted code appears near file:line.

    This is how the Critic catches hallucinated (non-tool) findings: the model must
    have quoted code that actually exists at (±3 lines of) the cited location.
    """
    if not quote or len(_norm(quote)) < 8:
        return False  # no usable quote to verify
    lines = _read_lines(file)
    if lines is None:
        return False
    lo, hi = max(0, int(line or 1) - 4), min(len(lines), int(line or 1) + 3)
    window = _norm(" ".join(lines[lo:hi]))
    q = _norm(quote)
    # Match on a 12-char slice to tolerate minor reformatting by the LLM.
    probe = q[:12] if len(q) >= 12 else q
    return probe in window


def critic_node(state: ReviewState) -> ReviewState:
    """Validate findings; produce ``critique`` and a cleaned ``findings`` list."""
    findings = state.get("findings", [])
    kept, dropped, low_conf, seen = [], [], [], set()

    for f in findings:
        file, line = f.get("file", ""), f.get("line", 0)
        # Collapse the same issue reported at one location (e.g. ruff B006 + AST-MUT).
        key = (file, line, f.get("type"))

        # 1. No finding without a verifiable file:line.
        if not _line_exists(file, line):
            dropped.append({"issue": f.get("issue", ""), "reason": "file:line not verifiable"})
            continue
        # 2. Non-tool (LLM) findings must quote code that actually exists at file:line.
        if not f.get("tool_grounded"):
            if not _quote_matches(file, line, f.get("example", "")):
                dropped.append({"issue": f.get("issue", ""),
                                "reason": "quoted code not found at file:line (likely hallucinated)"})
                continue
        # 3. Deduplicate.
        if key in seen:
            dropped.append({"issue": f.get("issue", ""), "reason": "duplicate"})
            continue
        seen.add(key)
        # 4. Low-confidence non-tool findings are flagged for re-check.
        if not f.get("tool_grounded") and float(f.get("confidence", 0)) < _LOW_CONFIDENCE:
            low_conf.append({"issue": f.get("issue", ""), "file": file, "line": line})
        kept.append(f)

    has_budget = state.get("iterations", 0) < MAX_ITERATIONS
    # Re-check when the Critic caught a hallucinated finding or flagged a weak one —
    # give the agents another pass (with this feedback) to self-correct.
    hallucinated = [d for d in dropped if "hallucinated" in d.get("reason", "")]
    needs_recheck = bool(low_conf or hallucinated) and has_budget

    notes = []
    if dropped:
        notes.append(f"Dropped {len(dropped)} unverifiable/duplicate finding(s).")
    if hallucinated:
        notes.append(f"{len(hallucinated)} finding(s) had quoted code that didn't match — re-checking.")
    if low_conf:
        notes.append(f"{len(low_conf)} low-confidence finding(s) need stronger evidence.")

    critique = {
        "dropped": dropped,
        "low_confidence": low_conf,
        "needs_recheck": needs_recheck,
        "notes": notes,
    }
    return {"findings": kept, "critique": critique}


def critic_router(state: ReviewState) -> str:
    """Conditional edge: re-check (re-analyze) or proceed to the report."""
    critique = state.get("critique", {})
    if critique.get("needs_recheck") and state.get("iterations", 0) < MAX_ITERATIONS:
        return "recheck"
    return "report"
