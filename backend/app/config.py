import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass

# Paths
DATA_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT",DATA_DIR.parent.parent,))

XLSX_PATH = PROJECT_ROOT / "nui_ba_den_tourism_database.xlsm"
IMAGES_DIR = PROJECT_ROOT / "images"

# ChromaDB
CHROMA_DIR = DATA_DIR.parent / "chroma_db"
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nui_ba_den_rag")

# Embedding / RAG
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RAG_EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "384"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_USE_SENTENCE_TRANSFORMER = os.getenv("RAG_USE_SENTENCE_TRANSFORMER", "false").lower() == "true"

# Claude / Anthropic

ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.huyztech.store/v1/ai").rstrip("/")
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY", "").strip())
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_AUTH_HEADER = os.getenv("ANTHROPIC_AUTH_HEADER", "x-api-key")
ANTHROPIC_MESSAGES_URL = os.getenv("ANTHROPIC_MESSAGES_URL", "")
ANTHROPIC_USER_AGENT = os.getenv("ANTHROPIC_USER_AGENT", "PostmanRuntime/7.43.0")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1200"))
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "5"))
ANTHROPIC_MAX_RETRIES = int(os.getenv("ANTHROPIC_MAX_RETRIES", "0"))

# Chat Memory

CHAT_SESSION_MAX_TURNS = int(os.getenv("CHAT_SESSION_MAX_TURNS", "10"))

CHAT_SESSION_TTL_SECONDS = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "1800"))

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
if DEBUG:
    print("===== CONFIG =====")
    print("BASE_URL:", ANTHROPIC_BASE_URL)
    print("MODEL:", ANTHROPIC_MODEL)
    print("API_KEY:", "***" if ANTHROPIC_API_KEY else "MISSING")
    print("TOP_K:", RAG_TOP_K)
    print("==================")     
