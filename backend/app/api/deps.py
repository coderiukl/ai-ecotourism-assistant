from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

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


class ChatHistoryItem(BaseModel):
    role: str
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        return role

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        return value.strip()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    destination_id: int | None = None
    session_id: str = Field("default", min_length=1, max_length=120)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=8)

    @field_validator("message", "session_id")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


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
