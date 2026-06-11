from __future__ import annotations

import json
import logging
from typing import Any

try:
    import asyncpg
except Exception:  # pragma: no cover - optional dependency at runtime
    asyncpg = None

from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)
_pool: Any | None = None


def _normalize_dsn() -> tuple[str, dict[str, Any]]:
    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    kwargs: dict[str, Any] = {}
    if "ssl=require" in dsn or "sslmode=require" in dsn:
        dsn = dsn.replace("?ssl=require", "").replace("&ssl=require", "")
        dsn = dsn.replace("?sslmode=require", "").replace("&sslmode=require", "")
        kwargs["ssl"] = "require"
    return dsn, kwargs


async def connect() -> None:
    global _pool
    if not DATABASE_URL or _pool is not None:
        return
    if asyncpg is None:
        logger.warning("Postgres disabled: asyncpg is not installed")
        return
    try:
        dsn, kwargs = _normalize_dsn()
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5, **kwargs)
        await migrate()
        logger.info("Postgres connected")
    except Exception as exc:
        _pool = None
        logger.warning("Postgres disabled: %s", exc)


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


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
                role text not null check (role in ('user','assistant')),
                content text not null,
                metadata jsonb not null default '{}'::jsonb,
                created_at timestamptz not null default now()
            );
            """
        )


async def save_chat(session_id: str, destination_id: int | None, user_message: str, assistant_message: str, metadata: dict[str, Any]) -> None:
    if _pool is None:
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            insert into chat_sessions(session_id, destination_id, updated_at)
            values($1, $2, now())
            on conflict(session_id) do update set destination_id = excluded.destination_id, updated_at = now()
            """,
            session_id,
            destination_id,
        )
        await conn.execute(
            "insert into chat_messages(session_id, role, content, metadata) values($1, 'user', $2, '{}'::jsonb)",
            session_id,
            user_message,
        )
        await conn.execute(
            "insert into chat_messages(session_id, role, content, metadata) values($1, 'assistant', $2, $3::jsonb)",
            session_id,
            assistant_message,
            json.dumps(metadata, ensure_ascii=False),
        )


def enabled() -> bool:
    return _pool is not None
