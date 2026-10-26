from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from openpyxl import load_workbook

from app.core.config import DATABASE_URL, DATA_PATH, DATA_REFRESH_SECONDS

try:
    import asyncpg
except Exception:
    asyncpg = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None
    RealDictCursor = None


logger = logging.getLogger(__name__)
_pool: Any | None = None
_refresh_lock = threading.RLock()
_last_refresh_monotonic = 0.0


DB_SHEETS = [
    "destinations",
    "media_assets",
    "services_pricing",
    "operation_hours",
    "activities",
    "faq",
    "seo_keywords",
    "knowledge_base",
    "itineraries",
    "tags",
    "maps_navigation",
    "travel_tips",
    "weather_info",
    "transportation",
    "photo_spots",
    "food_stay",
    "contact_info",
    "events_culture",
    "safety_emergency",
    "chatbot_intents",
]


def _base_postgres_dsn() -> str:
    """
    Chuẩn hóa SQLAlchemy URL:
    postgresql+asyncpg://... -> postgresql://...
    """
    if not DATABASE_URL:
        return ""

    return DATABASE_URL.replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )


def _asyncpg_dsn() -> str:
    """
    DSN dành cho asyncpg.

    asyncpg không dùng sslmode=require theo cách psycopg2.
    Ta loại bỏ ssl/sslmode khỏi query string và truyền ssl riêng
    trong asyncpg.create_pool(..., ssl="require").
    """
    dsn = _base_postgres_dsn()

    if not dsn:
        return ""

    parts = urlsplit(dsn)

    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in {"ssl", "sslmode"}
    ]

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_items),
            parts.fragment,
        )
    )


def _psycopg2_dsn() -> str:
    """
    DSN dành cho psycopg2.

    psycopg2 dùng sslmode=require.
    """
    dsn = _base_postgres_dsn()

    if not dsn:
        return ""

    parts = urlsplit(dsn)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    ssl_value = query.pop("ssl", None)

    if ssl_value and "sslmode" not in query:
        query["sslmode"] = ssl_value

    query.setdefault("sslmode", "require")

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


async def connect() -> None:
    global _pool

    if not DATABASE_URL:
        logger.warning("Postgres disabled: DATABASE_URL is empty")
        return

    if _pool is not None:
        return

    if asyncpg is None:
        logger.warning("Postgres disabled: asyncpg is not installed")
        return

    try:
        dsn = _asyncpg_dsn()

        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=5,
                timeout=10,
                command_timeout=30,
                ssl="require",
            ),
            timeout=15,
        )

        await asyncio.wait_for(migrate(), timeout=20)
        logger.info("Postgres connected")

    except Exception as exc:
        _pool = None
        logger.exception("Postgres disabled: %s", exc)


async def close() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres connection pool closed")


async def migrate() -> None:
    if _pool is None:
        return

    async with _pool.acquire() as conn:
        await conn.execute(
            """
            create table if not exists chat_sessions (
                session_id text primary key,
                destination_id integer,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            );

            create table if not exists chat_messages (
                id bigserial primary key,
                session_id text not null,
                role text not null check (role in ('user', 'assistant')),
                content text not null,
                metadata jsonb not null default '{}'::jsonb,
                created_at timestamptz not null default now()
            );

            create index if not exists idx_chat_messages_session_id
            on chat_messages(session_id);

            create index if not exists idx_chat_messages_created_at
            on chat_messages(created_at);
            """
        )


