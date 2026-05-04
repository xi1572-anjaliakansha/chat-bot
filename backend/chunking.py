"""
Split document text into overlapping chunks for retrieval / RAG (step-by-step).

Chunk schema (each chunk):
  index      — order in the document (0-based)
  text       — slice of the normalized document text
  char_start — inclusive offset in the stored full text
  char_end   — exclusive offset
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    char_start: int
    char_end: int

    def to_store_dict(self) -> dict[str, int | str]:
        d = asdict(self)
        # camelCase for any future JSON APIs
        return {
            "index": d["index"],
            "text": d["text"],
            "charStart": d["char_start"],
            "charEnd": d["char_end"],
        }


def split_text_into_chunks(
    text: str,
    *,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    """Greedy character windows with overlap. Later steps can add sentence/pdf-page boundaries."""
    max_chars = max_chars or int(os.getenv("CHUNK_MAX_CHARS", "1500"))
    overlap = overlap if overlap is not None else int(os.getenv("CHUNK_OVERLAP", "200"))

    if not text.strip():
        return []
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must satisfy 0 <= overlap < max_chars")

    chunks: list[TextChunk] = []
    start = 0
    n = len(text)
    idx = 0
    while start < n:
        end = min(start + max_chars, n)
        piece = text[start:end]
        chunks.append(
            TextChunk(index=idx, text=piece, char_start=start, char_end=end)
        )
        idx += 1
        if end >= n:
            break
        start = end - overlap
    return chunks
