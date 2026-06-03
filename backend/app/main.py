import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import IMAGES_DIR
from .routes import router

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

_stream = logging.StreamHandler(sys.stdout)
_stream.setFormatter(_formatter)

_file = logging.FileHandler(LOG_FILE, encoding="utf-8", delay=True)
_file.setFormatter(_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stream, _file],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    application = FastAPI(title="AI Ecotourism Assistant MVP")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if IMAGES_DIR.exists():
        application.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

    application.include_router(router)
    logger.info("Logging ready -> %s", LOG_FILE)
    return application


app = create_app()
