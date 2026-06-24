"""FastAPI app — REST + streaming endpoints that run the Scout review graph."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .graph import build_graph, run
from .state import initial_state
from .report_md import save_report

app = FastAPI(title="Scout — Research-Aware Code Review Assistant")

# Dev CORS: allow the Vite frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewRequest(BaseModel):
    source: str                 # repo folder path, GitHub URL, or unified-diff text
    input_type: str = "repo"    # "repo" | "github" | "pr_diff"
    save: bool = False          # also write a Markdown report to reports/


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/review")
def review(req: ReviewRequest) -> dict:
    """Run the review graph to completion and return the final report."""
    report = run(req.source, req.input_type)
    out = {"report": report}
    if req.save:
        out["saved_to"] = save_report(report, req.source)
    return out


@app.post("/review/stream")
def review_stream(req: ReviewRequest) -> StreamingResponse:
    """Stream per-node state updates for the glass-box view (SSE-style)."""

    def event_stream():
        graph = build_graph()
        for update in graph.stream(
            initial_state(req.source, req.input_type), {"recursion_limit": 50}
        ):
            yield f"data: {json.dumps(update, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
