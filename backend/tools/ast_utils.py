"""AST-based ground-truth checks for Python.

Deterministic structural checks that complement ruff: cyclomatic-ish complexity,
missing docstrings on public functions, and mutable default arguments. Each finding
carries a verifiable file:line the Critic can re-open.
"""

from __future__ import annotations

import ast
from pathlib import Path

_COMPLEXITY_THRESHOLD = 10


class _Analyzer(ast.NodeVisitor):
    def __init__(self, file: str) -> None:
        self.file = file
        self.findings: list[dict] = []

    def _complexity(self, node: ast.AST) -> int:
        score = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or,
                                  ast.ExceptHandler, ast.With, ast.Assert)):
                score += 1
            elif isinstance(child, ast.BoolOp):
                score += len(child.values) - 1
        return score

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        # Missing docstring on a public function.
        if not node.name.startswith("_") and ast.get_docstring(node) is None:
            self.findings.append(self._mk(node, "AST-DOC",
                                          f"Public function '{node.name}' has no docstring"))
        # High complexity.
        cx = self._complexity(node)
        if cx > _COMPLEXITY_THRESHOLD:
            self.findings.append(self._mk(node, "AST-CX",
                                          f"Function '{node.name}' is complex (score {cx})"))
        # Mutable default arguments.
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.findings.append(self._mk(node, "AST-MUT",
                                              f"Mutable default argument in '{node.name}'"))
                break
        self.generic_visit(node)

    def _mk(self, node: ast.AST, code: str, msg: str) -> dict:
        return {"tool": "ast", "code": code, "type": "code",
                "file": self.file, "line": getattr(node, "lineno", 0), "message": msg}


def _resolve_files(target) -> list[Path]:
    """Accept a file path, a dir path, or an explicit list of files."""
    if isinstance(target, (list, tuple)):
        return [Path(f) for f in target if str(f).endswith(".py")]
    p = Path(target)
    return [p] if p.is_file() and p.suffix == ".py" else list(p.rglob("*.py"))


_DOC_MAX_CHARS = 120


def _doc_summary(node) -> str:
    """Return the first line of a node's docstring, truncated. '' if none.

    The docstring is the author's stated intent — a fact the architecture LLM can
    reason over instead of guessing behavior from the function name. We keep only
    the first line so token cost stays tiny.
    """
    try:
        doc = ast.get_docstring(node)
    except Exception:
        return ""
    if not doc:
        return ""
    first = doc.strip().splitlines()[0].strip()
    return first[:_DOC_MAX_CHARS]


def python_skeleton(file: str) -> dict | None:
    """Return a compact structural skeleton of a Python file — imports + top-level
    class/function signatures + line count — for the architecture agent.

    This replaces sending raw file bodies to the LLM: it carries the *structure*
    an architect needs (modules, boundaries, public surface) at a tiny fraction of
    the tokens. Returns None if the file cannot be parsed.
    """
    try:
        src = Path(file).read_text(encoding="utf-8", errors="ignore").replace("\x00", "")
        tree = ast.parse(src)
    except Exception:
        return None

    imports: list[str] = []
    classes: list[dict] = []
    functions: list[dict] = []

    for node in tree.body:  # top-level declarations only
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.extend(f"{mod}.{a.name}" if mod else a.name for a in node.names)
        elif isinstance(node, ast.ClassDef):
            methods = [
                m.name for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            entry = {"name": node.name, "methods": methods, "line": node.lineno}
            doc = _doc_summary(node)
            if doc:
                entry["doc"] = doc
            classes.append(entry)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entry = {"name": node.name, "args": [a.arg for a in node.args.args],
                     "line": node.lineno}
            doc = _doc_summary(node)
            if doc:
                entry["doc"] = doc
            functions.append(entry)

    skeleton = {
        "imports": imports[:40],
        "classes": classes,
        "functions": functions,
        "loc": len(src.splitlines()),
    }
    # Module docstring = the file's own statement of purpose (gold for architecture).
    module_doc = _doc_summary(tree)
    if module_doc:
        skeleton["module_doc"] = module_doc
    return skeleton


def ast_findings(target) -> list[dict]:
    """Return AST findings for the given file/dir/list of Python files.

    Tolerant of real-world repos: skips files with null bytes or parse errors.
    """
    out: list[dict] = []
    for f in _resolve_files(target):
        try:
            src = f.read_text(encoding="utf-8", errors="ignore").replace("\x00", "")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, ValueError):
            out.append({"tool": "ast", "code": "AST-SYNTAX", "type": "code",
                        "file": str(f), "line": 0, "message": "File could not be parsed"})
            continue
        except Exception:
            continue
        analyzer = _Analyzer(str(f))
        analyzer.visit(tree)
        out.extend(analyzer.findings)
    return out
