from pydantic import BaseModel


class QRScanRequest(BaseModel):
    qr_code: str


class ChatRequest(BaseModel):
    destination_id: int
    message: str
    session_id: str = "default"
