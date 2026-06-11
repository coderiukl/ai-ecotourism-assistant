from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import AUTO_BUILD_CHROMA_ON_STARTUP, CORS_ORIGINS, IMAGES_DIR
from app.core.logging import configure_logging
from app.db import postgres

configure_logging()
logger = logging.getLogger(__name__)


def _build_chroma_if_empty() -> None:
    from app.rag import vector_store

    current = vector_store.status()
    if current.get("collection_count", 0) > 0:
        logger.info("Chroma startup build skipped: collection already has %s docs", current["collection_count"])
        return
    result = vector_store.rebuild_collection()
    logger.info("Chroma startup build finished: %s docs", result.get("collection_count", 0))


async def _background_chroma_build() -> None:
    try:
        await asyncio.sleep(1)
        await asyncio.to_thread(_build_chroma_if_empty)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Chroma startup build skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres.connect()
    chroma_task = None
    if AUTO_BUILD_CHROMA_ON_STARTUP:
        chroma_task = asyncio.create_task(_background_chroma_build())
    yield
    if chroma_task and not chroma_task.done():
        chroma_task.cancel()
    await postgres.close()


def create_app() -> FastAPI:
    application = FastAPI(title="AI Ecotourism Assistant", version="1.0.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if IMAGES_DIR.exists():
        application.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    application.include_router(router)
    return application


app = create_app()
