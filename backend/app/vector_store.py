import hashlib
import json

from .config import CHROMA_COLLECTION, CHROMA_DIR, RAG_EMBEDDING_DIM, RAG_EMBEDDING_MODEL

MANIFEST_FILE = CHROMA_DIR / "manifest.json"


def _load_chromadb():
    try:
        import chromadb
    except Exception:
        return None
    return chromadb


def _metadata_for(document):
    metadata = {
        "type": document.get("type") or "",
        "title": document.get("title") or "",
        "source_url": document.get("source_url") or "",
        "dest_code": str(document.get("dest_code") or ""),
    }
    if document.get("destination_id") is not None:
        metadata["destination_id"] = int(document["destination_id"])
    return metadata


def _fingerprint(documents):
    payload = {
        "embedding_model": RAG_EMBEDDING_MODEL,
        "embedding_dim": RAG_EMBEDDING_DIM,
        "documents": [
            {
                "id": document["id"],
                "text": document["text"],
                "metadata": _metadata_for(document),
            }
            for document in documents
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_manifest():
    if not MANIFEST_FILE.exists():
        return {}
    try:
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_manifest(fingerprint, documents):
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "collection": CHROMA_COLLECTION,
                "embedding_model": RAG_EMBEDDING_MODEL,
                "embedding_dim": RAG_EMBEDDING_DIM,
                "documents": len(documents),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _get_client():
    chromadb = _load_chromadb()
    if chromadb is None:
        return None
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _create_collection(client):
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def ensure_collection(documents, embed_text):
    try:
        client = _get_client()
    except Exception:
        return None
    if client is None:
        return None

    fingerprint = _fingerprint(documents)
    manifest = _read_manifest()

    try:
        collection = _create_collection(client)
    except Exception:
        return None

    try:
        current_count = collection.count()
    except Exception:
        return None

    if manifest.get("fingerprint") == fingerprint and current_count == len(documents):
        return collection

    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass

    collection = _create_collection(client)
    ids = [document["id"] for document in documents]
    texts = [document["text"] for document in documents]
    metadatas = [_metadata_for(document) for document in documents]
    embeddings = [embed_text(document["text"]) for document in documents]

    try:
        collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )
    except Exception:
        return None

    _write_manifest(fingerprint, documents)
    return collection


def query_collection(documents, embed_text, question, top_k, destination_id=None, dest_code=None):
    collection = ensure_collection(documents, embed_text)

    try:
        collection_count = collection.count() if collection else 0
    except Exception:
        return None

    if collection_count == 0:
        return None

    where = None
    if destination_id is not None:
        where = {"destination_id": destination_id}
    elif dest_code is not None:
        where = {"dest_code": dest_code}

    n_results = min(max(top_k * 4, top_k), collection_count)
    try:
        result = collection.query(
            query_embeddings=[embed_text(question)],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where=where,
        )
    except Exception:
        return None

    contexts = []

    for index, document_id in enumerate(result.get("ids", [[]])[0]):
        metadata = result.get("metadatas", [[]])[0][index] or {}
        distance = result.get("distances", [[]])[0][index]
        score = 1 - float(distance)

        if metadata.get("type") in {"service_pricing", "activity", "faq", "knowledge_base"}:
            pass
        if destination_id is not None and metadata.get("destination_id") != destination_id:
            continue
        if dest_code is not None and metadata.get("dest_code") != dest_code:
            continue

        contexts.append(
            {
                "score": round(score, 4),
                "id": document_id,
                "type": metadata.get("type"),
                "title": metadata.get("title"),
                "source_url": metadata.get("source_url"),
                "text": result.get("documents", [[]])[0][index],
            }
        )

    contexts.sort(key=lambda item: item["score"], reverse=True)
    return contexts[:top_k]


def vector_store_status(documents, embed_text):
    chromadb = _load_chromadb()

    if chromadb is None:
        return {
            "vector_store": "chromadb_missing",
            "persisted": False,
            "path": str(CHROMA_DIR),
            "collection": CHROMA_COLLECTION,
        }

    collection = ensure_collection(documents, embed_text)

    if collection is None:
        return {
            "vector_store": "chromadb_error",
            "persisted": False,
            "path": str(CHROMA_DIR),
            "collection": CHROMA_COLLECTION,
        }

    return {
        "vector_store": "chromadb",
        "persisted": True,
        "path": str(CHROMA_DIR),
        "collection": CHROMA_COLLECTION,
        "collection_count": collection.count() if collection else 0,
    }
