import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .constants import QR_CODES
from .data_loader import DESTINATIONS, WORKBOOK
from .memory import session_store
from .rag import rag_answer, rag_status as get_rag_status
from .schemas import ChatRequest, QRScanRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
def root():
    data_source = "xlsx" if WORKBOOK else "fallback (xlsx not found)"
    return {
        "message": "AI Ecotourism Assistant backend is running",
        "data_source": data_source,
        "destinations_count": len(DESTINATIONS),
    }


@router.post("/api/qr/scan")
def scan_qr(payload: QRScanRequest):
    qr = QR_CODES.get(payload.qr_code)
    if not qr:
        return {"status": "invalid", "message": "QR không thuộc hệ thống."}
    if qr["expired"]:
        return {"status": "expired", "message": "QR đã hết hạn."}
    destination = DESTINATIONS.get(qr["destination_id"], {})
    return {
        "status": "valid",
        "message": "Quét QR thành công.",
        "destination": destination,
    }


@router.get("/api/destinations")
def list_destinations():
    destinations = list(DESTINATIONS.values())
    return {"total": len(destinations), "destinations": destinations}


@router.get("/api/destinations/{destination_id}")
def get_destination(destination_id: int):
    return DESTINATIONS.get(destination_id, {})


@router.post("/api/chat")
def chat(payload: ChatRequest):
    session_store.get_or_create(
        payload.session_id, destination_id=payload.destination_id
    )
    return rag_answer(
        payload.message,
        destination_id=payload.destination_id,
        session_id=payload.session_id,
    )


@router.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest):
    session_store.get_or_create(
        payload.session_id, destination_id=payload.destination_id
    )

    async def event_generator() -> AsyncGenerator[bytes, None]:
        yield b"event: start\ndata: {}\n\n"
        result = rag_answer(
            payload.message,
            destination_id=payload.destination_id,
            session_id=payload.session_id,
        )
        answer = result.get("answer", "")
        for token in answer:
            payload_data = json.dumps({"token": token}, ensure_ascii=False)
            yield f"event: token\ndata: {payload_data}\n\n".encode("utf-8")
        done_payload = json.dumps(
            {"retrieval": result.get("retrieval", {})}, ensure_ascii=False
        )
        yield f"event: done\ndata: {done_payload}\n\n".encode("utf-8")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/api/chat/sessions/{session_id}")
def delete_session(session_id: str):
    existed = session_store.get(session_id) is not None
    session_store.delete(session_id)
    return {"deleted": existed}


@router.get("/api/chat/sessions/{session_id}")
def session_info(session_id: str):
    session = session_store.get(session_id)
    if not session:
        return {"exists": False}
    return {
        "exists": True,
        "destination_id": session.get("destination_id"),
        "turns": len(session.get("turns", [])),
        "expires_at": session.get("expires_at"),
    }


@router.get("/api/rag/status")
def rag_status():
    return get_rag_status()


@router.post("/api/rag/chat")
def rag_chat(payload: ChatRequest):
    return rag_answer(
        payload.message,
        destination_id=payload.destination_id,
        session_id=payload.session_id,
    )
