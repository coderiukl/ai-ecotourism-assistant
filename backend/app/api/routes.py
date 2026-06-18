from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.api.deps import QR_CODES, ChatRequest, QRScanRequest, safe_save_chat
from app.db import postgres
from app.rag.retriever import retrieve, status as rag_status
from app.rag.vector_store import rebuild_collection, rebuild_status
from app.services import chat_service, llm

router = APIRouter()

@router.get("/")
def root():
    return {
        "message": "AI Ecotourism Assistant backend is running",
        "postgres_enabled": postgres.enabled(),
    }

@router.get("/api/status")
def api_status():
    return {
        "data": postgres.data_stats(),
        "postgres_enabled": postgres.enabled(),
    }


@router.post("/api/qr/scan")
def scan_qr(payload: QRScanRequest):
    qr = QR_CODES.get(payload.qr_code.strip())

    if not qr:
        return {"status": "invalid", "message": "QR không thuộc hệ thống."}

    if qr["expired"]:
        return {"status": "expired", "message": "QR đã hết hạn."}

    return {
        "status": "valid",
        "message": "Quét QR thành công.",
        "destination": postgres.destinations().get(qr["destination_id"], {}),
    }

@router.get("/api/destinations")
def list_destinations():
    values = list(postgres.destinations().values())
    return {"total": len(values), "destinations": values}


@router.get("/api/destinations/{destination_id}")
def get_destination(destination_id: int):
    return postgres.destinations().get(destination_id, {})


@router.post("/api/chat")
async def chat(payload: ChatRequest):
    result = await chat_service.answer(
        payload.message,
        payload.destination_id,
        payload.session_id,
    )

    await safe_save_chat(
        payload.session_id,
        payload.destination_id,
        payload.message,
        result["answer"],
        result["retrieval"],
    )

    return result


@router.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest):
    destination = (
        postgres.destinations().get(payload.destination_id)
        if payload.destination_id
        else None
    )
    contexts = retrieve(payload.message, destination_id=payload.destination_id)

    async def events() -> AsyncGenerator[bytes, None]:
        answer = ""

        yield b"event: start\ndata: {}\n\n"

        async for token in llm.stream(payload.message, contexts, destination):
            answer += token
            body = json.dumps({"token": token}, ensure_ascii=False)
            yield f"event: token\ndata: {body}\n\n".encode("utf-8")

        retrieval = {
            "contexts": contexts,
            "used_llm": llm.configured(),
            "destination_id": payload.destination_id,
            "destination": destination,
        }

        await safe_save_chat(
            payload.session_id,
            payload.destination_id,
            payload.message,
            answer,
            retrieval,
        )

        body = json.dumps({"retrieval": retrieval}, ensure_ascii=False)
        yield f"event: done\ndata: {body}\n\n".encode("utf-8")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/rag/status")
def get_rag_status():
    return rag_status()


@router.post("/api/rag/rebuild")
def rebuild_rag(background_tasks: BackgroundTasks):
    current = rebuild_status()
    
    if current.get("status") == "running":
        return current
    
    background_tasks.add_task(rebuild_collection)
    return {"status": "queued", "message": "Chroma rebuild started in background."}

@router.get("/api/rag/rebuild/status")
def get_rebuild_status():
    try:
        return rebuild_status()
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.post("/api/rag/chat")
async def rag_chat(payload: ChatRequest):
    return await chat(payload)
