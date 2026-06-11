from __future__ import annotations

from pydantic import BaseModel, Field


class QRScanRequest(BaseModel):
    qr_code: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    destination_id: int | None = None
    session_id: str = "default"
