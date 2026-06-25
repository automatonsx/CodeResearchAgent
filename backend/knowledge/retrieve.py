"""Retrieve relevant KB context for a review (direct module lookup).

The KB describes THIS repo, so it only applies when the reviewed files map to known
modules (our own PRs/CI). For unrelated external repos nothing matches → the
KB-aware lens stays quiet.
"""

from __future__ import annotations

from .store import load_kb


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip("/")


def relevant_kb(rel_paths: list[str]) -> dict:
    """Return {overview, modules} for the KB modules the reviewed files belong to.

    ``rel_paths`` are repo-relative paths (e.g. "backend/agents/critic.py").
    Matches a module when a file sits under the module path or is listed in its
    key_files. Empty ``modules`` ⇒ KB doesn't apply (external repo).
    """
    kb = load_kb()
    modules = kb.get("modules", {})
    rels = [_norm(p) for p in rel_paths]

    matched: dict[str, dict] = {}
    for name, entry in modules.items():
        key = _norm(name)
        key_files = {_norm(f) for f in entry.get("key_files", [])}
        for rp in rels:
            if rp == key or rp.startswith(key + "/") or rp in key_files:
                matched[name] = entry
                break
    return {"overview": kb.get("overview", ""), "modules": matched}
