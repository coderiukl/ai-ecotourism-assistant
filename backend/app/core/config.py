from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Always locate the backend environment file from this module. Relying on the
# process working directory makes `uvicorn` and Docker load different configs.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env", override=False)


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
BACKEND_DIR = _BACKEND_DIR
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[3]))

DATA_PATH = Path(
    os.getenv("DATA_PATH")
    or os.getenv("DATA_FILE")
    or PROJECT_ROOT / "nui_ba_den_tourism_database.xlsx"
)
if not DATA_PATH.is_absolute():
    DATA_PATH = PROJECT_ROOT / DATA_PATH

CHROMA_PATH = Path(os.getenv("CHROMA_PATH", BACKEND_DIR / "chroma_db"))
if not CHROMA_PATH.is_absolute():
    CHROMA_PATH = PROJECT_ROOT / CHROMA_PATH

CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nui_ba_den_rag")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
)
EMBEDDING_DIM = _int("EMBEDDING_DIM", _int("RAG_EMBEDDING_DIM", 384))
EMBEDDING_ALLOW_DOWNLOAD = _bool("EMBEDDING_ALLOW_DOWNLOAD", False)

RAG_TOP_K = _int("RAG_TOP_K", 8)
RAG_MIN_RELEVANCE_SCORE = float(os.getenv("RAG_MIN_RELEVANCE_SCORE", "0.05"))
AUTO_BUILD_CHROMA_ON_STARTUP = _bool("AUTO_BUILD_CHROMA_ON_STARTUP", False)
RAG_AUTO_REFRESH = _bool("RAG_AUTO_REFRESH", True)
DATA_REFRESH_SECONDS = max(30, _int("DATA_REFRESH_SECONDS", 300))

SUNWORLD_LIVE_SEARCH = _bool("SUNWORLD_LIVE_SEARCH", True)
SUNWORLD_SEARCH_TIMEOUT_SECONDS = float(os.getenv("SUNWORLD_SEARCH_TIMEOUT_SECONDS", "8"))
SUNWORLD_CACHE_SECONDS = max(60, _int("SUNWORLD_CACHE_SECONDS", 900))
SUNWORLD_SEARCH_MAX_PAGES = max(1, min(5, _int("SUNWORLD_SEARCH_MAX_PAGES", 3)))

# Optional general web search. Sun World remains the preferred first-party
# source; Tavily broadens coverage for time-sensitive visitor advice.
WEB_SEARCH_ENABLED = _bool("WEB_SEARCH_ENABLED", True)
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "tavily").strip().lower()
WEB_SEARCH_API_KEY = os.getenv(
    "WEB_SEARCH_API_KEY",
    os.getenv("TAVILY_API_KEY", ""),
).strip()
WEB_SEARCH_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "10"))
WEB_SEARCH_CACHE_SECONDS = max(60, _int("WEB_SEARCH_CACHE_SECONDS", 900))
WEB_SEARCH_MAX_RESULTS = max(1, min(5, _int("WEB_SEARCH_MAX_RESULTS", 3)))
WEB_KNOWLEDGE_RETENTION_DAYS = max(
    1,
    _int("WEB_KNOWLEDGE_RETENTION_DAYS", 90),
)
WEB_KNOWLEDGE_MAX_CONTEXTS = max(
    1,
    min(8, _int("WEB_KNOWLEDGE_MAX_CONTEXTS", 4)),
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
OPENAI_MAX_TOKENS = _int("OPENAI_MAX_TOKENS", 900)
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.55"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "production")).strip().lower()
DEBUG_RETRIEVAL = _bool("DEBUG_RETRIEVAL", APP_ENV not in {"production", "prod"})

CORS_ORIGINS = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "*").split(",")
    if item.strip()
]
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
