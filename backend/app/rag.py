import logging
import math
import re

from anthropic import Anthropic
from .query_guard import check_query_clarity

logger = logging.getLogger(__name__)

from .config import (
    ANTHROPIC_BASE_URL,
    ANTHROPIC_USER_AGENT,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    ANTHROPIC_VERSION,
    ANTHROPIC_MAX_TOKENS,
    RAG_EMBEDDING_DIM,
    RAG_EMBEDDING_MODEL,
    RAG_TOP_K,
)
from .data_loader import (
    ACTIVITIES,
    DESTINATIONS,
    FAQ_LIST,
    KB_LIST,
    MEDIA_ASSETS,
    SERVICES_PRICING,
)
from .memory import session_store
from .prompts import build_messages, build_system_prompt, fallback_rag_answer
from .text_utils import clean_text, slugify
from .vector_store import query_collection, vector_store_status

_embedding_model = None
_embedding_backend = None
_rag_documents = None
_rag_index = None
_vector_store_backend = None
_last_claude_error = None


def doc_text(title, fields):
    parts = [title]
    for label, value in fields:
        value = clean_text(value)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def build_rag_documents():
    documents = []

    for destination in DESTINATIONS.values():
        documents.append(
            {
                "id": f"destination:{destination.get('dest_code')}",
                "type": "destination",
                "title": destination.get("name"),
                "source_url": destination.get("image_source_url"),
                "destination_id": destination.get("id"),
                "dest_code": destination.get("dest_code"),
                "text": doc_text(
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
            }
        )

    for dest_code, media in MEDIA_ASSETS.items():
        documents.append(
            {
                "id": f"media_asset:{media.get('media_id')}",
                "type": "media_asset",
                "title": media.get("image_caption") or media.get("image_alt"),
                "source_url": media.get("image_source_url"),
                "dest_code": dest_code,
                "text": doc_text(
                    f"Hình ảnh điểm đến: {media.get('image_caption') or dest_code}",
                    [
                        ("Mã điểm đến", dest_code),
                        ("Ảnh", media.get("image_url")),
                        ("Chú thích", media.get("image_caption")),
                        ("Mô tả ảnh", media.get("image_alt")),
                    ],
                ),
            }
        )

    for service in SERVICES_PRICING:
        documents.append(
            {
                "id": f"service_pricing:{service.get('service_id')}",
                "type": "service_pricing",
                "title": service.get("service_name"),
                "source_url": service.get("source_url"),
                "dest_code": service.get("dest_id"),
                "text": doc_text(
                    f"Dịch vụ / giá vé: {service.get('service_name')}",
                    [
                        ("Mã điểm đến", service.get("dest_id")),
                        ("Loại dịch vụ", service.get("service_type")),
                        ("Service category", service.get("service_category")),
                        ("Area", service.get("area")),
                        ("Direction", service.get("direction")),
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
            }
        )

    for activity in ACTIVITIES:
        documents.append(
            {
                "id": f"activity:{activity.get('activity_id')}",
                "type": "activity",
                "title": activity.get("activity_name"),
                "source_url": activity.get("source_url"),
                "dest_code": activity.get("dest_id"),
                "text": doc_text(
                    f"Hoạt động trải nghiệm: {activity.get('activity_name')}",
                    [
                        ("Mã điểm đến", activity.get("dest_id")),
                        ("Loại hoạt động", activity.get("activity_type")),
                        ("Độ khó", activity.get("difficulty_level")),
                        ("Thời lượng", activity.get("estimated_duration")),
                        ("Thời điểm đẹp", activity.get("best_time")),
                        ("Lưu ý an toàn", activity.get("safety_note")),
                    ],
                ),
            }
        )

    for faq in FAQ_LIST:
        documents.append(
            {
                "id": f"faq:{faq.get('faq_id')}",
                "type": "faq",
                "title": faq.get("question"),
                "source_url": faq.get("source_url"),
                "text": doc_text(
                    f"FAQ: {faq.get('question')}",
                    [
                        ("Chủ đề", faq.get("topic")),
                        ("Câu hỏi", faq.get("question")),
                        ("Trả lời", faq.get("answer")),
                        ("Intent", faq.get("intent")),
                    ],
                ),
            }
        )

    for kb in KB_LIST:
        documents.append(
            {
                "id": f"kb:{kb.get('kb_id')}",
                "type": "knowledge_base",
                "title": kb.get("title"),
                "source_url": kb.get("source_url"),
                "text": doc_text(
                    f"Knowledge base: {kb.get('title')}",
                    [
                        ("Chủ đề", kb.get("topic")),
                        ("Nội dung", kb.get("content")),
                        ("Từ khóa", kb.get("keywords")),
                    ],
                ),
            }
        )

    return documents


def get_rag_documents():
    global _rag_documents
    if _rag_documents is None:
        _rag_documents = build_rag_documents()
    return _rag_documents


def get_embedding_model():
    global _embedding_backend, _embedding_model
    if _embedding_backend:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        try:
            _embedding_model = SentenceTransformer(
                RAG_EMBEDDING_MODEL, local_files_only=True
            )
        except TypeError:
            _embedding_model = SentenceTransformer(RAG_EMBEDDING_MODEL)
        _embedding_backend = "minilm"
    except Exception:
        _embedding_model = None
        _embedding_backend = "hash_fallback"
    return _embedding_model


def fit_embedding_dimension(vector):
    vector = [float(value) for value in vector]
    if len(vector) > RAG_EMBEDDING_DIM:
        vector = vector[:RAG_EMBEDDING_DIM]
    elif len(vector) < RAG_EMBEDDING_DIM:
        vector = vector + [0.0] * (RAG_EMBEDDING_DIM - len(vector))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def hash_embedding(text):
    vector = [0.0] * RAG_EMBEDDING_DIM
    tokens = re.findall(r"\w+", slugify(text))
    for token in tokens:
        index = hash(token) % RAG_EMBEDDING_DIM
        vector[index] += 1.0
    return fit_embedding_dimension(vector)


def embed_text(text):
    model = get_embedding_model()
    if _embedding_backend == "minilm" and model:
        vector = model.encode(text, normalize_embeddings=True)
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        return fit_embedding_dimension(vector)
    return hash_embedding(text)


def cosine_similarity(left, right):
    return sum(a * b for a, b in zip(left, right))


def get_rag_index():
    global _rag_index
    if _rag_index is None:
        _rag_index = [
            {**document, "embedding": embed_text(document["text"])}
            for document in get_rag_documents()
        ]
    return _rag_index


def keyword_bonus(question, document):
    """Small lexical bonus so exact words like 'giá vé', 'cáp treo' rank higher."""
    query_tokens = set(re.findall(r"\w+", slugify(question or "")))
    if not query_tokens:
        return 0.0

    haystack = slugify(" ".join(
        str(document.get(field, ""))
        for field in ("title", "type", "text")
    ))
    matched = sum(1 for token in query_tokens if token and token in haystack)
    return min(0.25, matched * 0.04)


def rerank_contexts(question, contexts, top_k=RAG_TOP_K):
    reranked = []
    for context in contexts or []:
        score = float(context.get("score") or 0.0) + keyword_bonus(question, context)
        reranked.append(({**context, "score": round(score, 4)}))
    reranked.sort(key=lambda item: item.get("score", 0), reverse=True)
    return reranked[:top_k]


def query_tokens(question):
    return set(re.findall(r"[a-z0-9]+", slugify(question or "")))


def is_price_related(question):
    tokens = query_tokens(question)
    return bool(tokens & {"gia", "ve", "phi", "ticket", "price", "cost"})


def expand_contextual_query(question, destination_id=None):
    destination = DESTINATIONS.get(destination_id) if destination_id else None
    if not destination:
        return question, False

    tokens = query_tokens(question)
    if not tokens or len(tokens) > 8:
        return question, False

    place = clean_text(destination.get("name"))
    dest_code = clean_text(destination.get("dest_code"))

    if is_price_related(question):
        return f"gia ve cap treo dich vu buffet combo {place} {dest_code} Nui Ba Den", True
    if tokens & {"duong", "di", "xe", "route"}:
        return f"duong di di chuyen {place} {dest_code} Nui Ba Den", True
    if tokens & {"gio", "may", "time", "open"}:
        return f"gio mo cua thoi gian tham quan {place} {dest_code} Nui Ba Den", True
    if tokens & {"choi", "lam", "activity", "activities"}:
        return f"hoat dong trai nghiem co gi choi {place} {dest_code} Nui Ba Den", True

    return question, False


def service_contexts_for_question(question, destination_id=None):
    if not is_price_related(question):
        return []

    destination = DESTINATIONS.get(destination_id) if destination_id else None
    dest_code = clean_text(destination.get("dest_code")) if destination else ""
    wanted_codes = {dest_code, "TN001"} if dest_code else {"TN001"}
    docs = []

    for document in get_rag_documents():
        if document.get("type") != "service_pricing":
            continue
        if clean_text(document.get("dest_code")) not in wanted_codes:
            continue
        docs.append({
            "score": round(1.5 + keyword_bonus(question, document), 4),
            "id": document["id"],
            "type": document["type"],
            "title": document.get("title"),
            "source_url": document.get("source_url"),
            "text": document["text"],
        })

    return docs[:8]


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


def retrieve_context_from_memory(question, destination_id=None, top_k=RAG_TOP_K):
    query_embedding = embed_text(question)
    scored_documents = []
    destination = DESTINATIONS.get(destination_id) if destination_id else None
    dest_code = destination.get("dest_code") if destination else None

    for document in get_rag_index():
        score = cosine_similarity(query_embedding, document["embedding"])
        score += keyword_bonus(question, document)
        if destination_id and document.get("destination_id") == destination_id:
            score += 0.15
        elif dest_code and document.get("dest_code") == dest_code:
            score += 0.15
        scored_documents.append((score, document))

    scored_documents.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "score": round(score, 4),
            "id": document["id"],
            "type": document["type"],
            "title": document.get("title"),
            "source_url": document.get("source_url"),
            "text": document["text"],
        }
        for score, document in scored_documents[:top_k]
    ]


def retrieve_context(question, destination_id=None, top_k=RAG_TOP_K):
    global _vector_store_backend
    destination = DESTINATIONS.get(destination_id) if destination_id else None
    dest_code = destination.get("dest_code") if destination else None
    contexts = query_collection(
        get_rag_documents(),
        embed_text,
        question,
        top_k,
        destination_id=destination_id,
        dest_code=dest_code,
    )
    if contexts is not None:
        _vector_store_backend = "chromadb"
        return rerank_contexts(question, contexts, top_k=top_k)
    _vector_store_backend = "in_memory"
    return retrieve_context_from_memory(question, destination_id=destination_id, top_k=top_k)


def context_for_prompt(contexts):
    return "\n\n".join(
        f"[{index}] {context['title']}\n{context['text']}"
        for index, context in enumerate(contexts, start=1)
    )

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL,
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

    history = session_store.build_history(session_id)
    messages = build_messages(question, contexts, history)
    system_prompt = build_system_prompt(contexts)

    try:
        client = _get_client()
        text = ""
        logger.info(
            "Claude stream start | session=%s model=%s base_url=%s ua_len=%d",
            session_id,
            ANTHROPIC_MODEL,
            ANTHROPIC_BASE_URL,
            len(ANTHROPIC_USER_AGENT or ""),
        )
        with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                text += chunk
    except Exception as exc:
        _last_claude_error = str(exc)
        logger.warning("Claude API error for session %s: %s", session_id, exc)
        return None

    if not text.strip():
        _last_claude_error = "empty_response"
        logger.warning("Claude empty response for session %s", session_id)
        return None

    logger.info("Claude stream done | session=%s answer_len=%d", session_id, len(text))
    return text.strip() or None


def stream_rag_answer(question, destination_id=None, session_id="default"):
    global _last_claude_error

    question = (question or "").strip()
    effective_question, expanded_from_context = expand_contextual_query(
        question,
        destination_id=destination_id,
    )
    clarity = (
        {"needs_clarification": False, "clarifying_question": ""}
        if expanded_from_context
        else check_query_clarity(question)
    )

    def retrieval_payload(contexts, used_claude, claude_error=None):
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
            "expanded_from_context": expanded_from_context,
            "effective_question": effective_question,
            "contexts": contexts,
        }

    if clarity["needs_clarification"]:
        answer = clarity["clarifying_question"]
        for token in answer:
            yield "token", token
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        yield "done", retrieval_payload([], False, "needs_clarification")
        return

    contexts = retrieve_context(effective_question, destination_id=destination_id) if question else []
    contexts = merge_contexts(
        contexts,
        service_contexts_for_question(effective_question, destination_id=destination_id),
    )

    if not ANTHROPIC_API_KEY:
        answer = fallback_rag_answer(question, contexts)
        for token in answer:
            yield "token", token
        if session_id and answer:
            session_store.append_turn(session_id, question, answer)
        yield "done", retrieval_payload(contexts, False, "missing_api_key")
        return

    answer = ""
    _last_claude_error = None
    try:
        client = _get_client()
        history = session_store.build_history(session_id)
        messages = build_messages(question, contexts, history)
        system_prompt = build_system_prompt(contexts)

        with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
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
        yield "done", retrieval_payload(contexts, False, _last_claude_error)
        return

    answer = answer.strip()
    if session_id and answer:
        session_store.append_turn(session_id, question, answer)
    yield "done", retrieval_payload(contexts, True, _last_claude_error)


