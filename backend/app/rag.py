"""RAG pipeline for Nui Ba Den chatbot.

Delegates business rules to domain/:
  - query classification (is_price_related, is_route_related, etc.)
  - price analysis (build_price_answer)
  - retrieval scoring (intent_bonus, keyword_bonus)
  - field extraction (extract_fields, field)

This file owns only the pipeline orchestration, document building,
embedding, and Claude API interaction.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Tuple

from anthropic import Anthropic

from .config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_MAX_RETRIES,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_TIMEOUT_SECONDS,
    ANTHROPIC_USER_AGENT,
    ANTHROPIC_VERSION,
    RAG_EMBEDDING_DIM,
    RAG_EMBEDDING_MODEL,
    RAG_TOP_K,
    RAG_USE_SENTENCE_TRANSFORMER,
)
from .data_loader import (
    ACTIVITIES,
    ALL_SHEETS,
    DESTINATIONS,
    FAQ_LIST,
    KB_LIST,
    MEDIA_ASSETS,
    SERVICES_PRICING,
)
from .domain import (
    GENERIC_ALIAS_TOKENS,
    ACTION_ALIAS_TOKENS,
    extract_fields,
    field,
    intent_bonus,
    is_activity_related,
    is_hours_related,
    is_price_related,
    is_route_related,
    keyword_bonus,
    query_tokens,
    resolve_target_codes,
    slugify,
)
from .memory import session_store
from .prompts import build_messages, build_system_prompt, fallback_rag_answer
from .query_guard import check_query_clarity
from .text_utils import clean_text
from .vector_store import vector_store_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_embedding_model = None
_embedding_backend = None
_rag_documents = None
_rag_index = None
_vector_store_backend = None
_last_claude_error = None
_destination_aliases = None

# ---------------------------------------------------------------------------
# Document building
# ---------------------------------------------------------------------------

def _doc_text(title: str, fields: List[Tuple[str, str]]) -> str:
    parts = [title]
    for label, value in fields:
        value = clean_text(value)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def build_rag_documents() -> List[Dict[str, Any]]:
    documents = []

    for destination in DESTINATIONS.values():
        documents.append({
            "id": f"destination:{destination.get('dest_code')}",
            "type": "destination",
            "title": destination.get("name"),
            "source_url": destination.get("image_source_url") or destination.get("source_url"),
            "destination_id": destination.get("id"),
            "dest_code": destination.get("dest_code"),
            "text": _doc_text(
                f"Địa điểm: {destination.get('name')}",
                [
                    ("Mã", destination.get("dest_code")),
                    ("Danh mục", destination.get("category")),
                    ("Vị trí", destination.get("location")),
                    ("Mô tả ngắn", destination.get("short_description")),
                    ("Chi tiết", destination.get("description_detail")),
                    ("Điểm nổi bật", destination.get("highlight")),
                    ("Thời điểm đẹp", destination.get("best_time")),
                    ("Thời lượng", destination.get("estimated_duration")),
                    ("Loại hình", destination.get("travel_type")),
                    ("Độ khó", destination.get("difficulty_level")),
                    ("Di chuyển", destination.get("transport")),
                ],
            ),
        })

    for dest_code, media in MEDIA_ASSETS.items():
        documents.append({
            "id": f"media_asset:{media.get('media_id')}",
            "type": "media_asset",
            "title": media.get("image_caption") or media.get("image_alt"),
            "source_url": media.get("image_source_url"),
            "dest_code": dest_code,
            "text": _doc_text(
                f"Hình ảnh điểm đến: {media.get('image_caption') or dest_code}",
                [
                    ("Mã điểm đến", dest_code),
                    ("Ảnh", media.get("image_url")),
                    ("Chú thích", media.get("image_caption")),
                    ("Mô tả ảnh", media.get("image_alt")),
                ],
            ),
        })

    for service in SERVICES_PRICING:
        documents.append({
            "id": f"service_pricing:{service.get('service_id') or service.get('pricing_id')}",
            "type": "service_pricing",
            "title": service.get("service_name"),
            "source_url": service.get("source_url"),
            "dest_code": service.get("dest_id") or service.get("dest_code"),
            "text": _doc_text(
                f"Dịch vụ / giá vé: {service.get('service_name')}",
                [
                    ("Mã điểm đến", service.get("dest_id") or service.get("dest_code")),
                    ("service_name", service.get("service_name")),
                    ("Service category", service.get("service_category") or service.get("service_type")),
                    ("Area", service.get("area")),
                    ("Direction", service.get("direction")),
                    ("Valid day type", service.get("valid_day_type")),
                    ("Customer type", service.get("customer_type")),
                    ("Price VND", service.get("price_vnd")),
                    ("Giá người lớn", service.get("adult_price_vnd")),
                    ("Giá trẻ em", service.get("child_price_vnd")),
                    ("Giá combo", service.get("combo_price_vnd")),
                    ("Conditions", service.get("conditions")),
                    ("Included services", service.get("included_services")),
                    ("Excluded services", service.get("excluded_services")),
                    ("Ghi chú", service.get("note")),
                    ("Answer hint", service.get("answer_hint")),
                    ("Query keywords", service.get("query_keywords")),
                    ("Ngày cập nhật", service.get("updated_date")),
                    ("Source update", service.get("source_update")),
                    ("Xác minh", service.get("verification_note")),
                ],
            ),
        })

    for activity in ACTIVITIES:
        documents.append({
            "id": f"activity:{activity.get('activity_id')}",
            "type": "activity",
            "title": activity.get("activity_name"),
            "source_url": activity.get("source_url"),
            "dest_code": activity.get("dest_id") or activity.get("dest_code"),
            "text": _doc_text(
                f"Hoạt động trải nghiệm: {activity.get('activity_name')}",
                [
                    ("Mã điểm đến", activity.get("dest_id") or activity.get("dest_code")),
                    ("Loại hoạt động", activity.get("activity_type")),
                    ("Độ khó", activity.get("difficulty_level")),
                    ("Thời lượng", activity.get("estimated_duration")),
                    ("Thời điểm đẹp", activity.get("best_time")),
                    ("Lưu ý an toàn", activity.get("safety_note")),
                ],
            ),
        })

    for faq in FAQ_LIST:
        documents.append({
            "id": f"faq:{faq.get('faq_id')}",
            "type": "faq",
            "title": faq.get("question"),
            "source_url": faq.get("source_url"),
            "text": _doc_text(
                f"FAQ: {faq.get('question')}",
                [
                    ("Chủ đề", faq.get("topic")),
                    ("Câu hỏi", faq.get("question")),
                    ("Trả lời", faq.get("answer")),
                    ("Intent", faq.get("intent")),
                ],
            ),
        })

    for kb in KB_LIST:
        documents.append({
            "id": f"kb:{kb.get('kb_id')}",
            "type": "knowledge_base",
            "title": kb.get("title"),
            "source_url": kb.get("source_url"),
            "dest_code": kb.get("dest_code"),
            "text": _doc_text(
                f"Knowledge base: {kb.get('title')}",
                [
                    ("Chủ đề", kb.get("topic")),
                    ("Mã điểm đến", kb.get("dest_code")),
                    ("Nội dung", kb.get("content")),
                    ("Từ khóa", kb.get("keywords")),
                ],
            ),
        })

    return documents


def get_rag_documents() -> List[Dict[str, Any]]:
    global _rag_documents
    if _rag_documents is None:
        _rag_documents = build_rag_documents()
    return _rag_documents

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def get_embedding_model():
    global _embedding_backend, _embedding_model
    if _embedding_backend:
        return _embedding_model

    if not RAG_USE_SENTENCE_TRANSFORMER:
        _embedding_model = None
        _embedding_backend = "hash_fallback"
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer
        try:
            _embedding_model = SentenceTransformer(RAG_EMBEDDING_MODEL, local_files_only=True)
        except TypeError:
            _embedding_model = SentenceTransformer(RAG_EMBEDDING_MODEL)
        _embedding_backend = "minilm"
    except Exception:
        _embedding_model = None
        _embedding_backend = "hash_fallback"

    return _embedding_model


def _fit_embedding_dimension(vector):
    vector = [float(value) for value in vector]
    if len(vector) > RAG_EMBEDDING_DIM:
        vector = vector[:RAG_EMBEDDING_DIM]
    elif len(vector) < RAG_EMBEDDING_DIM:
        vector = vector + [0.0] * (RAG_EMBEDDING_DIM - len(vector))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _hash_embedding(text):
    vector = [0.0] * RAG_EMBEDDING_DIM
    for token in re.findall(r"\w+", slugify(text)):
        vector[hash(token) % RAG_EMBEDDING_DIM] += 1.0
    return _fit_embedding_dimension(vector)


def embed_text(text):
    model = get_embedding_model()
    if _embedding_backend == "minilm" and model:
        vector = model.encode(text, normalize_embeddings=True)
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        return _fit_embedding_dimension(vector)
    return _hash_embedding(text)


def _cosine_similarity(left, right):
    return sum(a * b for a, b in zip(left, right))


def get_rag_index():
    global _rag_index
    if _rag_index is None:
        _rag_index = [
            {**document, "embedding": embed_text(document["text"])}
            for document in get_rag_documents()
        ]
    return _rag_index

# ---------------------------------------------------------------------------
# Destination resolution
# ---------------------------------------------------------------------------

def _dest_code_from_record(record):
    for key in ("dest_id", "dest_code", "place_id", "destination_id"):
        value = clean_text(record.get(key))
        if re.fullmatch(r"TN\d{3}", value or "", re.I):
            return value.upper()
    return ""


def _tokenize_slug(value):
    return [token for token in slugify(value).split("_") if token]


def _is_generic_alias(tokens):
    if len(tokens) < 2:
        return True
    return set(tokens).issubset(GENERIC_ALIAS_TOKENS | ACTION_ALIAS_TOKENS)


def _alias_variants(value):
    variants = set()
    raw_parts = re.split(r"[/|\-]", str(value or ""))
    raw_parts.append(value)
    for part in raw_parts:
        tokens = _tokenize_slug(part)
        if _is_generic_alias(tokens):
            continue
        variants.add(" ".join(tokens))
        without_generic = [token for token in tokens if token not in GENERIC_ALIAS_TOKENS]
        if not _is_generic_alias(without_generic):
            variants.add(" ".join(without_generic))
        without_actions = [token for token in without_generic if token not in ACTION_ALIAS_TOKENS]
        if not _is_generic_alias(without_actions):
            variants.add(" ".join(without_actions))
        stripped = [token for token in tokens if token not in {"ton", "tuong", "cum", "khu", "vuc"}]
        if not _is_generic_alias(stripped):
            variants.add(" ".join(stripped))
        for size in (2, 3, 4):
            prefix = tokens[:size]
            if not _is_generic_alias(prefix):
                variants.add(" ".join(prefix))
    return variants


def destination_aliases():
    global _destination_aliases
    if _destination_aliases is not None:
        return _destination_aliases

    aliases = []

    def add_alias(value, dest_code):
        dest_code = clean_text(dest_code).upper()
        if not dest_code:
            return
        for alias in _alias_variants(value):
            aliases.append((alias, dest_code))

    for destination in DESTINATIONS.values():
        add_alias(destination.get("name"), destination.get("dest_code"))
        add_alias(destination.get("image_caption"), destination.get("dest_code"))

    for records in ALL_SHEETS.values():
        for record in records:
            dest_code = _dest_code_from_record(record)
            if not dest_code:
                continue
            for key in (
                "name", "destination_name", "place_name", "spot_name",
                "service_name", "activity_name", "question", "title",
                "keyword", "primary_keyword", "location_name", "event_name", "organization",
            ):
                add_alias(record.get(key), dest_code)

    _destination_aliases = sorted(set(aliases), key=lambda item: len(item[0]), reverse=True)
    return _destination_aliases


def _contains_alias(question_tokens, alias):
    alias_tokens = alias.split()
    if _is_generic_alias(alias_tokens) or len(alias_tokens) > len(question_tokens):
        return 0
    for index in range(0, len(question_tokens) - len(alias_tokens) + 1):
        if question_tokens[index:index + len(alias_tokens)] == alias_tokens:
            return len(alias_tokens)
    return 0


def resolve_target_codes(question, destination_id=None):
    question_tokens_list = _tokenize_slug(question)
    explicit_codes = {
        match.upper().replace(" ", "")
        for match in re.findall(r"\bTN\s*0?\d{2,3}\b", str(question or ""), re.I)
    }
    best_score = 0
    matched_codes = set(explicit_codes)
    for alias, dest_code in destination_aliases():
        score = _contains_alias(question_tokens_list, alias)
        if score <= 0:
            continue
        if score > best_score:
            best_score = score
            matched_codes = {dest_code}
        elif score == best_score:
            matched_codes.add(dest_code)
    explicit = bool(matched_codes)
    if matched_codes:
        return sorted(matched_codes), explicit
    current_code = _destination_code_for_id(destination_id)
    return ([current_code] if current_code else []), False


def _destination_code_for_id(destination_id):
    destination = DESTINATIONS.get(destination_id) if destination_id else None
    return clean_text(destination.get("dest_code")) if destination else ""


def _destination_name_for_code(dest_code):
    for destination in DESTINATIONS.values():
        if destination.get("dest_code") == dest_code:
            return clean_text(destination.get("name"))
    return ""


def _code_to_destination_id():
    return {
        destination.get("dest_code"): destination.get("id")
        for destination in DESTINATIONS.values()
        if destination.get("dest_code")
    }


def expand_contextual_query(question, destination_id=None, target_codes=None):
    tokens = query_tokens(question)
    if not tokens or len(tokens) > 12:
        return question, False
    names = " ".join(_destination_name_for_code(code) for code in (target_codes or []))
    current = DESTINATIONS.get(destination_id) if destination_id else None
    if not names and current:
        names = clean_text(current.get("name"))
    codes = " ".join(target_codes or [])
    place_hint = f"{names} {codes} Núi Bà Đen".strip()
    if not place_hint:
        return question, False
    if is_price_related(question):
        return f"giá vé cáp treo vé cổng combo buffet {question} {place_hint}", True
    if is_route_related(question):
        return f"đường đi di chuyển bản đồ vị trí {question} {place_hint}", True
    if is_hours_related(question):
        return f"giờ mở cửa giờ vận hành thời gian tham quan {question} {place_hint}", True
    if is_activity_related(question):
        return f"hoạt động trải nghiệm có gì chơi tham quan check-in {question} {place_hint}", True
    return f"{question} {place_hint}", True

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _context_matches_target(document, destination_id=None, target_codes=None):
    target_codes = set(target_codes or [])
    doc_code = clean_text(document.get("dest_code"))
    doc_destination_id = document.get("destination_id")
    if destination_id is not None and doc_destination_id == destination_id:
        return True
    if target_codes and doc_code in target_codes:
        return True
    return False


def _is_global_context(document):
    return not document.get("dest_code") and document.get("destination_id") is None


def _retrieve_context_from_memory(question, destination_id=None, target_codes=None, top_k=RAG_TOP_K):
    query_embedding = embed_text(question)
    scored_documents = []
    has_target = destination_id is not None or bool(target_codes)
    for document in get_rag_index():
        if has_target and not _context_matches_target(document, destination_id, target_codes) and not _is_global_context(document):
            continue
        score = _cosine_similarity(query_embedding, document["embedding"])
        score += keyword_bonus(question, document)
        if _context_matches_target(document, destination_id, target_codes):
            score += 1.0
        elif has_target and _is_global_context(document):
            score -= 0.15
        score += intent_bonus(question, document)
        scored_documents.append((score, document))
    scored_documents.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "score": round(score, 4),
            "id": document["id"],
            "type": document["type"],
            "title": document.get("title"),
            "source_url": document.get("source_url"),
            "dest_code": document.get("dest_code"),
            "text": document["text"],
        }
        for score, document in scored_documents[:top_k]
    ]


def retrieve_context(question, destination_id=None, target_codes=None, top_k=RAG_TOP_K):
    collection = _ensure_collection()
    if collection is None:
        return _retrieve_context_from_memory(question, destination_id, target_codes, top_k)

    try:
        collection_count = collection.count()
    except Exception:
        return _retrieve_context_from_memory(question, destination_id, target_codes, top_k)

    if collection_count == 0:
        return _retrieve_context_from_memory(question, destination_id, target_codes, top_k)

    n_results = min(max(top_k * 12, 50), collection_count)
    try:
        result = collection.query(
            query_embeddings=[embed_text(question)],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return _retrieve_context_from_memory(question, destination_id, target_codes, top_k)

    contexts = []
    for index, document_id in enumerate(result.get("ids", [[]])[0]):
        metadata = result.get("metadatas", [[]])[0][index] or {}
        distance = result.get("distances", [[]])[0][index]
        score = 1 - float(distance)
        has_target = destination_id is not None or bool(target_codes)
        if has_target and not _context_matches_target(metadata, destination_id, target_codes) and not _is_global_context(metadata):
            continue
        if _context_matches_target(metadata, destination_id, target_codes):
            score += 1.0
        elif has_target and _is_global_context(metadata):
            score -= 0.15
        score += intent_bonus(question, metadata)
        contexts.append({
            "score": round(score, 4),
            "id": document_id,
            "type": metadata.get("type"),
            "title": metadata.get("title"),
            "source_url": metadata.get("source_url"),
            "dest_code": metadata.get("dest_code"),
            "text": result.get("documents", [[]])[0][index],
        })

    contexts.sort(key=lambda item: item["score"], reverse=True)
    return contexts[:top_k]


def _ensure_collection():
    try:
        import chromadb
    except Exception:
        return None
    from .vector_store import ensure_collection
    documents = get_rag_documents()
    return ensure_collection(documents, embed_text)

# ---------------------------------------------------------------------------
# Service pricing retrieval (kept in rag.py because it's pipeline-specific)
# ---------------------------------------------------------------------------

def service_contexts_for_question(question, target_codes=None):
    if not is_price_related(question):
        return []
    tokens = query_tokens(question)
    is_cable_query = bool(tokens & {"cap", "treo", "cable", "car"})
    primary_codes = {code for code in (target_codes or []) if code}
    wanted_codes = set(primary_codes)
    if wanted_codes:
        wanted_codes.update({"TN001", "TN007"})
    if wanted_codes & {"TN006", "TN007"}:
        wanted_codes.update({"TN006", "TN007"})
    if wanted_codes & {"TN012", "TN013", "TN014", "TN015", "TN016"}:
        wanted_codes.add("TN016")
    primary_codes.add("TN016")
    if is_cable_query:
        wanted_codes.add("TN016")

    docs = []
    for document in get_rag_documents():
        if document.get("type") != "service_pricing":
            continue
        doc_code = clean_text(document.get("dest_code"))
        if wanted_codes and doc_code not in wanted_codes:
            continue
        title_slug = slugify(document.get("title", ""))
        text_slug = slugify(f"{document.get('title', '')} {document.get('text', '')}")
        is_cable_doc = any(
            marker in text_slug
            for marker in ("cap_treo", "tuyen_cap", "tam_an", "chua_hang", "combo_cap")
        )
        if is_cable_query and "buffet" in title_slug and "combo" not in title_slug:
            continue
        special_markers = ("wow_pass", "fastpass", "ve_nam", "mien_phi", "uu_dai", "sau_17h")
        asks_special = bool(tokens & {"wow", "fastpass", "nam", "mien", "phi", "uu", "dai", "sau", "17h"})
        if is_cable_query and not asks_special and any(marker in title_slug for marker in special_markers):
            continue
        if is_cable_query and not is_cable_doc:
            continue
        score = 1.0 + keyword_bonus(question, document)
        if doc_code in primary_codes:
            score += 0.8
        elif doc_code in wanted_codes:
            score += 0.35
        if is_cable_query:
            score += 0.45
        if tokens & {"chua", "hang"} and "chua_hang" in text_slug:
            score += 0.5
        docs.append({
            "score": round(score, 4),
            "id": document["id"],
            "type": document["type"],
            "title": document.get("title"),
            "source_url": document.get("source_url"),
            "dest_code": doc_code,
            "text": document["text"],
        })

    docs.sort(key=lambda item: item["score"], reverse=True)
    return docs[:10]


def merge_contexts(primary, supplemental, top_k=RAG_TOP_K):
    merged = []
    seen = set()
    for context in [*(supplemental or []), *(primary or [])]:
        context_id = context.get("id")
        if context_id in seen:
            continue
        seen.add(context_id)
        merged.append(context)
    return merged[:max(top_k, len(supplemental or []))]

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL,
            max_retries=ANTHROPIC_MAX_RETRIES,
            timeout=ANTHROPIC_TIMEOUT_SECONDS,
            default_headers={
                "User-Agent": ANTHROPIC_USER_AGENT,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )
    return _client


def ask_claude(question, contexts, session_id="default"):
    global _last_claude_error
    _last_claude_error = None
    if not ANTHROPIC_API_KEY:
        _last_claude_error = "missing_api_key"
        logger.warning("Claude skipped for session %s: missing ANTHROPIC_API_KEY", session_id)
        return None

    try:
        text = ""
        with _get_client().messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=build_system_prompt(contexts),
            messages=build_messages(question, session_store.build_history(session_id)),
        ) as stream:
            for chunk in stream.text_stream:
                text += chunk
    except Exception as exc:
        _last_claude_error = str(exc)
        logger.warning("Claude API error for session %s: %s", session_id, exc)
        return None

    if not text.strip():
        _last_claude_error = "empty_response"
        return None
    return text.strip()

# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _retrieval_payload(contexts, used_claude, claude_error, target_codes, explicit_destination, effective_question, expanded_from_context):
    return {
        "embedding_backend": _embedding_backend,
        "embedding_model": RAG_EMBEDDING_MODEL,
        "embedding_dim": RAG_EMBEDDING_DIM,
        "vector_store": _vector_store_backend,
        "top_k": RAG_TOP_K,
        "used_claude": used_claude,
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "claude_model": ANTHROPIC_MODEL,
        "claude_base_url": ANTHROPIC_BASE_URL,
        "claude_error": claude_error,
        "target_codes": target_codes,
        "explicit_destination": explicit_destination,
        "expanded_from_context": expanded_from_context,
        "effective_question": effective_question,
        "contexts": contexts,
    }


def _prepare_retrieval(question, destination_id=None):
    target_codes, explicit_destination = resolve_target_codes(question, destination_id=destination_id)
    target_destination_id = None
    if len(target_codes) == 1:
        target_destination_id = _code_to_destination_id().get(target_codes[0])
    if target_destination_id is None and not explicit_destination:
        target_destination_id = destination_id
    effective_question, expanded_from_context = expand_contextual_query(
        question,
        destination_id=target_destination_id or destination_id,
        target_codes=target_codes,
    )
    clarity = (
        {"needs_clarification": False, "clarifying_question": ""}
        if expanded_from_context
        else check_query_clarity(question)
    )
    return target_codes, explicit_destination, target_destination_id, effective_question, expanded_from_context, clarity

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def stream_rag_answer(question, destination_id=None, session_id="default"):
    global _last_claude_error
    question = (question or "").strip()
    target_codes, explicit_destination, target_destination_id, effective_question, expanded_from_context, clarity = _prepare_retrieval(question, destination_id)

    if clarity["needs_clarification"]:
        answer = clarity["clarifying_question"]
        for token in answer:
            yield "token", token
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        yield "done", _retrieval_payload([], False, "needs_clarification", target_codes, explicit_destination, effective_question, expanded_from_context)
        return

    contexts = retrieve_context(effective_question, destination_id=target_destination_id, target_codes=target_codes) if question else []
    contexts = merge_contexts(contexts, service_contexts_for_question(effective_question, target_codes=target_codes))

    if is_price_related(question) and any(context.get("type") == "service_pricing" for context in contexts):
        answer = fallback_rag_answer(question, contexts)
        for token in answer:
            yield "token", token
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        yield "done", _retrieval_payload(contexts, False, "structured_price", target_codes, explicit_destination, effective_question, expanded_from_context)
        return

    if not ANTHROPIC_API_KEY:
        answer = fallback_rag_answer(question, contexts)
        for token in answer:
            yield "token", token
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        yield "done", _retrieval_payload(contexts, False, "missing_api_key", target_codes, explicit_destination, effective_question, expanded_from_context)
        return

    answer = ""
    _last_claude_error = None
    try:
        with _get_client().messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=build_system_prompt(contexts),
            messages=build_messages(question, session_store.build_history(session_id)),
        ) as stream:
            for token in stream.text_stream:
                answer += token
                yield "token", token
    except Exception as exc:
        _last_claude_error = str(exc)
        logger.warning("Claude stream error for session %s: %s", session_id, exc)
        answer = fallback_rag_answer(question, contexts)
        for token in answer:
            yield "token", token

    if session_id and answer:
        session_store.append_turn(session_id, question, answer)
    yield "done", _retrieval_payload(contexts, True, _last_claude_error, target_codes, explicit_destination, effective_question, expanded_from_context)


def rag_answer(question, destination_id=None, session_id="default"):
    question = (question or "").strip()
    target_codes, explicit_destination, target_destination_id, effective_question, expanded_from_context, clarity = _prepare_retrieval(question, destination_id)

    if clarity["needs_clarification"]:
        answer = clarity["clarifying_question"]
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        return {
            "answer": answer,
            "retrieval": _retrieval_payload([], False, "needs_clarification", target_codes, explicit_destination, effective_question, expanded_from_context),
        }

    logger.info(
        "rag_answer start | session=%s dest=%s target_codes=%s q=%r effective_q=%r",
        session_id, destination_id, target_codes, question[:80], effective_question[:120],
    )

    contexts = retrieve_context(effective_question, destination_id=target_destination_id, target_codes=target_codes) if question else []
    contexts = merge_contexts(contexts, service_contexts_for_question(effective_question, target_codes=target_codes))

    structured_price = is_price_related(question) and any(context.get("type") == "service_pricing" for context in contexts)
    claude_answer = None if structured_price else ask_claude(question, contexts, session_id=session_id)
    answer = claude_answer or fallback_rag_answer(question, contexts)

    if session_id and answer:
        session_store.append_turn(session_id, question, answer)
    return {
        "answer": answer,
        "retrieval": _retrieval_payload(
            contexts, bool(claude_answer), "structured_price" if structured_price else _last_claude_error,
            target_codes, explicit_destination, effective_question, expanded_from_context,
        ),
    }


def rag_status():
    get_embedding_model()
    documents = get_rag_documents()
    sources = {}
    for document in documents:
        doc_type = document["type"]
        sources[doc_type] = sources.get(doc_type, 0) + 1
    return {
        "documents": len(documents),
        "sources": sources,
        **vector_store_status(documents, embed_text),
        "embedding_backend": _embedding_backend,
        "embedding_model": RAG_EMBEDDING_MODEL,
        "embedding_dim": RAG_EMBEDDING_DIM,
        "minilm_native_dim_note": "all-MiniLM-L6-v2 native dimension is 384; vectors are fitted to configured dimension.",
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "claude_model": ANTHROPIC_MODEL,
        "sessions": session_store.stats(),
    }