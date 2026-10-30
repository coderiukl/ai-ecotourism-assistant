from __future__ import annotations

from typing import Any

from app.core.config import DEBUG_RETRIEVAL, OPENAI_MODEL, RAG_TOP_K
from app.db import postgres
from app.rag.retriever import retrieve
from app.services import llm, sunworld_search
from app.services.query_understanding import understand_query


def related_media(
    destination: dict[str, Any] | None,
    contexts: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, str]]:
    destinations = list(postgres.destinations().values())
    by_code = {
        str(item.get("dest_code") or "").strip(): item
        for item in destinations
        if item.get("dest_code")
    }
    candidates: list[dict[str, Any]] = []

    if destination:
        candidates.append(destination)

    media: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for context in contexts:
        url = str(context.get("image_url") or "").strip()
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        media.append(
            {
                "url": url,
                "caption": str(context.get("title") or "Ảnh từ Sun World").strip(),
                "alt": str(context.get("title") or "Ảnh địa điểm Núi Bà Đen").strip(),
                "source_url": str(context.get("source_url") or "").strip(),
                "destination": str(context.get("title") or "").strip(),
            }
        )

        if len(media) >= limit:
            return media

    for context in contexts:
        item = by_code.get(str(context.get("dest_code") or "").strip())
        if item:
            candidates.append(item)

    for item in candidates:
        url = str(item.get("image_url") or "").strip()
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        media.append(
            {
                "url": url,
                "caption": str(item.get("image_caption") or item.get("name") or "").strip(),
                "alt": str(item.get("image_alt") or item.get("name") or "Ảnh địa điểm").strip(),
                "source_url": str(item.get("source_url") or "").strip(),
                "destination": str(item.get("name") or "").strip(),
            }
        )

        if len(media) >= limit:
            break

    return media


def live_sources(contexts: list[dict[str, Any]]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for context in contexts:
        if context.get("type") != "live_sunworld":
            continue
        url = str(context.get("source_url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(
            {
                "title": str(context.get("title") or "Sun World Ba Den Mountain"),
                "url": url,
                "last_updated": str(context.get("last_updated") or ""),
            }
        )

        if len(sources) >= 2:
            break

    return sources


# Volatile questions always need a current external check. Other substantive
# questions also search the official source so the model can supplement local
# RAG data; short social messages are skipped to avoid irrelevant links.
VOLATILE_INTENTS = {"price", "opening_hours", "events_culture", "contact", "facilities"}
SOCIAL_MESSAGES = {
    "alo",
    "cảm ơn",
    "cam on",
    "chào",
    "chào bạn",
    "hello",
    "hi",
    "hey",
    "xin chào",
}


def should_search_external(question: str, intent: str) -> bool:
    normalized = " ".join(str(question or "").casefold().split())
    if not normalized or normalized in SOCIAL_MESSAGES:
        return False
    return intent in VOLATILE_INTENTS or len(normalized) >= 6


async def contexts_for_question(
    question: str,
    destination_id: int | None,
    intent: str,
    destination_name: str | None = None,
) -> list[dict[str, Any]]:
    local_contexts = retrieve(
        question,
        top_k=RAG_TOP_K,
        destination_id=destination_id,
        intent=intent,
    )
    live_contexts = []
    if should_search_external(question, intent):
        live_contexts = await sunworld_search.search(question, destination_name)
    seen_ids: set[str] = set()
    merged: list[dict[str, Any]] = []

    for context in [*live_contexts, *local_contexts]:
        context_id = str(context.get("id") or context.get("source_url") or "")
        if not context_id or context_id in seen_ids:
            continue
        seen_ids.add(context_id)
        merged.append(context)

    return merged


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
        "media": metadata.get("media") or [],
        "sources": metadata.get("sources") or [],
    }

    if DEBUG_RETRIEVAL:
        public["contexts"] = metadata.get("contexts") or []
        public["llm_error"] = metadata.get("llm_error")

    return public


async def answer(
    question: str,
    destination_id: int | None = None,
    session_id: str = "default",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
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
            "media": related_media(destination, []),
        }
        return {
            "answer": query_info.clarify_question,
            "retrieval": public_retrieval(metadata),
            "metadata": metadata,
        }
    
    contexts = await contexts_for_question(
        question,
        destination_id,
        query_info.intent,
        destination_name,
    )
    text, error = await llm.complete(question, contexts, destination, history)

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
        "media": related_media(destination, contexts),
        "sources": live_sources(contexts),
    }

    return {
        "answer": text,
        "retrieval": public_retrieval(metadata),
        "metadata": metadata,
    }
