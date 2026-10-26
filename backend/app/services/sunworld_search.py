from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import (
    SUNWORLD_CACHE_SECONDS,
    SUNWORLD_LIVE_SEARCH,
    SUNWORLD_SEARCH_MAX_PAGES,
    SUNWORLD_SEARCH_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://sunworld.vn/sitemap/sitemap-vi.xml"
DISCOVERY_URLS = (
    "https://sunworld.vn/vi/ba-den/cong-trinh-bieu-tuong",
    "https://sunworld.vn/vi/ba-den/cam-nang-du-lich",
    "https://sunworld.vn/vi/ba-den/tin-tuc-sunworld",
    "https://sunworld.vn/vi/ba-den/uu-dai",
    "https://sunworld.vn/vi/ba-den/di-chuyen",
    "https://sunworld.vn/vi/ba-den/activities",
    "https://sunworld.vn/vi/ba-den/check-in",
)
ALLOWED_HOST = "sunworld.vn"
ALLOWED_PATH_PREFIXES = ("/vi/ba-den/", "/ba-den/")
MAX_RESPONSE_BYTES = 2_000_000
MAX_CONTEXT_CHARS = 5_500
USER_AGENT = "AI-Ecotourism-Assistant/1.0 (+https://ai-ecotourism-assistant.vercel.app)"

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()

STOP_WORDS = {
    "anh",
    "bao",
    "ban",
    "bi",
    "cai",
    "cho",
    "co",
    "cua",
    "di",
    "duoc",
    "gi",
    "la",
    "minh",
    "mot",
    "nao",
    "nay",
    "nhung",
    "o",
    "tai",
    "the",
    "thong",
    "tin",
    "va",
    "ve",
}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize(value).split()
        if len(token) >= 2 and token not in STOP_WORDS
    }


def _allowed_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and (parts.hostname or "").casefold() == ALLOWED_HOST
        and any(parts.path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES)
    )


