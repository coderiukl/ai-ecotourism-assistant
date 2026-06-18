from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.db import postgres

logger = logging.getLogger(__name__)

QR_CODES = {
    "ECO_NUI_BA_DEN_001": {
        "destination_id": 1,
        "expired": False,
    }
}


class QRScanRequest(BaseModel):
    qr_code: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    destination_id: int | None = None
    session_id: str = "default"


async def safe_save_chat(
    session_id: str,
    destination_id: int | None,
    question: str,
    answer: str,
    metadata: dict[str, Any],
) -> None:
    try:
        await postgres.save_chat(session_id, destination_id, question, answer, metadata)
    except Exception as exc:
        logger.warning("Chat persistence skipped: %s", exc)