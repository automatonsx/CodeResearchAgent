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
        hits = retrieve(query, k=1)
        if hits:
            top = hits[0]
            basis = f"{top['title']} — {top['source']}"
            f["research_basis"] = [basis]
            citations.append({"finding": f.get("issue", ""), "title": top["title"],
                              "source": top["source"], "principle": top.get("principle")})
        else:
            f.setdefault("research_basis", [])
    return {"findings": findings, "citations": citations}
