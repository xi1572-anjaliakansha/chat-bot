"""
Step 2 of RAG: embed the question and pick the top-k chunks by cosine similarity.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector length mismatch for cosine similarity")
    dot = math.fsum(x * y for x, y in zip(a, b))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def retrieve_context(
    question: str,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    *,
    top_k: int | None = None,
) -> str:
    """
    Returns a single string made of the top-k chunk texts (with light labels).
    `chunks` / `embeddings` must be aligned (same order as upload).
    """
    top_k = top_k if top_k is not None else int(os.getenv("RAG_TOP_K", "5"))
    top_k = max(1, top_k)

    if not chunks or not embeddings:
        return ""
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
        )

    from embeddings import embed_query_text

    q_vec = embed_query_text(question)
    scored: list[tuple[float, dict[str, Any]]] = []
    for emb, ch in zip(embeddings, chunks):
        scored.append((_cosine_similarity(q_vec, emb), ch))
    scored.sort(key=lambda x: -x[0])

    take = scored[: min(top_k, len(scored))]
    logger.debug(
        "retrieval top scores: %s",
        [round(s, 4) for s, _ in take[:3]],
    )

    parts: list[str] = []
    for i, (score, ch) in enumerate(take, 1):
        t = str(ch.get("text", "")).strip()
        if not t:
            continue
        idx = ch.get("index", i - 1)
        parts.append(f"[Passage {idx} | relevance={score:.3f}]\n{t}")

    return "\n\n---\n\n".join(parts)
