---
name: build-corpus
description: (Re)build the curated best-practices ChromaDB index that the Grounding step uses to cite findings. Use after editing backend/corpus/best_practices.json or to initialize the vector store.
---


# build-corpus

(Re)build the best-practices corpus index used for citation grounding (the RAG store).

## When to use
- After editing `backend/corpus/best_practices.json` (add/change entries).
- To initialize the ChromaDB collection on a fresh checkout.

## Steps
1. From the repo root, run the indexer:
   ```bash
   python -m backend.corpus.build_index --rebuild
   ```
2. It loads `best_practices.json`, embeds each entry into ChromaDB at
   `CHROMA_PERSIST_DIR` (default `data/chroma`), and prints the indexed count.
3. If ChromaDB/embeddings are unavailable, grounding still works via keyword/tag
   retrieval over the same JSON — the rebuild is a no-op in that case.

## Note
The corpus is intentionally small and curated (~12 entries) — quality over quantity.
Each entry: `{id, title, principle, source, tags}`.
