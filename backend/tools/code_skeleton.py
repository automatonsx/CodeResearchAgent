"""Language-agnostic structural skeletons via tree-sitter.

Extracts a compact structure — imports, class/type names, function/method names,
and line count — from a source file in any supported language, WITHOUT sending the
raw file body to the LLM. This is what the architecture agent reviews: it carries
module boundaries and the public surface at a tiny fraction of the tokens.

Python is handled by the stdlib ``ast`` (see ast_utils.python_skeleton); every other
language is handled here by tree-sitter. If a language is unsupported or a file fails
to parse, ``code_skeleton`` returns None and the caller falls back to a small head.
"""

from __future__ import annotations

from pathlib import Path

from .ast_utils import python_skeleton

# File extension → tree-sitter language name (as known to tree_sitter_language_pack).
_EXT_LANG = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".java": "java", ".go": "go", ".rb": "ruby", ".php": "php", ".cs": "c_sharp",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".rs": "rust", ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
}

# Node types that represent each construct, across languages. A superset is fine —
# we only collect what a given grammar actually produces.
_FUNC_TYPES = {
    "function_declaration", "function_definition", "method_definition",
    "method_declaration", "function_item", "func_literal", "constructor_declaration",
}
_CLASS_TYPES = {
    "class_declaration", "class_definition", "class_specifier", "interface_declaration",
    "struct_item", "struct_specifier", "type_declaration", "enum_declaration",
    "trait_item", "object_declaration",
}
_IMPORT_TYPES = {
    "import_statement", "import_declaration", "import_from_statement",
    "using_directive", "preproc_include", "package_clause", "use_declaration",
}


def _name_of(node) -> str:
    """Best-effort name of a declaration node (first identifier-ish child)."""
    for child in node.children:
        if "identifier" in child.type or child.type in ("name", "type_identifier"):
            try:
                return child.text.decode("utf-8", "ignore")
            except Exception:
                return ""
    return ""


def _ts_skeleton(file: str, lang_name: str) -> dict | None:
    try:
        import tree_sitter
        from tree_sitter_language_pack import get_language
    except Exception:
        return None  # tree-sitter not installed → caller falls back to head
    try:
        src = Path(file).read_text(encoding="utf-8", errors="ignore")
        parser = tree_sitter.Parser(get_language(lang_name))
        tree = parser.parse(bytes(src, "utf-8"))
    except Exception:
        return None

    imports = 0
    classes: list[str] = []
    functions: list[str] = []

    def walk(node) -> None:
        nonlocal imports
        if node.type in _IMPORT_TYPES:
            imports += 1
        elif node.type in _CLASS_TYPES:
            nm = _name_of(node)
            if nm:
                classes.append(nm)
        elif node.type in _FUNC_TYPES:
            nm = _name_of(node)
            if nm:
                functions.append(nm)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return {
        "imports": imports,
        "classes": classes[:60],
        "functions": functions[:120],
        "loc": len(src.splitlines()),
    }


def code_skeleton(file: str) -> dict | None:
    """Return a structural skeleton for any supported language, or None.

    Python → stdlib ast; everything else → tree-sitter. None means "unsupported or
    unparseable" — the caller should fall back to a small text head.
    """
    if file.endswith(".py"):
        return python_skeleton(file)
    lang = _EXT_LANG.get(Path(file).suffix.lower())
    if not lang:
        return None
    return _ts_skeleton(file, lang)
