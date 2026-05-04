"""
Azure OpenAI embedding calls; vectors stored in memory alongside chunks (see app.DOCUMENT_STORE).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

_embedder: Any = None


def _azure_base() -> tuple[str, str, str]:
    azure_url = (os.getenv("AZURE_OPENAI_URL") or "").strip()
    azure_endpoint = (
        azure_url.split("/openai/")[0] if "/openai/" in azure_url else azure_url
    )
    api_key = os.getenv("AZURE_OPENAI_KEY") or ""
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    return azure_endpoint, api_key, api_version


def get_embedding_model() -> Any:
    """Singleton Azure OpenAI embeddings client (lazy)."""
    global _embedder
    if _embedder is not None:
        return _embedder

    try:
        from langchain_openai import AzureOpenAIEmbeddings
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Package langchain-openai is not installed in this Python environment. "
            f"Current interpreter: {sys.executable}. "
            "Fix: cd backend && source venv/bin/activate && pip install -r requirements.txt "
            "then run: ./venv/bin/python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000"
        ) from e

    azure_endpoint, api_key, api_version = _azure_base()
    deployment = (os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or "").strip()

    if not azure_endpoint or not api_key:
        raise RuntimeError(
            "Missing AZURE_OPENAI_URL (or endpoint) or AZURE_OPENAI_KEY for embeddings."
        )
    if not deployment:
        raise RuntimeError(
            "Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT to your Azure embedding deployment name."
        )

    _embedder = AzureOpenAIEmbeddings(
        azure_endpoint=azure_endpoint,
        azure_deployment=deployment,
        openai_api_version=api_version,
        openai_api_key=api_key,
    )
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed each string; returns vectors in the same order as `texts`.
    Batches to limit payload size per API call.
    """
    if not texts:
        return []

    batch_size = max(1, int(os.getenv("EMBED_BATCH_SIZE", "16")))
    embedder = get_embedding_model()

    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = embedder.embed_documents(batch)
        out.extend(vectors)

    if len(out) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: expected {len(texts)}, got {len(out)}"
        )
    return out


def embed_query_text(text: str) -> list[float]:
    """Single-vector embedding for the user question (same model as chunk embeddings)."""
    q = (text or "").strip()
    if not q:
        raise ValueError("Query text is empty")
    embedder = get_embedding_model()
    return embedder.embed_query(q)
