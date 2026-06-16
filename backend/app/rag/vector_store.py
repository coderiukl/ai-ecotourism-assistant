from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import CHROMA_COLLECTION, CHROMA_PATH, RAG_TOP_K
from app.rag.embeddings import embed_text
from app.services.excel_loader import rag_documents

logger = logging.getLogger(__name__)


def _metadata(document: dict[str, Any]) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {}
    for key in ("sheet", "type", "title", "dest_code", "source_url"):
        value = document.get(key)
        if value is not None:
            metadata[key] = str(value)
    return metadata


@lru_cache(maxsize=1)
def client():
    import chromadb

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


@lru_cache(maxsize=1)
def collection():
    return client().get_or_create_collection(name=CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})


def rebuild_collection() -> dict[str, Any]:
    docs = rag_documents()
    chroma_client = client()
    try:
        chroma_client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    coll = chroma_client.get_or_create_collection(name=CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})
    collection.cache_clear()

    batch_size = 128
    for start in range(0, len(docs), batch_size):
        batch = docs[start:start + batch_size]
        coll.add(
            ids=[item["id"] for item in batch],
            documents=[item["text"] for item in batch],
            metadatas=[_metadata(item) for item in batch],
            embeddings=[embed_text(item["text"]) for item in batch],
        )
    logger.info("Chroma collection rebuilt: %s docs", len(docs))
    return status()


def ensure_index() -> None:
    coll = collection()
    if coll.count() == 0:
        logger.warning("Chroma collection is empty; skipping rebuild during request")


def query(question: str, top_k: int = RAG_TOP_K) -> list[dict[str, Any]]:
    ensure_index()
    coll = collection()
    if coll.count() == 0:
        return []
    result = coll.query(
        query_embeddings=[embed_text(question)],
        n_results=min(top_k, coll.count()),
        include=["documents", "metadatas", "distances"],
    )
    contexts: list[dict[str, Any]] = []
    for index, doc_id in enumerate(result.get("ids", [[]])[0]):
        metadata = result.get("metadatas", [[]])[0][index] or {}
        distance = result.get("distances", [[]])[0][index]
        contexts.append({
            "id": doc_id,
            "score": round(1 - float(distance), 4),
            "text": result.get("documents", [[]])[0][index],
            **metadata,
        })
    return contexts


def status() -> dict[str, Any]:
    try:
        coll = collection()
        count = coll.count()
        available = True
        error = ""
    except Exception as exc:
        count = 0
        available = False
        error = str(exc)
    return {
        "chroma_available": available,
        "chroma_path": str(CHROMA_PATH),
        "collection": CHROMA_COLLECTION,
        "collection_count": count,
        "error": error,
    }