async def save_chat(
    session_id: str,
    destination_id: int | None,
    user_message: str,
    assistant_message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if _pool is None:
        logger.warning("save_chat skipped: Postgres is not connected")
        return

    metadata = metadata or {}

    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                insert into chat_sessions(
                    session_id,
                    destination_id,
                    updated_at
                )
                values($1, $2, now())
                on conflict(session_id)
                do update set
                    destination_id = excluded.destination_id,
                    updated_at = now()
                """,
                session_id,
                destination_id,
            )

            await conn.execute(
                """
                insert into chat_messages(
                    session_id,
                    role,
                    content,
                    metadata
                )
                values($1, 'user', $2, '{}'::jsonb)
                """,
                session_id,
                user_message,
            )

            await conn.execute(
                """
                insert into chat_messages(
                    session_id,
                    role,
                    content,
                    metadata
                )
                values($1, 'assistant', $2, $3::jsonb)
                """,
                session_id,
                assistant_message,
                json.dumps(metadata, ensure_ascii=False),
            )


def enabled() -> bool:
    return _pool is not None


def clean(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value).strip()


def image_url_for_dest(fallback_url: str = "") -> str:
    return fallback_url.strip()


def google_maps_url_for_dest(
    navigation: dict[str, str],
    name: str,
    location: str,
) -> str:
    configured_url = navigation.get("google_maps_search_url", "").strip()

    if configured_url.startswith(
        ("https://www.google.com/maps/", "https://maps.google.com/")
    ):
        return configured_url

    query = " ".join(
        value for value in (name, location, "Tây Ninh, Việt Nam") if value
    )
    return (
        "https://www.google.com/maps/search/?api=1&query="
        f"{quote_plus(query)}"
    )


def _row_to_dict(
    headers: list[str],
    row: tuple[Any, ...],
) -> dict[str, str]:
    record: dict[str, str] = {}

    for index, header in enumerate(headers):
        if not header:
            continue

        value = clean(row[index] if index < len(row) else "")

        if value:
            record[header] = value

    return record


def _load_supabase_rows() -> dict[str, list[dict[str, str]]]:
    if not DATABASE_URL:
        return {}

    if psycopg2 is None or RealDictCursor is None:
        logger.warning(
            "Supabase data load skipped: psycopg2 is not installed"
        )
        return {}

    sheets: dict[str, list[dict[str, str]]] = {}
    dsn = _psycopg2_dsn()

    try:
        with psycopg2.connect(
            dsn,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cursor:
                for table in DB_SHEETS:
                    try:
                        cursor.execute(
                            f'SELECT * FROM "{table}"'
                        )
                        rows = cursor.fetchall()

                    except Exception as exc:
                        conn.rollback()
                        logger.warning(
                            "Supabase table skipped: %s (%s)",
                            table,
                            exc,
                        )
                        continue

                    sheets[table] = [
                        {
                            key: cleaned_value
                            for key, value in dict(row).items()
                            if (cleaned_value := clean(value))
                        }
                        for row in rows
                    ]

    except Exception as exc:
        logger.exception(
            "Supabase data load skipped: %s",
            exc,
        )
        return {}

    return sheets


@lru_cache(maxsize=1)
def load_rows() -> dict[str, list[dict[str, str]]]:
    if DATABASE_URL:
        supabase_rows = _load_supabase_rows()

        if supabase_rows:
            return supabase_rows

        logger.warning(
            "Supabase returned no data; falling back to Excel"
        )

    if not DATA_PATH.exists():
        logger.warning("Excel file not found: %s", DATA_PATH)
        return {}

    workbook = load_workbook(
        DATA_PATH,
        read_only=True,
        data_only=True,
    )

    sheets: dict[str, list[dict[str, str]]] = {}

    for worksheet in workbook.worksheets:
        rows = worksheet.iter_rows(values_only=True)
        header_row = next(rows, None)

        if not header_row:
            continue

        headers = [
            clean(cell).lower().strip()
            for cell in header_row
        ]

        records = [
            _row_to_dict(headers, row)
            for row in rows
        ]

        sheets[worksheet.title] = [
            record
            for record in records
            if any(record.values())
        ]

    workbook.close()
    return sheets


@lru_cache(maxsize=1)
def destinations() -> dict[int, dict[str, Any]]:
    sheets = load_rows()

    media_by_dest: dict[str, dict[str, str]] = {}
    navigation_by_dest: dict[str, dict[str, str]] = {}

    for media in sheets.get("media_assets", []):
        media_by_dest.setdefault(
            media.get("dest_id", ""),
            media,
        )

    for navigation in sheets.get("maps_navigation", []):
        navigation_by_dest.setdefault(
            navigation.get("dest_id", ""),
            navigation,
        )

    result: dict[int, dict[str, Any]] = {}

    for index, record in enumerate(
        sheets.get("destinations", []),
        start=1,
    ):
        dest_id = record.get("dest_id", "")
        media = media_by_dest.get(dest_id, {})
        navigation = navigation_by_dest.get(dest_id, {})
        name = record.get("name", "Điểm đến Núi Bà Đen")
        location = record.get("location", "")

        result[index] = {
            "id": index,
            "dest_code": dest_id,
            "name": name,
            "category": record.get("category", ""),
            "location": location,
            "short_description": record.get(
                "description_short",
                "",
            ),
            "description_detail": record.get(
                "description_detail",
                "",
            ),
            "highlight": record.get("highlight", ""),
            "best_time": record.get("best_time", ""),
            "estimated_duration": record.get(
                "estimated_duration",
                "",
            ),
            "travel_type": record.get("travel_type", ""),
            "difficulty_level": record.get(
                "difficulty_level",
                "",
            ),
            "transport": record.get("transport", ""),
            "seo_keyword": record.get("seo_keyword", ""),
            "source_url": record.get("source_url", ""),
            "google_maps_url": google_maps_url_for_dest(
                navigation,
                name,
                location,
            ),
            "map_place_name": navigation.get("place_name", ""),
            "map_area": navigation.get("area", ""),
            "navigation_note": navigation.get("navigation_note", ""),
            "coordinates_or_altitude": navigation.get(
                "coordinates_or_altitude",
                "",
            ),
            "image_url": image_url_for_dest(
                media.get("image_url", "")
            ),
            "image_caption": media.get("caption", ""),
            "image_alt": media.get("alt_text", ""),
        }

    return result


def _title_for_record(
    sheet: str,
    record: dict[str, str],
) -> str:
    for key in (
        "name",
        "title",
        "question",
        "service_name",
        "activity_name",
        "place_name",
        "spot_name",
        "event_name",
        "organization",
        "keyword",
    ):
        if record.get(key):
            return record[key]

    return sheet


def _record_text(
    sheet: str,
    record: dict[str, str],
) -> str:
    labels = [
        f"sheet: {sheet}",
        f"title: {_title_for_record(sheet, record)}",
    ]

    labels.extend(
        f"{key}: {value}"
        for key, value in record.items()
        if value
    )

    return "\n".join(labels)


@lru_cache(maxsize=1)
def rag_documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []

    for sheet, records in load_rows().items():
        for row_index, record in enumerate(
            records,
            start=2,
        ):
            documents.append(
                {
                    "id": f"{sheet}:{row_index}",
                    "sheet": sheet,
                    "type": sheet,
                    "title": _title_for_record(
                        sheet,
                        record,
                    ),
                    "dest_code": (
                        record.get("dest_id")
                        or record.get("place_id")
                        or ""
                    ),
                    "source_url": record.get(
                        "source_url",
                        "",
                    ),
                    "text": _record_text(
                        sheet,
                        record,
                    ),
                }
            )

    return documents


def clear_data_cache() -> None:
    load_rows.cache_clear()
    destinations.cache_clear()
    rag_documents.cache_clear()


def data_revision() -> str:
    payload = json.dumps(
        load_rows(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def refresh_data_if_stale(force: bool = False) -> dict[str, Any]:
    global _last_refresh_monotonic

    now = time.monotonic()
    if not force and now - _last_refresh_monotonic < DATA_REFRESH_SECONDS:
        return {
            "checked": False,
            "changed": False,
            "revision": data_revision(),
        }

    with _refresh_lock:
        now = time.monotonic()
        if not force and now - _last_refresh_monotonic < DATA_REFRESH_SECONDS:
            return {
                "checked": False,
                "changed": False,
                "revision": data_revision(),
            }

        previous_revision = data_revision()
        clear_data_cache()
        current_revision = data_revision()
        _last_refresh_monotonic = now

        return {
            "checked": True,
            "changed": previous_revision != current_revision,
            "revision": current_revision,
        }


def data_stats() -> dict[str, Any]:
    sheets = load_rows()

    return {
        "postgres_enabled": enabled(),
        "data_source": (
            "supabase"
            if DATABASE_URL and sheets
            else "excel"
        ),
        "data_path": str(DATA_PATH),
        "data_exists": DATA_PATH.exists(),
        "sheets": {
            name: len(rows)
            for name, rows in sheets.items()
        },
        "destinations": len(destinations()),
        "documents": len(rag_documents()),
    }
