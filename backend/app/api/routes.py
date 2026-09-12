"""HTTP API: SSE chat stream, conversations CRUD, settings, health."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from .. import db, hf_models
from ..agent.loop import run_agent
from ..config import settings, update_settings
from ..local_llm import runtime as llm_runtime
from ..providers import build_provider
from ..providers.discovery import list_remote_models
from ..providers.url_utils import models_url

router = APIRouter(prefix="/api")

# Test seam: tests replace this with an httpx.MockTransport so the model
# discovery endpoint can be exercised without a live LLM server.
DISCOVERY_TRANSPORT: httpx.AsyncBaseTransport | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ModelsProbe(BaseModel):
    """Probe an endpoint's model list *before* the settings are saved.

    `base_url` / `api_key` default to the stored values of `provider`; an
    explicit `api_key` (including "") overrides them so the UI can test a key
    the user just typed (or deliberately cleared).
    """

    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class SettingsUpdate(BaseModel):
    provider: str | None = None
    hf_base_url: str | None = None
    hf_model: str | None = None
    hf_api_key: str | None = None
    thinking: bool | None = None
    hf_port: int | None = None
    hf_ctx_size: int | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_api_key: str | None = None
    temperature: float | None = None
    max_steps: int | None = None
    logprobs: bool | None = None

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, v: str | None) -> str | None:
        """An unknown provider silently degraded to the HF default before."""
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("huggingface", "openai", "mock"):
            raise ValueError(
                "provider harus salah satu dari: huggingface, openai, mock")
        return v


class UseModelRequest(BaseModel):
    thinking: bool | None = None
    run: bool = False          # also (re)start llama-server on this GGUF
    port: int | None = None
    ctx: int | None = None


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# SSE keep-alive: a comment frame, ignored by clients but enough to stop
# proxies from closing a stream that is silent while the LLM thinks.
KEEPALIVE = ": keep-alive\n\n"
KEEPALIVE_S = 10.0


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
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                except asyncio.TimeoutError:
                    # SSE comment (bukan `data:`) → diabaikan klien, tetapi
                    # menjaga proxy (Next rewrite, nginx, Coolify) tidak menutup
                    # koneksi yang diam sementara LLM masih berpikir.
                    yield KEEPALIVE
                    continue
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


# ---------------------------------------------------------------------------
# Model list of an OpenAI-compatible endpoint (dropdown in *Settings provider*)
# ---------------------------------------------------------------------------
@router.post("/models")
async def list_models(probe: ModelsProbe):
    provider = (probe.provider or settings.provider or "").strip().lower()

    if provider == "mock":
        return {"ok": True, "provider": "mock", "base_url": None, "url": None,
                "status": None, "active_model": "mock-agent (offline demo)",
                "models": [{"id": "mock-agent", "label": "mock-agent (offline demo)"}],
                "count": 1, "error": None}

    if provider == "openai":
        base = settings.openai_base_url if probe.base_url is None else probe.base_url
        key = settings.openai_api_key if probe.api_key is None else probe.api_key
        active = settings.openai_model
    elif provider == "huggingface":
        base = settings.hf_base_url if probe.base_url is None else probe.base_url
        key = settings.hf_api_key if probe.api_key is None else probe.api_key
        active = settings.hf_model
    else:
        return {"ok": False, "provider": provider, "base_url": None, "url": None,
                "status": None, "active_model": None, "models": [], "count": 0,
                "error": f"provider tidak dikenal: {provider or '(kosong)'}"}

    result = await list_remote_models(base, key, transport=DISCOVERY_TRANSPORT)
    return {**result, "provider": provider, "base_url": base or None,
            "active_model": active, "count": len(result.get("models") or [])}


# ---------------------------------------------------------------------------
# Offline HuggingFace models (catalog → download → run with llama.cpp)
# ---------------------------------------------------------------------------
@router.get("/hf/models")
async def list_hf_models():
    return {
        "models_dir": str(hf_models.models_dir()),
        "endpoint": settings.hf_endpoint,
        "models": hf_models.list_models(),
        "runtime": llm_runtime.status(),
        "active": {
            "provider": settings.provider,
            "hf_model": settings.hf_model,
            "hf_base_url": settings.hf_base_url,
            "thinking": settings.thinking,
        },
    }


@router.post("/hf/models/{model_id}/download")
async def download_hf_model(model_id: str):
    if hf_models.get_spec(model_id) is None:
        return {"error": f"model tidak dikenal: {model_id}"}
    try:
        state = hf_models.start_download(model_id)
    except KeyError:
        return {"error": f"model tidak dikenal: {model_id}"}
    return {"ok": True, "model_id": model_id, "download": state,
            "models_dir": str(hf_models.models_dir())}


@router.post("/hf/models/{model_id}/delete")
async def delete_hf_model(model_id: str):
    if llm_runtime.alive() and llm_runtime.model_path:
        if Path(llm_runtime.model_path).name == Path(model_id).name:
            await llm_runtime.stop()
    removed = hf_models.delete_model(model_id)
    if not removed:
        return {"error": "file model tidak ditemukan"}
    return {"ok": True, "model_id": model_id}


@router.post("/hf/models/{model_id}/use")
async def use_hf_model(model_id: str, req: UseModelRequest):
    try:
        result = hf_models.use_model(model_id, thinking=req.thinking)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    runtime_status = llm_runtime.status()
    if req.run:
        path = result["local_model_path"]
        try:
            runtime_status = await llm_runtime.start(
                path, port=req.port, ctx=req.ctx)
        except (RuntimeError, FileNotFoundError) as exc:
            return {"error": str(exc), "settings": result,
                    "runtime": llm_runtime.status()}
        result = update_settings(
            hf_base_url=runtime_status["base_url"], hf_model=Path(path).name)
        result["local_model_path"] = path
    return {"ok": True, "model_id": model_id, "settings": result,
            "runtime": runtime_status}


@router.get("/hf/runtime")
async def hf_runtime_status():
    return llm_runtime.status()


@router.post("/hf/runtime/stop")
async def hf_runtime_stop():
    stopped = await llm_runtime.stop()
    return {"ok": True, "stopped": stopped, "runtime": llm_runtime.status()}


@router.get("/health")
async def health():
    llm_reachable = False
    llm_error = None
    llm_status = None
    if settings.provider in ("huggingface", "openai"):
        base = (settings.hf_base_url if settings.provider == "huggingface"
                else settings.openai_base_url)
        key = (settings.hf_api_key if settings.provider == "huggingface"
               else settings.openai_api_key)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(models_url(base), headers=headers)
                llm_status = r.status_code
                # Any HTTP answer proves the endpoint exists; 401/403 just mean
                # the API key is missing/wrong — still "reachable".
                llm_reachable = r.status_code < 500
        except Exception as exc:  # noqa: BLE001
            llm_error = str(exc)
    return {
        "status": "ok",
        "provider": settings.provider,
        "model": settings.active_model_label(),
        "llm_reachable": llm_reachable,
        "llm_status": llm_status,
        "llm_error": llm_error,
        "local_llm": llm_runtime.status()["running"],
    }
