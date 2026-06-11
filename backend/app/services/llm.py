from __future__ import annotations

import logging
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


def configured() -> bool:
    return bool(OPENAI_API_KEY)


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=OPENAI_TIMEOUT_SECONDS,
    )


def _payload(question: str, contexts: list[dict[str, Any]], stream: bool) -> dict[str, Any]:
    return {
        "model": OPENAI_MODEL,
        "messages": messages(question, contexts),
        "temperature": OPENAI_TEMPERATURE,
        "max_tokens": OPENAI_MAX_TOKENS,
        "stream": stream,
    }


async def complete(question: str, contexts: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not configured():
        return fallback_answer(question, contexts), "missing_openai_api_key"
    try:
        response = await _client().chat.completions.create(**_payload(question, contexts, False))
        answer = (response.choices[0].message.content or "").strip()
        return answer or fallback_answer(question, contexts), None
    except Exception as exc:
        logger.warning("LLM completion failed: %s", exc)
        return fallback_answer(question, contexts), str(exc)


async def stream(question: str, contexts: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
    if not configured():
        for char in fallback_answer(question, contexts):
            yield char
        return
    try:
        stream_response = await _client().chat.completions.create(**_payload(question, contexts, True))
        async for chunk in stream_response:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc)
        for char in fallback_answer(question, contexts):
            yield char
