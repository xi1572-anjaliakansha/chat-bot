from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ.setdefault(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; NoshDocChat/1.0)",
)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_CONTEXT_CHARS = 120_000

# doc_id -> {"text": str, "file_name": str}
DOCUMENT_STORE: dict[str, dict[str, str]] = {}

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

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import AzureChatOpenAI

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
                "You are a helpful assistant. Answer the user's question using "
                "only the document content below when it is relevant. If the "
                "answer is not in the document, say so clearly and offer what "
                "you can infer safely. Be concise.\n\n--- Document ---\n{context}\n--- End ---",
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


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
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

    doc_id = str(uuid.uuid4())
    DOCUMENT_STORE[doc_id] = {
        "text": text[:MAX_CONTEXT_CHARS],
        "file_name": fname,
    }
    logger.info("Stored document %s (%s chars)", doc_id, len(DOCUMENT_STORE[doc_id]["text"]))

    return {
        "ok": True,
        "docId": doc_id,
        "fileName": fname,
        "size": len(raw),
        "type": file.content_type or "application/octet-stream",
    }


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    docId: str | None = None


@app.post("/chat")
def chat(body: ChatBody) -> dict[str, str]:
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is required")

    doc_id = (body.docId or "").strip()
    if not doc_id or doc_id not in DOCUMENT_STORE:
        raise HTTPException(
            status_code=400,
            detail="Unknown or missing document. Upload a file first.",
        )

    entry = DOCUMENT_STORE[doc_id]
    context = entry["text"]

    try:
        chain = get_answer_chain()
        reply = chain.invoke({"context": context, "question": text})
    except RuntimeError as e:
        logger.warning("%s", e)
        raise HTTPException(
            status_code=503,
            detail=str(e),
        ) from e
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
