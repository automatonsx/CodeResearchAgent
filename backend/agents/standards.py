"""Standards Extractor — synthesizes Scout findings into project-specific coding rules.

Runs after the full review pipeline. Produces a structured ``standards`` object that
``backend/standards_skill.py`` renders as a SKILL.md for Claude Code injection.

The output is repo-specific: every rule is grounded in an actual verified finding from
the codebase, not generic advice. This makes the generated skill file more useful than
a generic linting guide.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import re

from ..state import ReviewState
from ..llm import chat_json, load_prompt

# Config files that encode tooling rules worth surfacing in the skill
_CONFIG_FILES = [
    "pyproject.toml", ".ruff.toml", "ruff.toml",
    ".eslintrc", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
    "setup.cfg", ".flake8", "tox.ini",
]
_MAX_CONFIG_CHARS = 800


_FRAMEWORK_PATTERNS = {
    "pytest": r"\bpytest\b",
    "django": r"\bdjango\b",
    "fastapi": r"\bfastapi\b",
    "flask": r"\bflask\b",
    "react": r"\breact\b",
    "vue": r"\bvue\b",
    "express": r"\bexpress\b",
}


def _detect_frameworks(file_contents: list[dict]) -> list[str]:
    """Detect framework names by scanning file content for known import patterns."""
    found: set[str] = set()
    for fc in file_contents:
        content = (fc.get("content") or "").lower()
        for name, pat in _FRAMEWORK_PATTERNS.items():
            if re.search(pat, content):
                found.add(name)
    return sorted(found)


def _read_config_files(review_path: str) -> dict[str, str]:
    root = Path(review_path)
    found: dict[str, str] = {}
    for name in _CONFIG_FILES:
        p = root / name
        if p.is_file():
            try:
                found[name] = p.read_text(encoding="utf-8", errors="ignore")[:_MAX_CONFIG_CHARS]
            except Exception:
                pass
    return found


def standards_node(state: ReviewState) -> ReviewState:
    """Synthesize all pipeline findings into an explicit standards object."""
    findings = state.get("findings", [])
    ctx = state.get("context", {})
    review_path = ctx.get("review_path", "")

    if not findings:
        return {"standards": {}}

    config_files = _read_config_files(review_path)
    frameworks = _detect_frameworks(ctx.get("_file_contents", []))

    # Build a lean findings payload — only the fields the LLM needs for rule synthesis
    payload = {
        "findings": [
            {
                "category":      f.get("category", ""),
                "severity":      f.get("severity", ""),
                "issue":         f.get("issue", ""),
                "suggestion":    f.get("suggestion", ""),
                # bad_code = the real offending lines from the repo file (the actual bad pattern)
                # good_code = the corrected snippet the security/quality agent wrote
                # Using distinct keys avoids the LLM confusing which is which.
                "bad_code":      (f.get("_raw_snippet") or "")[:300],
                "good_code":     (f.get("example") or "")[:200],
                "file":          f.get("file", ""),
                "line":          f.get("line", ""),
                "tool_evidence": f.get("tool_evidence", ""),
                "tool_grounded": f.get("tool_grounded", False),
                "confidence":    f.get("confidence", 0.5),
                # Corpus citations attached by grounding_node — used to populate rule citations
                "citations":     f.get("research_basis", []),
            }
            for f in findings
        ],
        "language":     ctx.get("language", "unknown"),
        "frameworks":   frameworks,
        "config_files": config_files,
        "dropped_count":len(state.get("critique", {}).get("dropped", [])),
    }

    prompt = (
        load_prompt("standards")
        + "\n\nINPUT:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )
    try:
        data = chat_json(
            "You are a senior engineering team lead writing project-specific coding standards.",
            prompt,
            temperature=0.1,  # low variance — rules should be deterministic
        )
    except Exception as exc:
        print(f"[Scout] standards_node failed: {exc}", file=sys.stderr)
        data = {}

    return {"standards": data}
