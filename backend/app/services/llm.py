from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

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


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


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
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{OPENAI_BASE_URL}/chat/completions", headers=_headers(), json=_payload(question, contexts, False))
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
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
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OPENAI_BASE_URL}/chat/completions", headers=_headers(), json=_payload(question, contexts, True)) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    data = json.loads(payload)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content") or ""
                    if token:
                        yield token
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc)
        for char in fallback_answer(question, contexts):
            yield char
