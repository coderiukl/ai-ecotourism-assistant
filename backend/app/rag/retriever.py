from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

from app.core.config import RAG_TOP_K
from app.rag.embeddings import backend_name, embed_text
from app.rag import vector_store
from app.services.excel_loader import rag_documents, stats as data_stats

_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


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
    return [{**document, "embedding": embed_text(document["text"])} for document in rag_documents()]


def _memory_query(question: str, top_k: int) -> list[dict[str, Any]]:
    query_embedding = embed_text(question)
    scored = []
    for document in _memory_index():
        score = _cosine(query_embedding, document["embedding"]) + _lexical_bonus(question, document["text"]) + _intent_bonus(question, document)
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
    ]


def _rerank(question: str, contexts: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    scored = []
    for context in contexts:
        score = float(context.get("score") or 0) + _lexical_bonus(question, str(context.get("text") or "")) + _intent_bonus(question, context)
        scored.append((score, context))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{**context, "score": round(score, 4)} for score, context in scored[:top_k]]


def retrieve(question: str, top_k: int = RAG_TOP_K) -> list[dict[str, Any]]:
    try:
        contexts = vector_store.query(question, top_k=max(top_k * 4, 20))
        if contexts:
            return _rerank(question, contexts, top_k)
    except Exception:
        pass
    return _memory_query(question, top_k)


def status() -> dict[str, Any]:
    return {
        **data_stats(),
        **vector_store.status(),
        "embedding_backend": backend_name(),
    }
