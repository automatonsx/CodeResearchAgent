"""Shared batching helpers for the file-content review agents.

The architecture, test-review and generic-review agents used to pack *all* files
into a single LLM prompt. On large repos that single prompt blew past the model
context window ("token limit exceeded") and forced aggressive per-file truncation
(2.5k chars) that silently dropped coverage.

These helpers instead split work into size-bounded batches and run the per-batch
LLM calls concurrently. Concurrency is safe within the project's Azure quota — the
LLM client (llm.py) already retries 429s with exponential back-off.

Tunable via env (all optional):
    SCOUT_BATCH_CHARS    max characters of file content per batch   (default 48000)
    SCOUT_BATCH_ITEMS    max files per batch                        (default 12)
    SCOUT_BATCH_WORKERS  max concurrent LLM calls                   (default 8)
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")

# gpt-4o has a ~128k-token context window. We budget input file content well under
# that per call (~4 chars/token → 48000 chars ≈ 12k input tokens) so the prompt
# template + corpus + KB + the model's JSON output all fit with comfortable headroom.
MAX_BATCH_CHARS = int(os.environ.get("SCOUT_BATCH_CHARS", "48000"))
# Kept modest: the LLM's *output* grows with the number of findings a batch
# produces, and too many findings in one reply can exceed the output-token limit.
MAX_BATCH_ITEMS = int(os.environ.get("SCOUT_BATCH_ITEMS", "8"))
# Concurrent LLM calls. Rate limits (429) are driven by concurrency × per-call
# token reservation within Azure's ~10s window, so this is the PRIMARY 429 lever —
# kept low on purpose. Override SCOUT_BATCH_WORKERS.
MAX_WORKERS = int(os.environ.get("SCOUT_BATCH_WORKERS", "4"))


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return len(text) // 4 + 1


def batch_by_size(
    items: list[T],
    size_of: Callable[[T], int],
    max_chars: int = MAX_BATCH_CHARS,
    max_items: int = MAX_BATCH_ITEMS,
) -> list[list[T]]:
    """Greedily pack ``items`` into batches bounded by total chars and item count.

    An item larger than ``max_chars`` on its own still gets its own batch — callers
    truncate individual files to a sane per-file ceiling before batching.
    """
    batches: list[list[T]] = []
    current: list[T] = []
    current_chars = 0
    for item in items:
        size = size_of(item)
        if current and (current_chars + size > max_chars or len(current) >= max_items):
            batches.append(current)
            current, current_chars = [], 0
        current.append(item)
        current_chars += size
    if current:
        batches.append(current)
    return batches


def _run_with_split(
    batch: list[T],
    fn: Callable[[list[T]], list[R]],
    label: str,
) -> list[R]:
    """Run ``fn`` on a batch; on failure, split in half and retry recursively.

    This is the self-healing core: a batch that fails for *any* reason (truncated
    JSON, output-token overflow, a single pathological item that makes the model
    loop) is bisected and each half retried. Only a *single* item that still fails
    on its own is dropped — so worst-case loss is one item, never a whole batch,
    on any codebase without per-repo tuning.
    """
    try:
        return list(fn(batch) or [])
    except Exception as exc:  # noqa: BLE001 — fn failures are expected & recovered
        if len(batch) <= 1:
            print(
                f"[Scout/batch] dropping 1 item in {label} after isolated failure: "
                f"{type(exc).__name__}: {str(exc)[:160]}",
                file=sys.stderr,
            )
            return []
        mid = len(batch) // 2
        out: list[R] = []
        out.extend(_run_with_split(batch[:mid], fn, label))
        out.extend(_run_with_split(batch[mid:], fn, label))
        return out


def map_batches(
    batches: list[list[T]],
    fn: Callable[[list[T]], list[R]],
    max_workers: int = MAX_WORKERS,
    label: str = "batch",
) -> list[R]:
    """Run ``fn`` over each batch concurrently and flatten the results.

    ``fn`` may raise — a failing batch is bisected and retried (see
    ``_run_with_split``), so callers should let LLM/parse errors propagate rather
    than swallowing them. Genuinely-empty results (no findings) are fine.
    """
    if not batches:
        return []
    if len(batches) == 1:
        return _run_with_split(batches[0], fn, label)
    out: list[R] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(batches))) as pool:
        for result in pool.map(lambda b: _run_with_split(b, fn, label), batches):
            if result:
                out.extend(result)
    return out
