from __future__ import annotations

import io
import logging
import os
import sys
import uuid
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AliasChoices, BaseModel, Field

from chunking import split_text_into_chunks
from embeddings import embed_texts
from retrieval import retrieve_context

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ.setdefault(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; NoshDocChat/1.0)",
)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_CONTEXT_CHARS = 120_000

# doc_id -> { text, file_name, chunks, embeddings: list[list[float]] }
DOCUMENT_STORE: dict[str, dict[str, Any]] = {}

_azure_chain: Any = None


def _azure_env() -> tuple[str, str, str, str]:
    azure_url = (os.getenv("AZURE_OPENAI_URL") or "").strip()
    azure_endpoint = (
        azure_url.split("/openai/")[0] if "/openai/" in azure_url else azure_url
    )
    api_key = os.getenv("AZURE_OPENAI_KEY") or ""
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    chat_deployment = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini")
    return azure_endpoint, api_key, api_version, chat_deployment


def get_answer_chain():
    """Build LangChain RAG-style chain once (lazy)."""
    global _azure_chain
    if _azure_chain is not None:
        return _azure_chain

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import AzureChatOpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "LangChain packages are missing. Install: pip install -r requirements.txt "
            f"using the same Python as uvicorn (this one: {sys.executable}). "
            "Or run: ./run_dev.sh from the backend folder."
        ) from e

    azure_endpoint, api_key, api_version, chat_deployment = _azure_env()
    if not azure_endpoint or not api_key:
        raise RuntimeError(
            "Missing AZURE_OPENAI_URL (or endpoint) or AZURE_OPENAI_KEY in environment."
        )

    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        azure_deployment=chat_deployment,
        openai_api_version=api_version,
        openai_api_key=api_key,
        temperature=0.3,
        max_tokens=1024,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Answer using only the retrieved "
                "passages below when they are relevant. If the answer is not in "
                "the passages, say so clearly. Be concise.\n\n"
                "--- Retrieved passages ---\n{context}\n--- End ---",
            ),
            ("human", "{question}"),
        ]
    )

    _azure_chain = prompt | llm | StrOutputParser()
    return _azure_chain


def extract_text(filename: str, raw: bytes) -> str:
    name = (filename or "upload").lower()

    if name.endswith((".txt", ".md", ".csv", ".json", ".html", ".htm")):
        return raw.decode("utf-8", errors="replace")

    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n\n".join(parts)

    if name.endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text)

    # Plain fallback for unknown types
    return raw.decode("utf-8", errors="replace")


app = FastAPI(title="Nosh Doc Chat API", version="1.0.0")

# Cross-origin browser requests: Origin must be echoed in Access-Control-Allow-Origin.
# - If CORS_ORIGINS is set (comma-separated), use that explicit list.
# - Otherwise allow any http://localhost:PORT and http://127.0.0.1:PORT (local dev).
_cors_env = (os.getenv("CORS_ORIGINS") or "").strip()
if _cors_env:
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class UploadResponse(BaseModel):
    """JSON body returned on successful POST /upload."""

    ok: bool = True
    docId: str = Field(description="Session id for POST /chat")
    fileName: str
    size: int = Field(description="Original file size in bytes")
    type: str = Field(description="Client-provided MIME type")
    textLength: int = Field(
        description="Length of extracted text stored server-side (capped by MAX_CONTEXT_CHARS)"
    )
    chunkCount: int = Field(
        description="Number of text chunks derived for later retrieval / RAG"
    )
    embeddingDim: int = Field(
        default=0,
        description="Vector size for each chunk embedding (0 if no chunks)",
    )


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 15 MB)")

    fname = file.filename or "document"
    try:
        text = extract_text(fname, raw).strip()
    except Exception as e:
        logger.exception("extract_text failed")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read file: {e!s}",
        ) from e

    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from this file.",
        )

    stored_text = text[:MAX_CONTEXT_CHARS]
    chunks = split_text_into_chunks(stored_text)
    chunk_payload = [c.to_store_dict() for c in chunks]

    chunk_texts = [c["text"] for c in chunk_payload]
    embedding_vectors: list[list[float]] = []
    try:
        embedding_vectors = embed_texts(chunk_texts)
    except RuntimeError as e:
        # Missing keys, wrong venv, or no embedding deployment — still store doc; chat uses full text.
        logger.warning("Embeddings skipped (upload still succeeds): %s", e)
    except Exception as e:
        logger.exception("Embeddings failed; continuing without vectors: %s", e)

    embedding_dim = len(embedding_vectors[0]) if embedding_vectors else 0

    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "text": stored_text,
        "file_name": fname,
        "chunks": chunk_payload,
        "embeddings": embedding_vectors,
    }
    logger.info(
        "Stored document %s (%s chars, %s chunks, emb_dim=%s)",
        doc_id,
        len(stored_text),
        len(chunk_payload),
        embedding_dim,
    )

    return UploadResponse(
        ok=True,
        docId=doc_id,
        fileName=fname,
        size=len(raw),
        type=file.content_type or "application/octet-stream",
        textLength=len(stored_text),
        chunkCount=len(chunk_payload),
        embeddingDim=embedding_dim,
    )


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    docId: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("docId", "doc_id"),
    )


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


@app.post("/chat")
def chat(body: ChatBody) -> dict[str, str]:
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is required")

    doc_id = (body.docId or "").strip()
    if not doc_id:
        raise HTTPException(
            status_code=400,
            detail="Missing docId in request body. Expected JSON: { \"message\": \"...\", \"docId\": \"<uuid>\" }.",
        )
    if doc_id not in DOCUMENT_STORE:
        raise HTTPException(
            status_code=400,
            detail="Document session expired or server was restarted — upload the file again. (docId not found)",
        )

    entry = DOCUMENT_STORE[doc_id]
    chunks = entry.get("chunks") or []
    embs = entry.get("embeddings") or []

    context: str
    if chunks and embs and len(chunks) == len(embs):
        try:
            context = retrieve_context(text, chunks, embs)
        except Exception as e:
            logger.warning("RAG retrieval failed, using full document: %s", e)
            context = ""
        if not (context and context.strip()):
            context = str(entry.get("text", ""))
    else:
        context = str(entry.get("text", ""))

    # Local/dev without Azure chat: set CHAT_MOCK=1 in .env → 200 + stub reply (no 503).
    if _env_truthy("CHAT_MOCK"):
        preview = context[:800] + ("…" if len(context) > 800 else "")
        return {
            "reply": (
                "[Mock LLM — set CHAT_MOCK=0 and AZURE_OPENAI_URL / AZURE_OPENAI_KEY for real answers]\n\n"
                f"Your question: {text}\n\n"
                f"Context passed to the model (truncated):\n{preview or '(empty)'}"
            )
        }

    try:
        chain = get_answer_chain()
        reply = chain.invoke({"context": context, "question": text})
    except RuntimeError as e:
        logger.warning("%s", e)
        detail = str(e)
        if "AZURE_OPENAI" in detail or "LangChain" in detail:
            detail += (
                " — Or set CHAT_MOCK=1 in backend/.env for a stub response without Azure."
            )
        raise HTTPException(status_code=503, detail=detail) from e
    except Exception as e:
        logger.exception("chat invoke failed")
        raise HTTPException(
            status_code=502,
            detail=f"Model error: {e!s}",
        ) from e

    return {"reply": str(reply).strip()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