async def _get_text(url: str) -> str:
    if url != SITEMAP_URL and not _allowed_url(url):
        raise ValueError("Sun World URL is outside the allowlist")

    now = time.monotonic()
    cached = _cache.get(url)
    if cached and now - cached[0] < SUNWORLD_CACHE_SECONDS:
        return str(cached[1])

    async with _cache_lock:
        cached = _cache.get(url)
        if cached and now - cached[0] < SUNWORLD_CACHE_SECONDS:
            return str(cached[1])

    timeout = httpx.Timeout(SUNWORLD_SEARCH_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "vi-VN,vi;q=0.9"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        final_url = str(response.url)
        if url == SITEMAP_URL:
            if (urlsplit(final_url).hostname or "").casefold() != ALLOWED_HOST:
                raise ValueError("Sun World sitemap redirected outside the allowlist")
        elif not _allowed_url(final_url):
            raise ValueError("Sun World page redirected outside the allowlist")
        content = response.content[:MAX_RESPONSE_BYTES]
        text = content.decode(response.encoding or "utf-8", errors="replace")

    async with _cache_lock:
        _cache[url] = (now, text)
    return text


async def _sitemap_entries() -> list[dict[str, str]]:
    xml_text = await _get_text(SITEMAP_URL)
    root = ET.fromstring(xml_text)
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries_by_url: dict[str, dict[str, str]] = {}

    for node in root.findall("sm:url", namespace):
        url = (node.findtext("sm:loc", default="", namespaces=namespace) or "").strip()
        if not _allowed_url(url):
            continue
        entries_by_url[url] = {
            "url": url,
            "lastmod": (
                node.findtext("sm:lastmod", default="", namespaces=namespace) or ""
            ).strip(),
        }

    discovery_pages = await asyncio.gather(
        *(_get_text(url) for url in DISCOVERY_URLS),
        return_exceptions=True,
    )
    for page in discovery_pages:
        if isinstance(page, Exception):
            continue
        paths = set(
            re.findall(
                r"/ba-den/(?:[a-z0-9-]+/)+[a-z0-9-]+(?:-\d+)?",
                str(page).casefold(),
            )
        )
        for path in paths:
            url = f"https://sunworld.vn/vi{path}"
            if _allowed_url(url):
                entries_by_url.setdefault(url, {"url": url, "lastmod": ""})

    return list(entries_by_url.values())


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.image_url = ""
        self._in_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        lowered = tag.casefold()

        if lowered == "title":
            self._in_title = True
        if lowered in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if lowered == "meta":
            name = (values.get("name") or values.get("property") or "").casefold()
            content = values.get("content", "").strip()
            if name in {"description", "og:description"} and not self.description:
                self.description = content
            if name in {"og:image", "twitter:image"} and not self.image_url:
                self.image_url = content

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "title":
            self._in_title = False
        if lowered in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        elif not self._skip_depth:
            self._chunks.append(text)

    def article_text(self) -> str:
        seen: set[str] = set()
        chunks: list[str] = []

        for chunk in self._chunks:
            normalized = _normalize(chunk)
            if len(normalized) < 20 or normalized in seen:
                continue
            seen.add(normalized)
            chunks.append(chunk)

        return "\n".join(chunks)


def _parse_article(html_text: str, url: str, lastmod: str) -> dict[str, Any]:
    parser = _ArticleParser()
    parser.feed(html_text)
    text = parser.article_text()
    combined = "\n".join(
        item for item in (parser.description, text) if item
    )[:MAX_CONTEXT_CHARS]
    title = re.sub(r"\s*[-|]\s*Sun World.*$", "", parser.title).strip()
    published_match = re.search(
        r'(?:\\?"dateOrigin\\?"\s*:\s*\\?")(\d{4}-\d{2}-\d{2})',
        html_text,
    )
    source_date = lastmod or (published_match.group(1) if published_match else "")

    return {
        "id": f"sunworld:{hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]}",
        "sheet": "live_sunworld",
        "type": "live_sunworld",
        "title": title or "Thông tin Sun World Ba Den Mountain",
        "dest_code": "",
        "source_url": url,
        "image_url": parser.image_url,
        "last_updated": source_date,
        "text": combined,
    }


def _url_score(url: str, query_tokens: set[str]) -> float:
    path_tokens = _tokens(urlsplit(url).path)
    if not query_tokens:
        return 0.0
    overlap = query_tokens & path_tokens
    phrase = " ".join(query_tokens)
    normalized_path = _normalize(urlsplit(url).path)
    score = len(overlap) * 2.0 + (2.0 if phrase and phrase in normalized_path else 0.0)
    if "/uu-dai/" in url and not query_tokens.intersection({"uu", "dai", "khuyen", "mai"}):
        score -= 1.5
    return score


def _content_score(document: dict[str, Any], query_tokens: set[str]) -> float:
    searchable = _tokens(f"{document.get('title', '')} {document.get('text', '')}")
    return float(len(query_tokens & searchable))


async def search(
    question: str,
    destination_name: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not SUNWORLD_LIVE_SEARCH:
        return []

    query = " ".join(item for item in (destination_name, question) if item)
    query_tokens = _tokens(query)
    result_limit = limit or SUNWORLD_SEARCH_MAX_PAGES

    try:
        entries = await _sitemap_entries()
        ranked = sorted(
            entries,
            key=lambda item: _url_score(item["url"], query_tokens),
            reverse=True,
        )
        candidates = [
            item for item in ranked[: max(result_limit * 4, 8)]
            if _url_score(item["url"], query_tokens) > 0
        ]

        if not candidates:
            return []

        pages = await asyncio.gather(
            *(_get_text(item["url"]) for item in candidates),
            return_exceptions=True,
        )
        documents: list[dict[str, Any]] = []

        for entry, page in zip(candidates, pages):
            if isinstance(page, Exception):
                continue
            document = _parse_article(str(page), entry["url"], entry["lastmod"])
            if document["text"]:
                document["score"] = round(
                    _url_score(entry["url"], query_tokens)
                    + _content_score(document, query_tokens),
                    4,
                )
                documents.append(document)

        documents.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return documents[:result_limit]
    except Exception as exc:
        logger.warning("Sun World live search skipped: %s", exc)
        return []
