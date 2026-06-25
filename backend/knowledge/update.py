"""Update the architecture knowledge base — from a merged diff or by seeding the repo.

CLI (run from repo root):
    python -m backend.knowledge.update --seed                 # bootstrap from current repo
    python -m backend.knowledge.update --diff-file merge.diff # update from a merge diff
"""

from __future__ import annotations

import sys
from pathlib import Path

from .extractor import extract_from_diff, extract_seed
from .store import load_kb, merge_update, save_kb, append_changelog

_ROOT = Path(__file__).resolve().parent.parent.parent
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", ".vite",
              "vendor", "eslint_env", "chroma"}
_CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".md", ".json", ".yml", ".yaml"}


def _repo_map(limit: int = 400) -> str:
    """A compact file tree of the repo (source/config files only)."""
    paths = []
    for p in sorted(_ROOT.rglob("*")):
        if p.is_dir() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in _CODE_EXT:
            paths.append(str(p.relative_to(_ROOT)).replace("\\", "/"))
    return "\n".join(paths[:limit])


def _docs() -> dict:
    out = {}
    for name in ("README.md", "DESIGN.md"):
        fp = _ROOT / name
        if fp.exists():
            out[name] = fp.read_text(encoding="utf-8", errors="ignore")[:8000]
    return out


def seed() -> None:
    print("Seeding knowledge base from current repo…")
    update = extract_seed(_repo_map(), _docs())
    kb = merge_update(load_kb(), update)
    save_kb(kb)
    append_changelog(update.get("change_summary") or "Initial knowledge-base seed from repo.",
                     source="seed")
    print(f"KB seeded: {len(kb.get('modules', {}))} module(s).")


def update_from_diff(diff_text: str, source: str = "merge") -> None:
    kb = load_kb()
    update = extract_from_diff(kb, diff_text)
    if not update.get("modules") and not update.get("overview"):
        print("No architectural changes detected in diff.")
        return
    kb = merge_update(kb, update)
    save_kb(kb)
    append_changelog(update.get("change_summary") or "Updated modules.", source=source)
    print(f"KB updated: {len(update.get('modules', {}))} module(s) touched.")


def main() -> None:
    args = sys.argv[1:]
    if "--seed" in args:
        seed()
        return
    if "--diff-file" in args:
        path = args[args.index("--diff-file") + 1]
        source = args[args.index("--source") + 1] if "--source" in args else "merge"
        update_from_diff(Path(path).read_text(encoding="utf-8", errors="ignore"), source)
        return
    print(__doc__)


if __name__ == "__main__":
    main()
