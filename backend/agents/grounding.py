"""Grounding step — attach a best-practice citation to each finding (RAG).

Queries the curated ChromaDB corpus for the principle behind each finding and stores
it in ``research_basis``. No LLM call — deterministic retrieval.
"""

from __future__ import annotations

from ..state import ReviewState
from ..corpus.build_index import retrieve


def grounding_node(state: ReviewState) -> ReviewState:
    findings = state.get("findings", [])
    citations = []
    for f in findings:
        # KB-grounded (architecture/design) findings already carry a KB citation — leave them.
        if f.get("kb_grounded"):
            continue
        query = " ".join(
            str(x) for x in [f.get("type"), f.get("tool_evidence"), f.get("issue")] if x
        )
        hits = retrieve(query, k=3)
        if hits:
            # Attach up to 2 distinct citations; dedup by title to avoid corpus repeats.
            seen_titles: set[str] = set()
            basis: list[str] = []
            for hit in hits:
                title = hit.get("title") or ""
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    basis.append(f"{title} — {hit['source']}")
                    citations.append({
                        "finding": f.get("issue", ""),
                        "title": title,
                        "source": hit["source"],
                        "principle": hit.get("principle"),
                    })
                if len(basis) >= 2:
                    break
            f["research_basis"] = basis
        else:
            f.setdefault("research_basis", [])
    return {"findings": findings, "citations": citations}
