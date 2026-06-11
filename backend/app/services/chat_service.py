from __future__ import annotations

from typing import Any

from app.core.config import OPENAI_BASE_URL, OPENAI_MODEL, RAG_TOP_K
from app.rag.retriever import retrieve
from app.services import llm


async def answer(question: str, destination_id: int | None = None, session_id: str = "default") -> dict[str, Any]:
    contexts = retrieve(question, top_k=RAG_TOP_K)
    text, error = await llm.complete(question, contexts)
    return {
        "answer": text,
        "retrieval": {
            "top_k": RAG_TOP_K,
            "contexts": contexts,
            "used_llm": error is None and llm.configured(),
            "llm_error": error,
            "model": OPENAI_MODEL,
            "base_url": OPENAI_BASE_URL,
            "destination_id": destination_id,
            "session_id": session_id,
        },
    }
