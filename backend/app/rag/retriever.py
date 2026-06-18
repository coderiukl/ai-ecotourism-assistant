from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

from app.core.config import RAG_TOP_K
from app.rag.embeddings import backend_name, embed_text
from app.rag import vector_store
from app.db import postgres

_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))

def _normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().split())

def _destination_scope(destination_id: int | None) -> dict[str, Any] | None:
    if destination_id is None:
        return None
    
    destination = postgres.destinations().get(destination_id)

    if not destination:
        return {"id": destination_id, "missing": True}
    
    return {
        "id": destination_id,
        "dest_code": str(destination.get("dest_code") or "").strip(),
        "name": str(destination.get("name") or "").strip(),
        "destination": destination,
    }


def _matches_destination(document: dict[str, Any], scope: dict[str, Any] | None) -> bool:
    if not scope:
        return True
    
    if scope.get("missing"):
        return False

    doc_dest_code = str(document.get("dest_code") or "").strip()
    dest_code = str(scope.get("dest_code") or "").strip()

    if dest_code and doc_dest_code == dest_code:
        return True
    
    if doc_dest_code:
        return False

    text = _normalize(f"{document.get('title', '')}\n{document.get('text', '')}")
    name = _normalize(str(scope.get('name') or ""))

    return bool((dest_code and _normalize(dest_code) in text) or (name and name in text))

def _query_text(question: str, scope: dict[str, Any] | None) -> str:
    name = str(scope.get("name") or "") if scope else ""
    return f"{name}. {question}" if name else question

def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _lexical_bonus(question: str, text: str) -> float:
    q = _tokens(question)
    if not q:
        return 0.0
    return len(q & _tokens(text)) / math.sqrt(len(q))


def _intent_bonus(question: str, document: dict[str, Any]) -> float:
    tokens = _tokens(question)
    sheet = str(document.get("sheet") or document.get("type") or "")
    text = str(document.get("text") or "").lower()
    bonus = 0.0

    if tokens & {"chơi", "tham", "quan", "hoạt", "động", "trải", "nghiệm", "check", "in"}:
        if sheet in {"activities", "destinations", "travel_tips", "photo_spots", "itineraries"}:
            bonus += 1.2

    if tokens & {"giá", "vé", "combo", "buffet", "cáp", "treo", "tiền"}:
        if sheet in {"services_pricing", "contact_info"}:
            bonus += 1.5

    if tokens & {"giờ", "mở", "cửa", "lịch", "vận", "hành"}:
        if sheet in {"operation_hours", "contact_info"}:
            bonus += 1.5

    if tokens & {"đường", "đi", "xe", "bus", "di", "chuyển", "bản", "đồ"}:
        if sheet in {"transportation", "maps_navigation", "destinations"}:
            bonus += 1.2

    if tokens & {"ăn", "uống", "đặc", "sản", "khách", "sạn", "ở"}:
        if sheet == "food_stay":
            bonus += 1.3

    if "truy xuất dữ liệu từ sheet" in text:
        bonus -= 1.0

    return bonus


@lru_cache(maxsize=1)
def _memory_index() -> list[dict[str, Any]]:
    return [{**document, "embedding": embed_text(document["text"])} for document in postgres.rag_documents()]

def _lexical_query(question: str, top_k: int, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query_text = _query_text(question, scope)
    scored = []

    for document in postgres.rag_documents():
        if not _matches_destination(document, scope):
            continue

        score = _lexical_bonus(query_text, document["text"]) + _intent_bonus(question, document)
        scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    
    return [
        {
            "id": doc["id"],
            "score": round(score, 4),
            "sheet": doc.get("sheet"),
            "type": doc.get("type"),
            "title": doc.get("title"),
            "dest_code": doc.get("dest_code"),
            "source_url": doc.get("source_url"),
            "text": doc.get("text"),
        }
        for score, doc in scored[:top_k]
        if score > 0
    ]


def _rerank(question: str, contexts: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    scored = []

    for context in contexts:
        score = (
            float(context.get("score") or 0)
            + _lexical_bonus(question, str(context.get("text") or ""))
            + _intent_bonus(question, context)
        )
        scored.append((score, context))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [{**context, "score": round(score, 4)} for score, context in scored[:top_k]]


def retrieve(question: str, top_k: int = RAG_TOP_K, destination_id: int | None = None, intent: str = "general") -> list[dict[str, Any]]:
    scope = _destination_scope(destination_id)
    scoped_query = _query_text(question, scope)

    preferred_sheets = {
        "price": {"services_pricing"},
        "opening_hours": {"operation_hours"},
        "activities": {"activities", "destinations", "travel_tips", "photo_spots"},
        "transport": {"transportation", "maps_navigation", "destinations"},
        "itinerary": {"itineraries", "activities", "destinations"},
        "general": set(),
    }

    try:
        contexts = vector_store.query(
            scoped_query,
            top_k=max(top_k * 6, 30),
            dest_code=None if not scope else scope.get("dest_code"),
        )

        contexts = [context for context in contexts if _matches_destination(context, scope)]
       
        sheets = preferred_sheets.get(intent, set())

        if sheets: 
            contexts = sorted(
                contexts,
                key=lambda context: (
                    1 if str(context.get("sheet") or context.get("type") or "") in sheets else 0,
                    float(context.get("score") or 0),
                ),
                reverse=True,
            )
        if contexts:
            return _rerank(question, contexts, top_k)
        
    except Exception:
        pass
    
    return _lexical_query(question, top_k, scope)


def status() -> dict[str, Any]:
    return {
        **postgres.data_stats(),
        **vector_store.status(),
        "embedding_backend": backend_name(),
    }
