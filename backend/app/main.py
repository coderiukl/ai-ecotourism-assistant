from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import (
    AUTO_BUILD_CHROMA_ON_STARTUP,
    CORS_ORIGIN_REGEX,
    CORS_ORIGINS,
    DATA_REFRESH_SECONDS,
    RAG_AUTO_REFRESH,
)
from app.core.logging import configure_logging
from app.db import postgres

configure_logging()
logger = logging.getLogger(__name__)


def _refresh_rag_index() -> None:
    from app.rag import vector_store

    result = vector_store.refresh_if_stale(force_data_refresh=True)
    logger.info("RAG refresh finished: %s", result.get("status"))


async def _background_rag_maintenance() -> None:
    await asyncio.sleep(1)

    while True:
        try:
            await asyncio.to_thread(_refresh_rag_index)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Automatic RAG refresh skipped: %s", exc)

        if not RAG_AUTO_REFRESH:
            return

        await asyncio.sleep(DATA_REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres.connect()

    chroma_task = None
    if AUTO_BUILD_CHROMA_ON_STARTUP or RAG_AUTO_REFRESH:
        chroma_task = asyncio.create_task(_background_rag_maintenance())

    yield

    if chroma_task and not chroma_task.done():
        chroma_task.cancel()

    await postgres.close()

def create_app() -> FastAPI:
    app = FastAPI(title="AI Ecotourism Assistant", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_origin_regex=CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
