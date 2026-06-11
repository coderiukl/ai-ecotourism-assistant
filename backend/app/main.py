from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import CORS_ORIGINS, IMAGES_DIR
from app.core.logging import configure_logging
from app.db import postgres

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres.connect()
    yield
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
