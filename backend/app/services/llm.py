from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TIMEOUT_SECONDS,
)
from app.services.prompts import fallback_answer, messages

logger = logging.getLogger(__name__)

_INTERNAL_WORD_RE = re.compile(
    r"\b(?:context|sheet|excel nội bộ|database|vector store|rag|nguồn \d+)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>)]+")
_SOURCE_LINE_RE = re.compile(r"(?im)^\s*(?:nguồn|source)\s*:\s*.*(?:\n|$)")


_DANGLING_CONNECTOR_RE = re.compile(
    r"(?:,\s*)?\b(?:tại|ở|qua|xem(?:\s+thêm)?(?:\s+tại)?|truy cập|chi tiết tại|liên kết|link)\s*:?\s*(?=https?://)",
    re.IGNORECASE,
)


def _format_urls_and_spacing(text: str) -> str:
    urls: list[str] = []
    # Drop dangling connector words ("xem thêm tại", "chi tiết tại", ...) that
    # would otherwise leave an awkward trailing fragment once the bare URL
    # right after them is stripped out below.
    text = _DANGLING_CONNECTOR_RE.sub("", text)

    def protect_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        url = raw_url.rstrip(".,;:!?")
        trailing = raw_url[len(url):]

        # Preserve explicit action links such as Google Maps, but remove raw
        # URLs. Official sources are rendered separately by the frontend.
        if match.start() > 0 and text[match.start() - 1] == "(":
            placeholder = f"__URL_{len(urls)}__"
            urls.append(url)
            return placeholder + trailing
        return trailing

    answer = _URL_RE.sub(protect_url, text)
    # Repair common token-boundary issues returned by compatible model gateways.
    answer = re.sub(r"(?<!\d[hH])(?<=[^\W\d_])(?=\d)", " ", answer)
    answer = re.sub(r"(?<=\d)(?=(?:phút|giờ|tiếng|km|mét)\b)", " ", answer, flags=re.IGNORECASE)
    # Collapse whitespace left behind by removed connectors/URLs and fix any
    # now-dangling punctuation (e.g. "tại  ." -> "tại.").
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    answer = re.sub(r"[ \t]+([,.!?;:])", r"\1", answer)

    for index, url in enumerate(urls):
        answer = answer.replace(f"__URL_{index}__", url)

    return answer


def polish_answer(text: str) -> str:
    answer = str(text or "").strip()

    if not answer:
        return answer

    replacements = [
        (r"(?i)\bdựa trên context[:,]?\s*", ""),
        (r"(?i)\btheo context[:,]?\s*", ""),
        (r"(?i)\btheo dữ liệu được cung cấp[:,]?\s*", ""),
        (r"(?i)\btrong context[:,]?\s*", ""),
    ]

    for pattern, replacement in replacements:
        answer = re.sub(pattern, replacement, answer)

    answer = _SOURCE_LINE_RE.sub("", answer)
    answer = _format_urls_and_spacing(answer)
    answer = re.sub(r"\s*[•●▪]\s*", "\n- ", answer)
    answer = re.sub(r"(^|\n)\s*[-*]\s*", r"\1- ", answer)
    answer = re.sub(
        r"(?im)^\*\*(Lưu ý|Mẹo|Gợi ý|Quan trọng):\*\*\s*",
        r"\1: ",
        answer,
    )
    answer = "\n".join(line.rstrip() for line in answer.splitlines())
    answer = re.sub(r"\s+([,.!?;:])", r"\1", answer)
    answer = re.sub(r"\n{3,}", "\n\n", answer)

    if _INTERNAL_WORD_RE.search(answer):
        answer = _INTERNAL_WORD_RE.sub("thông tin tham khảo", answer)

    return answer.strip()


def configured() -> bool:
    return bool(OPENAI_API_KEY)


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=1,
    )


def _payload(
    question: str,
    contexts: list[dict[str, Any]],
    stream: bool,
    destination: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "model": OPENAI_MODEL,
        "messages": messages(question, contexts, destination, history),
        "temperature": OPENAI_TEMPERATURE,
        "max_tokens": OPENAI_MAX_TOKENS,
        "stream": stream,
    }


async def complete(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, str | None]:
    if not configured():
        return polish_answer(fallback_answer(question, contexts, destination)), "missing_openai_api_key"

    try:
        response = await _client().chat.completions.create(
            **_payload(question, contexts, False, destination, history)
        )
        answer = (response.choices[0].message.content or "").strip()
        return polish_answer(answer or fallback_answer(question, contexts, destination)), None
    except Exception as exc:
        logger.warning("LLM completion failed: %s", exc)
        return polish_answer(fallback_answer(question, contexts, destination)), exc.__class__.__name__


async def stream(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    if not configured():
        for char in polish_answer(fallback_answer(question, contexts, destination)):
            yield char
        return

    emitted = False
    try:
        stream_response = await _client().chat.completions.create(
            **_payload(question, contexts, True, destination, history)
        )
        async for chunk in stream_response:
            token = chunk.choices[0].delta.content or ""
            if token:
                emitted = True
                yield token

        if not emitted:
            yield polish_answer(fallback_answer(question, contexts, destination))
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc)
        if not emitted:
            yield polish_answer(fallback_answer(question, contexts, destination))
        else:
            yield "\n\nKết nối bị gián đoạn. Bạn có thể gửi lại câu hỏi để mình trả lời đầy đủ hơn."
