"""HTTP API: SSE chat stream, conversations CRUD, settings, health."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from .. import db
from ..agent.loop import run_agent
from ..config import settings, update_settings
from ..providers import build_provider

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class SettingsUpdate(BaseModel):
    provider: str | None = None
    hf_base_url: str | None = None
    hf_model: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_api_key: str | None = None
    temperature: float | None = None


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    conv = None
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id)
    if conv is None:
        conv = db.new_conversation(title=req.message[:64])
    cid = conv["id"]
    history = db.list_messages(cid)

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            provider = build_provider(settings)
            result = await run_agent(
                conversation_id=cid,
                user_message=req.message,
                history=history,
                provider=provider,
                settings=settings,
                emit=emit,
            )
            await queue.put({"type": "agent_done", "conversation_id": cid,
                             "answer": result.get("answer", ""),
                             "error": result.get("error")})
            db.touch_conversation(cid)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def gen() -> AsyncIterator[str]:
        try:
            yield _sse({"type": "start", "conversation_id": cid})
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                yield _sse(ev)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations():
    return {"conversations": db.list_conversations()}


@router.get("/conversations/{cid}")
async def get_conversation(cid: str):
    conv = db.get_conversation(cid)
    if conv is None:
        return {"error": "not found"}
    return {
        "conversation": conv,
        "messages": db.list_messages(cid),
        "trace": db.list_trace(cid),
    }


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str):
    db.delete_conversation(cid)
    return {"ok": True}


@router.get("/settings")
async def get_settings():
    return settings.as_public_dict()


@router.post("/settings")
async def post_settings(update: SettingsUpdate):
    return update_settings(**update.model_dump())


@router.get("/health")
async def health():
    llm_reachable = False
    llm_error = None
    if settings.provider in ("huggingface", "openai"):
        base = (settings.hf_base_url if settings.provider == "huggingface"
                else settings.openai_base_url).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{base}/models")
                llm_reachable = r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            llm_error = str(exc)
    return {
        "status": "ok",
        "provider": settings.provider,
        "model": settings.active_model_label(),
        "llm_reachable": llm_reachable,
        "llm_error": llm_error,
    }
