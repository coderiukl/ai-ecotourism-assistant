from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

from app.core.config import EMBEDDING_ALLOW_DOWNLOAD, EMBEDDING_DIM, EMBEDDING_MODEL

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


@lru_cache(maxsize=1)
def _sentence_model():
    try:
        from sentence_transformers import SentenceTransformer

        if EMBEDDING_ALLOW_DOWNLOAD:
            return SentenceTransformer(EMBEDDING_MODEL)
        
        return SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
    except Exception as exc:
        logger.warning("SentenceTransformer unavailable, using hash embeddings: %s", exc)
        return None


def _fit(vector: list[float]) -> list[float]:
    if len(vector) > EMBEDDING_DIM:
        vector = vector[:EMBEDDING_DIM]
    elif len(vector) < EMBEDDING_DIM:
        vector = vector + [0.0] * (EMBEDDING_DIM - len(vector))

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    for token in _TOKEN_RE.findall((text or "").lower()):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        vector[index] += 1.0
    return _fit(vector)


def embed_text(text: str) -> list[float]:
    model = _sentence_model()

    if model is None:
        return _hash_embedding(text)
    
    vector = model.encode(text or "", normalize_embeddings=True)

    if hasattr(vector, "tolist"):
        vector = vector.tolist()
        
    return _fit([float(value) for value in vector])


def backend_name() -> str:
    return "sentence-transformer" if _sentence_model() is not None else "hash-fallback"
