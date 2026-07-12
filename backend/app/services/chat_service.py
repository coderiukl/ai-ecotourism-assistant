from __future__ import annotations

from typing import Any

from app.core.config import DEBUG_RETRIEVAL, OPENAI_MODEL, RAG_TOP_K
from app.db import postgres
from app.rag.retriever import retrieve
from app.services import llm
from app.services.query_understanding import understand_query


def public_retrieval(metadata: dict[str, Any]) -> dict[str, Any]:
    public = {
        "top_k": metadata.get("top_k", 0),
        "context_count": len(metadata.get("contexts") or []),
        "used_llm": bool(metadata.get("used_llm")),
        "model": metadata.get("model"),
        "destination_id": metadata.get("destination_id"),
        "destination": metadata.get("destination"),
        "session_id": metadata.get("session_id"),
        "intent": metadata.get("intent"),
        "clarified": bool(metadata.get("clarified")),
    }

    if DEBUG_RETRIEVAL:
        public["contexts"] = metadata.get("contexts") or []
        public["llm_error"] = metadata.get("llm_error")

    return public


async def answer(question: str, destination_id: int | None = None, session_id: str = "default") -> dict[str, Any]:
    destination = postgres.destinations().get(destination_id) if destination_id else None
    destination_name = destination.get("name") if destination else None

    query_info = understand_query(question, destination_name)

    if query_info.should_clarify:
        metadata = {
            "top_k": 0,
            "contexts": [],
            "used_llm": False,
            "llm_error": None,
            "model": OPENAI_MODEL,
            "destination_id": destination_id,
            "destination": destination,
            "session_id": session_id,
            "intent": query_info.intent,
            "clarified": True,
        }
        return {
            "answer": query_info.clarify_question,
            "retrieval": public_retrieval(metadata),
            "metadata": metadata,
        }
    
    contexts = retrieve(question, top_k=RAG_TOP_K, destination_id=destination_id, intent=query_info.intent)
    text, error = await llm.complete(question, contexts, destination)

    metadata = {
        "top_k": RAG_TOP_K,
        "contexts": contexts,
        "used_llm": error is None and llm.configured(),
        "llm_error": error,
        "model": OPENAI_MODEL,
        "destination_id": destination_id,
        "destination": destination,
        "session_id": session_id,
        "intent": query_info.intent,
        "clarified": False,
    }

    return {
        "answer": text,
        "retrieval": public_retrieval(metadata),
        "metadata": metadata,
    }
