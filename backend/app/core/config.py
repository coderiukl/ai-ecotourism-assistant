from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[3]))

DATA_PATH = Path(os.getenv("DATA_PATH") or os.getenv("DATA_FILE") or PROJECT_ROOT / "nui_ba_den_tourism_database.xlsx")
if not DATA_PATH.is_absolute():
    DATA_PATH = PROJECT_ROOT / DATA_PATH

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", PROJECT_ROOT / "images"))
if not IMAGES_DIR.is_absolute():
    IMAGES_DIR = PROJECT_ROOT / IMAGES_DIR

CHROMA_PATH = Path(os.getenv("CHROMA_PATH", BACKEND_DIR / "chroma_db"))
if not CHROMA_PATH.is_absolute():
    CHROMA_PATH = PROJECT_ROOT / CHROMA_PATH
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nui_ba_den_rag")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
EMBEDDING_DIM = _int("EMBEDDING_DIM", _int("RAG_EMBEDDING_DIM", 384))
EMBEDDING_ALLOW_DOWNLOAD = _bool("EMBEDDING_ALLOW_DOWNLOAD", False)
RAG_TOP_K = _int("RAG_TOP_K", 6)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
OPENAI_MAX_TOKENS = _int("OPENAI_MAX_TOKENS", 900)
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "*").split(",") if item.strip()]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
