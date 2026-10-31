from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from typing import Any

from app.core.config import DEBUG_RETRIEVAL, OPENAI_MODEL, RAG_TOP_K
from app.db import postgres
from app.rag.retriever import retrieve
from app.services import llm, sunworld_search, web_search
from app.services.query_understanding import understand_query

logger = logging.getLogger(__name__)


def related_media(
    destination: dict[str, Any] | None,
    contexts: list[dict[str, Any]],
    limit: int = 3,
    intent: str | None = None,
) -> list[dict[str, str]]:
    if intent is not None and intent not in MEDIA_INTENTS:
        return []

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


def live_sources(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for context in contexts:
        if context.get("type") not in {"live_sunworld", "live_web", "stored_web"}:
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
                "citation_index": context.get("citation_index"),
                "source_type": str(context.get("type") or ""),
            }
        )

        if len(sources) >= 5:
            break

    return sources


# Only volatile questions (price, hours, events, contact, facilities) justify
# a live external check and the "Cập nhật từ Sun World" source link that
# comes with it — every other question stays on local RAG data so the chat
# doesn't clutter every reply with links/sources it doesn't need.
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

# Media (photo carousel) is only useful when the question is actually about
# seeing/visiting/experiencing the place — attaching it to every answer
# (e.g. a price or contact question) just clutters the chat bubble.
MEDIA_INTENTS = {"activities", "photography", "itinerary", "events_culture", "general"}

_GENERIC_DESTINATION_ALIASES = {
    "ba den",
    "dia diem",
    "khu du lich",
    "nui ba",
    "nui ba den",
    "tay ninh",
}

_LOCAL_SCOPE_MARKERS = (
    "dia diem nay",
    "ngay day",
    "o day",
    "tai day",
    "cho nay",
)

_GLOBAL_SCOPE_MARKERS = (
    "cac dia diem",
    "cac tuyen",
    "khu du lich",
    "nui ba den",
    "tat ca",
    "toan bo",
    "toan khu",
    "tong cong",
    "tong gia",
)


def is_global_destination_question(question: str) -> bool:
    """Return true when a question is about the whole tourism area.

    The destination selected in the UI is conversational context, not a hard
    search boundary. Site-wide services such as cable cars must remain
    queryable from any destination page.
    """
    normalized = _normalize_place_name(question)
    if not normalized or any(marker in normalized for marker in _LOCAL_SCOPE_MARKERS):
        return False

    if any(marker in normalized for marker in _GLOBAL_SCOPE_MARKERS):
        return True

    # Cable-car routes and their tickets apply across the complex rather than
    # to the attraction card from which the visitor opened the chatbot.
    return "cap treo" in normalized


def _normalize_place_name(value: str) -> str:
    """Make Vietnamese destination names comparable to unaccented user input."""
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _destination_aliases(name: str) -> set[str]:
    normalized = _normalize_place_name(name)
    aliases = {normalized}

    # Slash/dash-separated names commonly contain the short name visitors use,
    # for example "Linh Sơn Tiên Thạch Tự / Chùa Bà" -> "chua ba".
    aliases.update(
        _normalize_place_name(part)
        for part in re.split(r"\s*(?:/|[-–—])\s*", name)
    )

    # Visitors also tend to omit formal prefixes ("Tôn tượng Bồ Tát Di Lặc"
    # becomes "Di Lặc"). Unique two-or-more-word suffixes cover that case while
    # avoiding ambiguous single words such as "chùa" or "tượng".
    words = normalized.split()
    aliases.update(" ".join(words[index:]) for index in range(1, max(1, len(words) - 1)))

    return {
        alias
        for alias in aliases
        if len(alias.split()) >= 2 and alias not in _GENERIC_DESTINATION_ALIASES
    }


