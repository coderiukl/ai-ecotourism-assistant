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

_INTERNAL_WORD_RE = re.compile(r"\b(?:context|CONTEXT|sheet|Sheet|Excel nội bộ|nguồn \d+)\b")
_URL_RE = re.compile(r"https?://[^\s<>)]+")


def _format_urls_and_spacing(text: str) -> str:
    urls: list[str] = []

    def protect_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        url = raw_url.rstrip(".,;:!?")
        trailing = raw_url[len(url):]
        placeholder = f"__URL_{len(urls)}__"
        urls.append(url)

        # A URL preceded by '(' is already part of a Markdown link.
        if match.start() > 0 and text[match.start() - 1] == "(":
            return placeholder + trailing
        return f"\n\nNguồn: [Xem trang chính thức]({placeholder}){trailing}"

    answer = _URL_RE.sub(protect_url, text)
    # Repair common token-boundary issues returned by compatible model gateways.
    answer = re.sub(r"(?<!\d[hH])(?<=[^\W\d_])(?=\d)", " ", answer)
    answer = re.sub(r"(?<=\d)(?=(?:phút|giờ|tiếng|km|mét)\b)", " ", answer, flags=re.IGNORECASE)

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

    answer = _format_urls_and_spacing(answer)
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
) -> dict[str, Any]:
    return {
        "model": OPENAI_MODEL,
        "messages": messages(question, contexts, destination),
        "temperature": OPENAI_TEMPERATURE,
        "max_tokens": OPENAI_MAX_TOKENS,
        "stream": stream,
    }


async def complete(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    if not configured():
        return polish_answer(fallback_answer(question, contexts, destination)), "missing_openai_api_key"

    try:
        response = await _client().chat.completions.create(**_payload(question, contexts, False, destination))
        answer = (response.choices[0].message.content or "").strip()
        return polish_answer(answer or fallback_answer(question, contexts, destination)), None
    except Exception as exc:
        logger.warning("LLM completion failed: %s", exc)
        return polish_answer(fallback_answer(question, contexts, destination)), exc.__class__.__name__


async def stream(
    question: str,
    contexts: list[dict[str, Any]],
    destination: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    if not configured():
        for char in polish_answer(fallback_answer(question, contexts, destination)):
            yield char
        return

    try:
        stream_response = await _client().chat.completions.create(**_payload(question, contexts, True, destination))
        raw_answer = ""
        async for chunk in stream_response:
            token = chunk.choices[0].delta.content or ""
            if token:
                raw_answer += token

        answer = polish_answer(raw_answer or fallback_answer(question, contexts, destination))
        for start in range(0, len(answer), 24):
            yield answer[start:start + 24]
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc)
        for char in polish_answer(fallback_answer(question, contexts, destination)):
            yield char
