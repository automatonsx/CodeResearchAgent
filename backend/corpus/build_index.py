"""Best-practices corpus → ChromaDB index, with retrieval for the Grounding step.

RAG component: each curated best-practice is embedded into ChromaDB so findings can
be matched to a cited principle. If ChromaDB/embeddings are unavailable, retrieval
falls back to keyword/tag scoring over the same JSON — grounding always works.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_CORPUS_PATH = _DIR / "best_practices.json"
_PERSIST = os.environ.get("CHROMA_PERSIST_DIR") or str(_DIR.parent.parent / "data" / "chroma")
_COLLECTION = "best_practices"


def load_corpus() -> list[dict]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _collection():
    """Build (or load) the ChromaDB collection. Returns None on any failure."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=_PERSIST)
        col = client.get_or_create_collection(_COLLECTION)
        if col.count() == 0:
            corpus = load_corpus()
            col.add(
                ids=[c["id"] for c in corpus],
                documents=[f"{c['title']}. {c['principle']} Tags: {' '.join(c['tags'])}" for c in corpus],
                metadatas=[{"title": c["title"], "source": c["source"], "tags": ",".join(c["tags"])} for c in corpus],
            )
        return col
    except Exception:
        return None


def _keyword_retrieve(query: str, k: int) -> list[dict]:
    """Fallback: score corpus entries by token/tag overlap with the query."""
    corpus = load_corpus()
    q = query.lower()
    q_tokens = set(t for t in q.replace(",", " ").split() if len(t) > 2)
    scored = []
    for c in corpus:
        hay = (c["title"] + " " + c["principle"] + " " + " ".join(c["tags"])).lower()
        tag_hits = sum(1 for t in c["tags"] if t.lower() in q)
        tok_hits = sum(1 for t in q_tokens if t in hay)
        score = tag_hits * 3 + tok_hits
        if score:
            scored.append((score, c))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [c for _, c in scored[:k]]


def retrieve(query: str, k: int = 1) -> list[dict]:
    """Return up to k best-practice citations for a finding query.

    Each: {id?, title, principle?, source}. Tries ChromaDB, falls back to keywords.
    """
    col = _collection()
    if col is not None:
        try:
            res = col.query(query_texts=[query], n_results=k)
            metas = (res.get("metadatas") or [[]])[0]
            ids = (res.get("ids") or [[]])[0]
            if metas:
                by_id = {c["id"]: c for c in load_corpus()}
                out = []
                for cid, m in zip(ids, metas):
                    base = by_id.get(cid, {})
                    out.append({"id": cid, "title": m.get("title"),
                                "principle": base.get("principle"), "source": m.get("source")})
                return out
        except Exception:
            pass
    return _keyword_retrieve(query, k)


def build(rebuild: bool = False) -> int:
    """(Re)build the ChromaDB index. Returns the number of indexed entries."""
    if rebuild:
        try:
            import chromadb

            chromadb.PersistentClient(path=_PERSIST).delete_collection(_COLLECTION)
        except Exception:
            pass
        _collection.cache_clear()
    col = _collection()
    if col is not None:
        return col.count()
    return len(load_corpus())  # fallback mode still "works" via keyword retrieval


if __name__ == "__main__":
    import sys

    n = build(rebuild="--rebuild" in sys.argv)
    print(f"Corpus ready: {n} best-practice entries indexed at {_PERSIST}")
