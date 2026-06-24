"""Context Extractor — detect stack, find files to review.

Handles both inputs:
  - repo:    source is a folder path; walk it for source files.
  - pr_diff: source is unified-diff text; reconstruct changed files into a temp tree
             so the ground-truth tools can lint them, and record changed line numbers.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..state import ReviewState
from ..tools import parse_diff, clone_repo, fetch_pr_diff

_PY = {".py"}
# Source files we review across languages (Python is tool-grounded; others via
# the generic scanner + LLM reviewer).
_CODE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".java", ".kt", ".go", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".cc",
    ".hpp", ".rs", ".swift", ".scala", ".sh", ".bash", ".sql", ".pl", ".lua", ".r",
}
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", ".vite", "vendor"}
_SKIP_SUBSTR = (".min.", ".bundle.")
_MAX_FILES = 40  # soft cap on files actually analyzed, so large repos stay demo-fast


_LANG_BY_EXT = {".py": "python", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
                ".ts": "ts", ".tsx": "ts", ".vue": "vue", ".svelte": "svelte",
                ".java": "java", ".kt": "kotlin", ".go": "go", ".rb": "ruby", ".php": "php",
                ".cs": "c#", ".c": "c", ".h": "c", ".cpp": "c++", ".cc": "c++", ".hpp": "c++",
                ".rs": "rust", ".swift": "swift", ".scala": "scala", ".sh": "shell",
                ".bash": "shell", ".sql": "sql", ".pl": "perl", ".lua": "lua", ".r": "r"}


def _detect_language(files: list[str]) -> str:
    """Return the top languages present, e.g. 'js, python'."""
    from collections import Counter

    c = Counter(_LANG_BY_EXT.get(Path(f).suffix.lower(), "other") for f in files)
    top = [lang for lang, _ in c.most_common(3) if lang != "other"]
    return ", ".join(top) if top else "unknown"


def _walk_repo(root: Path) -> list[str]:
    out = []
    for p in root.rglob("*"):
        if p.is_dir() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        if any(s in p.name for s in _SKIP_SUBSTR):
            continue
        if p.suffix.lower() in _CODE_EXT:
            out.append(str(p))
    return out


def context_node(state: ReviewState) -> ReviewState:
    """Populate ``context`` = {language, review_path, files, changed_lines, entry_points}."""
    input_type = state.get("input_type", "repo")
    source = state["source"]

    # PR review: accept either a pasted diff ("pr_diff") or a GitHub PR URL
    # ("pr_url", or a URL pasted into pr_diff mode) which we fetch the diff for.
    if input_type in ("pr_diff", "pr_url"):
        diff_text = source
        if input_type == "pr_url" or source.strip().lower().startswith("http"):
            res = fetch_pr_diff(source)
            if res.get("error"):
                return {"context": {"input_type": input_type, "language": "unknown",
                                    "review_path": "", "files": [], "py_files": [],
                                    "other_files": [], "changed_lines": {},
                                    "entry_points": [], "error": res["error"]}}
            diff_text = res["diff"]
        parsed = parse_diff(diff_text)
        tmp = Path(tempfile.mkdtemp(prefix="scout_diff_"))
        files, changed_lines = [], {}
        for rel, info in parsed["files"].items():
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(info["content"], encoding="utf-8")
            files.append(str(dest))
            changed_lines[str(dest)] = sorted(info["added_lines"])
        review_path = str(tmp)
    elif input_type == "github":
        res = clone_repo(source)
        if res.get("error"):
            return {"context": {"input_type": "github", "language": "unknown",
                                "review_path": "", "files": [], "py_files": [],
                                "changed_lines": {}, "entry_points": [], "error": res["error"]}}
        root = Path(res["path"])
        files = _walk_repo(root)
        changed_lines = {}
        review_path = res["path"]
    else:
        root = Path(source)
        files = _walk_repo(root) if root.exists() else []
        changed_lines = {}
        review_path = source

    # Cap the source files we actually analyze (Python prioritized for tool grounding).
    py_all = [f for f in files if Path(f).suffix.lower() in _PY]
    other_all = [f for f in files if Path(f).suffix.lower() not in _PY]
    ordered = py_all + other_all
    reviewed_files = ordered[:_MAX_FILES]
    py_files = [f for f in reviewed_files if Path(f).suffix.lower() in _PY]
    other_files = [f for f in reviewed_files if Path(f).suffix.lower() not in _PY]

    counts = {
        "total_source": len(files),
        "python": len(py_all),
        "other": len(other_all),
        "reviewed": len(reviewed_files),
        "skipped": len(files) - len(reviewed_files),
    }
    entry_points = [f for f in py_files if Path(f).name in {"main.py", "app.py", "__main__.py"}]

    return {
        "context": {
            "input_type": input_type,
            "language": _detect_language(reviewed_files),
            "review_path": review_path,
            "files": reviewed_files,
            "py_files": py_files,
            "other_files": other_files,
            "counts": counts,
            "changed_lines": changed_lines,
            "entry_points": entry_points,
        }
    }
