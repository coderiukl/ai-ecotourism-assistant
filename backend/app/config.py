import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DATA_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", DATA_DIR.parent.parent))

XLSX_PATH = PROJECT_ROOT / "nui_ba_den_tourism_database.xlsx"
IMAGES_DIR = PROJECT_ROOT / "images"
CHROMA_DIR = DATA_DIR.parent / "chroma_db"
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "nui_ba_den_rag")

RAG_EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
RAG_EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "384"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MESSAGES_URL = os.getenv("ANTHROPIC_MESSAGES_URL", "")
ANTHROPIC_AUTH_HEADER = os.getenv("ANTHROPIC_AUTH_HEADER", "x-api-key")
ANTHROPIC_USER_AGENT = os.getenv(
    "ANTHROPIC_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1200"))
CHAT_SESSION_MAX_TURNS = int(os.getenv("CHAT_SESSION_MAX_TURNS", "10"))
CHAT_SESSION_TTL_SECONDS = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "1800"))