def rag_answer(question, destination_id=None, session_id="default"):
    question = (question or "").strip()
    effective_question, expanded_from_context = expand_contextual_query(
        question,
        destination_id=destination_id,
    )
    clarity = (
        {"needs_clarification": False, "clarifying_question": ""}
        if expanded_from_context
        else check_query_clarity(question)
    )

    if clarity["needs_clarification"]:
        answer = clarity["clarifying_question"]

        if session_id and answer:
            session_store.append_turn(session_id, question, answer)

        return {
            "answer": answer,
            "retrieval": {
                "embedding_backend": _embedding_backend,
                "embedding_model": RAG_EMBEDDING_MODEL,
                "embedding_dim": RAG_EMBEDDING_DIM,
                "vector_store": _vector_store_backend,
                "top_k": RAG_TOP_K,
                "used_claude": False,
                "claude_configured": bool(ANTHROPIC_API_KEY),
                "claude_model": ANTHROPIC_MODEL,
                "claude_base_url": ANTHROPIC_BASE_URL,
                "claude_error": "needs_clarification",
                "contexts": [],
            },
        }
    logger.info(
        "rag_answer start | session=%s dest=%s q=%r effective_q=%r",
        session_id,
        destination_id,
        question[:80],
        effective_question[:120],
    )
    contexts = retrieve_context(effective_question, destination_id=destination_id) if question else []
    contexts = merge_contexts(
        contexts,
        service_contexts_for_question(effective_question, destination_id=destination_id),
    )
    logger.info("rag_answer retrieved %d contexts", len(contexts))
    claude_answer = ask_claude(question, contexts, session_id=session_id)
    logger.info(
        "rag_answer used_claude=%s claude_error=%s",
        bool(claude_answer),
        _last_claude_error,
    )
    answer = claude_answer or fallback_rag_answer(question, contexts)
    if session_id and answer:
        session_store.append_turn(session_id, question, answer)
    logger.info("rag_answer done | answer_len=%d", len(answer))
    return {
        "answer": answer,
        "retrieval": {
            "embedding_backend": _embedding_backend,
            "embedding_model": RAG_EMBEDDING_MODEL,
            "embedding_dim": RAG_EMBEDDING_DIM,
            "vector_store": _vector_store_backend,
            "top_k": RAG_TOP_K,
            "used_claude": bool(claude_answer),
            "claude_configured": bool(ANTHROPIC_API_KEY),
            "claude_model": ANTHROPIC_MODEL,
            "claude_base_url": ANTHROPIC_BASE_URL,
            "claude_error": _last_claude_error,
            "expanded_from_context": expanded_from_context,
            "effective_question": effective_question,
            "contexts": contexts,
        },
    }


def rag_status():
    get_embedding_model()
    documents = get_rag_documents()
    sources = {}
    for document in documents:
        doc_type = document["type"]
        sources[doc_type] = sources.get(doc_type, 0) + 1

    session_stats = session_store.stats()

    return {
        "documents": len(documents),
        "sources": sources,
        **vector_store_status(documents, embed_text),
        "embedding_backend": _embedding_backend,
        "embedding_model": RAG_EMBEDDING_MODEL,
        "embedding_dim": RAG_EMBEDDING_DIM,
        "minilm_native_dim_note": (
            "all-MiniLM-L6-v2 native dimension is 384; vectors are fitted "
            "to configured dimension."
        ),
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "claude_model": ANTHROPIC_MODEL,
        "sessions": session_stats,
    }
