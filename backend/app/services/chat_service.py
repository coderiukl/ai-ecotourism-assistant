from __future__ import annotations

from typing import Any

from app.core.config import OPENAI_BASE_URL, OPENAI_MODEL, RAG_TOP_K
from app.rag.retriever import retrieve
from app.services import llm
from app.services.excel_loader import destinations


async def answer(question: str, destination_id: int | None = None, session_id: str = "default") -> dict[str, Any]:
    destination = destinations().get(destination_id) if destination_id else None
    contexts = retrieve(question, top_k=RAG_TOP_K, destination_id=destination_id)
    text, error = await llm.complete(question, contexts, destination)
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
            "destination": destination,
            "session_id": session_id,
        },
    }