def resolve_destination(
    question: str,
    selected_destination_id: int | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Resolve an explicitly named destination, otherwise retain the UI selection."""
    destinations = postgres.destinations()
    aliases_by_destination = {
        destination_id: _destination_aliases(str(destination.get("name") or ""))
        for destination_id, destination in destinations.items()
    }
    alias_owners: dict[str, set[int]] = {}

    for destination_id, aliases in aliases_by_destination.items():
        for alias in aliases:
            alias_owners.setdefault(alias, set()).add(destination_id)

    def match(text: str) -> tuple[int, dict[str, Any]] | None:
        normalized_text = f" {_normalize_place_name(text)} "
        matches: list[tuple[int, int, dict[str, Any]]] = []

        for destination_id, aliases in aliases_by_destination.items():
            for alias in aliases:
                if len(alias_owners[alias]) == 1 and f" {alias} " in normalized_text:
                    matches.append((len(alias), destination_id, destinations[destination_id]))

        if not matches:
            return None

        _, destination_id, destination = max(matches, key=lambda item: item[0])
        return destination_id, destination

    current_match = match(question)
    if current_match:
        return current_match

    if is_global_destination_question(question):
        return None, None

    # Keep a newly mentioned place active for natural follow-ups such as
    # "đi tới đó thế nào?", even when the UI was opened from another place.
    for item in reversed(history or []):
        if str(item.get("role") or "").strip().lower() != "user":
            continue
        history_match = match(str(item.get("content") or ""))
        if history_match:
            return history_match

    destination = destinations.get(selected_destination_id) if selected_destination_id else None
    return selected_destination_id, destination


def should_search_external(question: str, intent: str) -> bool:
    normalized = " ".join(str(question or "").casefold().split())
    if not normalized or normalized in SOCIAL_MESSAGES:
        return False
    return intent in VOLATILE_INTENTS


def should_search_web(question: str, intent: str) -> bool:
    normalized = " ".join(str(question or "").casefold().split())
    if not normalized:
        return False

    # Auto mode: every substantive visitor question gets a live web lookup.
    # Skip short social turns because searching for greetings/thanks only adds
    # latency and provider cost without improving the answer.
    social_prefixes = (
        "chào",
        "xin chào",
        "hello",
        "hi",
        "hey",
        "cảm ơn",
        "cam on",
        "tạm biệt",
        "tam biet",
    )
    is_short_social_turn = len(normalized.split()) <= 6 and any(
        normalized.startswith(prefix) for prefix in social_prefixes
    )
    return normalized not in SOCIAL_MESSAGES and not is_short_social_turn


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
    search_tasks = []
    if should_search_external(question, intent):
        search_tasks.append(sunworld_search.search(question, destination_name))
    if should_search_web(question, intent):
        search_tasks.append(web_search.search(question, destination_name))

    search_results = await asyncio.gather(
        postgres.search_web_knowledge(question),
        *search_tasks,
        return_exceptions=True,
    )
    stored_result = search_results[0]
    stored_contexts = stored_result if isinstance(stored_result, list) else []
    if isinstance(stored_result, Exception):
        logger.warning("Stored web knowledge retrieval skipped: %s", stored_result)

    live_contexts: list[dict[str, Any]] = []
    for result in search_results[1:]:
        if isinstance(result, list):
            live_contexts.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Live source retrieval skipped: %s", result)

    if live_contexts:
        try:
            await postgres.save_web_knowledge(question, live_contexts)
        except Exception as exc:
            logger.warning("Web knowledge persistence skipped: %s", exc)
    seen_ids: set[str] = set()
    merged: list[dict[str, Any]] = []

    # Keep the prompt varied: current web sources first, then a small number of
    # saved sources and local RAG documents before filling remaining slots.
    ordered_contexts = [
        *live_contexts[:3],
        *stored_contexts[:2],
        *local_contexts[:2],
        *live_contexts[3:],
        *stored_contexts[2:],
        *local_contexts[2:],
    ]
    for context in ordered_contexts:
        # The same official page may be returned by both the Sun World crawler
        # and the general search provider. Prefer URL identity so it is cited
        # only once even when provider-specific IDs differ.
        context_id = str(context.get("source_url") or context.get("id") or "").strip().casefold()
        if not context_id or context_id in seen_ids:
            continue
        seen_ids.add(context_id)
        merged.append(context)

    citation_index = 0
    for context in merged:
        if context.get("type") in {"live_sunworld", "live_web", "stored_web"}:
            citation_index += 1
            context["citation_index"] = citation_index

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
    requested_destination_id = destination_id
    destination_id, destination = resolve_destination(question, destination_id, history)
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
            "requested_destination_id": requested_destination_id,
            "destination": destination,
            "session_id": session_id,
            "intent": query_info.intent,
            "clarified": True,
            "media": related_media(destination, [], intent=query_info.intent),
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
        "requested_destination_id": requested_destination_id,
        "destination": destination,
        "session_id": session_id,
        "intent": query_info.intent,
        "clarified": False,
        "media": related_media(destination, contexts, intent=query_info.intent),
        "sources": live_sources(contexts),
    }

    return {
        "answer": text,
        "retrieval": public_retrieval(metadata),
        "metadata": metadata,
    }
