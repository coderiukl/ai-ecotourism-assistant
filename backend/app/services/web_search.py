from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import (
    WEB_SEARCH_API_KEY,
    WEB_SEARCH_CACHE_SECONDS,
    WEB_SEARCH_ENABLED,
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_PROVIDER,
    WEB_SEARCH_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_CONTEXT_CHARS = 4_000

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_cache_lock = asyncio.Lock()


def configured() -> bool:
    return (
        WEB_SEARCH_ENABLED
        and WEB_SEARCH_PROVIDER == "tavily"
        and bool(WEB_SEARCH_API_KEY)
    )


def _public_url(value: str) -> bool:
    parts = urlsplit(str(value or "").strip())
    hostname = (parts.hostname or "").casefold()
    return (
        parts.scheme in {"http", "https"}
        and bool(hostname)
        and hostname not in {"localhost", "127.0.0.1", "::1"}
        and not hostname.endswith(".local")
    )


def _document(result: dict[str, Any]) -> dict[str, Any] | None:
    url = str(result.get("url") or "").strip()
    content = " ".join(str(result.get("content") or "").split())
    if not _public_url(url) or not content:
        return None

    title = " ".join(str(result.get("title") or "Nguồn web").split())
    return {
        "id": f"web:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]}",
        "sheet": "live_web",
        "type": "live_web",
        "title": title,
        "dest_code": "",
        "source_url": url,
        "image_url": "",
        "last_updated": str(result.get("published_date") or "").strip(),
        "text": content[:MAX_CONTEXT_CHARS],
        "score": float(result.get("score") or 0),
    }


async def search(
    question: str,
    destination_name: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search the public web and return prompt-ready, attributable snippets."""
    if not configured():
        return []

    query = " ".join(
        value for value in (destination_name, "Núi Bà Đen Tây Ninh", question) if value
    )
    result_limit = limit or WEB_SEARCH_MAX_RESULTS
    cache_key = f"{query.casefold()}:{result_limit}"
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < WEB_SEARCH_CACHE_SECONDS:
        return [dict(item) for item in cached[1]]

    try:
        timeout = httpx.Timeout(WEB_SEARCH_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": WEB_SEARCH_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "topic": "general",
                    "max_results": result_limit,
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
            )
            response.raise_for_status()
            payload = response.json()

        documents = []
        for result in payload.get("results") or []:
            if not isinstance(result, dict):
                continue
            document = _document(result)
            if document:
                documents.append(document)

        documents.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        documents = documents[:result_limit]
        async with _cache_lock:
            _cache[cache_key] = (now, [dict(item) for item in documents])
        return documents
    except Exception as exc:
        logger.warning("General web search skipped: %s", exc)
        return []
