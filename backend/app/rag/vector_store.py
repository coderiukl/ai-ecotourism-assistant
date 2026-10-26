from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Any

from app.core.config import CHROMA_COLLECTION, CHROMA_PATH, RAG_TOP_K
from app.rag.embeddings import embed_text
from app.db import postgres

logger = logging.getLogger(__name__)
_last_rebuild: dict[str, Any] = {"status": "idle"}
_rebuild_lock = threading.Lock()


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
    global _last_rebuild
    _last_rebuild = {"status": "running"}
    docs = postgres.rag_documents()
    source_revision = postgres.data_revision()

    try:
        coll = collection()
        batch_size = 16
        document_ids = {item["id"] for item in docs}
        existing_ids = set(coll.get(include=[]).get("ids") or [])
        stale_ids = sorted(existing_ids - document_ids)

        if stale_ids:
            coll.delete(ids=stale_ids)

        for start in range(0, len(docs), batch_size):
            batch = docs[start:start + batch_size]

            coll.upsert(
                ids=[item["id"] for item in batch],
                documents=[item["text"] for item in batch],
                metadatas=[_metadata(item) for item in batch],
                embeddings=[embed_text(item["text"]) for item in batch],
            )

            _last_rebuild = {"status": "running", "processed": min(start + batch_size, len(docs)), "total": len(docs)}

        coll.modify(metadata={"source_revision": source_revision})
        
        result = status()
        _last_rebuild = {"status": "done", **result}
        logger.info("Chroma collection rebuilt: %s docs", len(docs))
        return result
    except Exception as exc:
        _last_rebuild = {"status": "error", "message": str(exc)}
        raise

def rebuild_status() -> dict[str, Any]:
    return _last_rebuild


def ensure_index() -> None:
    coll = collection()
    if coll.count() == 0:
        logger.warning("Chroma collection is empty")


def refresh_if_stale(force_data_refresh: bool = False) -> dict[str, Any]:
    refresh = postgres.refresh_data_if_stale(force=force_data_refresh)
    coll = collection()
    source_revision = str(refresh.get("revision") or postgres.data_revision())
    indexed_revision = str((coll.metadata or {}).get("source_revision") or "")
    source_count = len(postgres.rag_documents())

    if (
        indexed_revision == source_revision
        and coll.count() == source_count
        and not refresh.get("changed")
    ):
        return {
            "status": "current",
            "source_revision": source_revision,
            "collection_count": coll.count(),
        }

    if not _rebuild_lock.acquire(blocking=False):
        return {"status": "running", "source_revision": source_revision}

    try:
        return {"status": "rebuilt", **rebuild_collection()}
    finally:
        _rebuild_lock.release()


def query(question: str, top_k: int = RAG_TOP_K, dest_code: str | None = None) -> list[dict[str, Any]]:
    ensure_index()
    
    coll = collection()
    count = coll.count()

    if count == 0:
        return []
    
    query_kwargs: dict[str, Any] = {
        "query_embeddings": [embed_text(question)],
        "n_results": min(top_k, coll.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    
    if dest_code:
        query_kwargs["where"] = {"dest_code": str(dest_code)}
    
    result = coll.query(**query_kwargs)

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
        "source_documents": len(postgres.rag_documents()),
        "index_ready": count > 0,
        "rebuild": _last_rebuild,
        "source_revision": postgres.data_revision(),
        "indexed_revision": str((coll.metadata or {}).get("source_revision") or "") if available else "",
        "error": error,
    }
