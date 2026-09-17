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

from .. import db, hf_hub
from ..agent.loop import run_agent
from ..config import HF_MODES, settings, update_settings
from ..local_inference import dependencies, engine
from ..providers import build_provider
from ..providers.diagnostics import probe_endpoint
from ..providers.discovery import list_remote_models
from ..providers.url_utils import models_url

router = APIRouter(prefix="/api")

# Test seams: tests replace these with an httpx.MockTransport so discovery,
# diagnostics and Hub access can be exercised without a live server.
DISCOVERY_TRANSPORT: httpx.AsyncBaseTransport | None = None
DIAGNOSTICS_TRANSPORT: httpx.AsyncBaseTransport | None = None
HUB_TRANSPORT: httpx.AsyncBaseTransport | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class DeepResearchRequest(BaseModel):
    topic: str
    max_queries: int | None = None
    max_results_per_query: int | None = None


class ModelsProbe(BaseModel):
    """Probe an endpoint's model list *before* the settings are saved.

    `base_url` / `api_key` default to the stored values of `provider`; an
    explicit `api_key` (including "") overrides them so the UI can test a key
    the user just typed (or deliberately cleared).
    """

    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    #: hanya dipakai `/models/test`: model yang baru diketik di UI
    model: str | None = None


class SettingsUpdate(BaseModel):
    provider: str | None = None
    hf_mode: str | None = None
    hf_base_url: str | None = None
    hf_model: str | None = None
    hf_api_key: str | None = None
    hf_token: str | None = None
    hf_device: str | None = None
    hf_dtype: str | None = None
    thinking: bool | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_api_key: str | None = None
    temperature: float | None = None
    max_steps: int | None = None
    logprobs: bool | None = None
    #: ke mana web_search mengarah (gateway pencarian internal / server demo)
    search_ddg_url: str | None = None

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

    @field_validator("hf_mode")
    @classmethod
    def _known_mode(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in HF_MODES:
            raise ValueError("hf_mode harus salah satu dari: local, server")
        return v


class RepoRequest(BaseModel):
    """Repo id travels in the body: it contains a `/` (org/name)."""

    repo_id: str
    thinking: bool | None = None
    load: bool = True          # langsung muat ke memori setelah dipilih
    device: str | None = None
    dtype: str | None = None


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
            # Snapshot akhir (bukan hanya teks): UI memakai ini untuk menyegarkan
            # kartu diagram + bar sitasi tanpa harus menunggu reload riwayat.
            await queue.put({"type": "agent_done", "conversation_id": cid,
                             "answer": result.get("answer", ""),
                             "sources": result.get("sources") or [],
                             "citations": result.get("citations") or {},
                             "diagrams": result.get("diagrams") or [],
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


@router.post("/deep-research")
async def deep_research(req: DeepResearchRequest):
    """Run deep research on a topic, streaming nodes for the canvas."""
    from ..deep_research import run_deep_research

    topic = (req.topic or "").strip()
    if not topic:
        return {"error": "topic tidak boleh kosong"}

    # Apply per-request overrides without mutating the global settings.
    research_settings = settings
    if req.max_queries or req.max_results_per_query:
        # Shallow copy of settings for this request only.
        import copy
        research_settings = copy.copy(settings)
        if req.max_queries:
            research_settings.deep_research_max_queries = req.max_queries
        if req.max_results_per_query:
            research_settings.deep_research_max_results_per_query = (
                req.max_results_per_query
            )

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            result = await run_deep_research(
                topic=topic,
                settings=research_settings,
                emit=emit,
            )
            # run_deep_research already emits research_done internally
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def gen() -> AsyncIterator[str]:
        try:
            yield _sse({"type": "start", "topic": topic})
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                except asyncio.TimeoutError:
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


@router.post("/models/test")
async def test_models(probe: ModelsProbe):
    """Replay the real requests against the endpoint and report each one.

    Ini jawaban untuk "kenapa masih error?": status HTTP + pesan server apa
    adanya untuk `GET /models`, chat non-streaming (bentuk contoh curl) dan
    chat streaming (yang dipakai app).
    """
    provider = (probe.provider or settings.provider or "").strip().lower()
    if provider == "mock":
        return {"ok": True, "provider": "mock",
                "checks": [{"name": "mode mock", "ok": True, "status": None,
                            "detail": "tidak memakai endpoint jaringan"}],
                "hint": None}

    if provider == "openai":
        base = settings.openai_base_url if probe.base_url is None else probe.base_url
        key = settings.openai_api_key if probe.api_key is None else probe.api_key
        model = settings.openai_model if probe.model is None else probe.model
    else:
        base = settings.hf_base_url if probe.base_url is None else probe.base_url
        key = settings.hf_api_key if probe.api_key is None else probe.api_key
        model = settings.hf_model if probe.model is None else probe.model

    report = await probe_endpoint(base, key, model,
                                  transport=DIAGNOSTICS_TRANSPORT)
    return {"provider": provider or "huggingface", **report}


# ---------------------------------------------------------------------------
# Offline models: HuggingFace Hub → models/ → inference lokal (transformers)
# ---------------------------------------------------------------------------
@router.get("/hf/search")
async def search_hf_models(q: str = "", limit: int = 20):
    result = await hf_hub.search_models(q, limit=limit, transport=HUB_TRANSPORT)
    return result


@router.get("/hf/models")
async def list_hf_models():
    return {
        "models_dir": str(hf_hub.models_dir()),
        "endpoint": settings.hf_endpoint,
        "models": hf_hub.list_local(),
        "downloads": hf_hub.all_downloads(),
        "engine": engine.status(),
        "deps": dependencies(),
        "active": {
            "provider": settings.provider,
            "hf_mode": settings.hf_mode,
            "hf_model": settings.hf_model,
            "thinking": settings.thinking,
        },
    }


@router.get("/hf/downloads")
async def hf_downloads():
    return {"downloads": hf_hub.all_downloads(),
            "models": hf_hub.list_local()}


@router.post("/hf/models/download")
async def download_hf_model(req: RepoRequest):
    try:
        state = hf_hub.start_download(req.repo_id, transport=HUB_TRANSPORT)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True, "repo_id": req.repo_id, "download": state,
            "models_dir": str(hf_hub.models_dir())}


@router.post("/hf/models/cancel")
async def cancel_hf_download(req: RepoRequest):
    return {"ok": hf_hub.cancel_download(req.repo_id),
            "download": hf_hub.download_state(req.repo_id)}


@router.post("/hf/models/delete")
async def delete_hf_model(req: RepoRequest):
    if engine.ready() and (engine.repo_id or "") == req.repo_id.strip("/"):
        await engine.unload()
    removed = hf_hub.delete_model(req.repo_id)
    if not removed:
        return {"error": "folder model tidak ditemukan"}
    return {"ok": True, "repo_id": req.repo_id}


@router.post("/hf/models/use")
async def use_hf_model(req: RepoRequest):
    """Select a downloaded model as the active one (and load it by default)."""
    try:
        result = hf_hub.use_model(req.repo_id, thinking=req.thinking)
    except FileNotFoundError as exc:
        return {"error": str(exc)}

    status = engine.status()
    if req.load:
        path = result["local_model_path"]
        try:
            status = engine.start_load(path, device=req.device, dtype=req.dtype)
        except RuntimeError as exc:      # torch/transformers belum ada
            return {"error": str(exc), "settings": result, "engine": status}
        if status["state"] == "error":
            return {"error": status["error"], "settings": result,
                    "engine": status}
    return {"ok": True, "repo_id": req.repo_id, "settings": result,
            "engine": status}


class LoadPathRequest(BaseModel):
    """Muat model dari SEMANGKAH folder di disk — bukan hanya `models/`.

    `path` boleh absolut (`/home/user/models/Qwen/Qwen2.5-0.5B-Instruct`),
    relatif ke project (`models/Qwen/...`), atau `~/...`. Ini jalur untuk
    model yang di-download manual (huggingface-cli, git, dsb.) ke luar folder
    default — "apapun modelnya yang ter-load, pasti jalan".
    """

    path: str
    repo_id: str | None = None
    thinking: bool | None = None
    device: str | None = None
    dtype: str | None = None


@router.post("/hf/models/load")
async def load_model_from_path(req: LoadPathRequest):
    raw = (req.path or "").strip().strip("'\"")
    if not raw:
        return {"error": "path folder model tidak boleh kosong"}
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    try:
        repo_id, manifest = hf_hub.register_model_folder(p, req.repo_id or "")
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    hf_hub.set_active(repo_id, str(p))

    patch: dict[str, Any] = {"provider": "huggingface", "hf_mode": "local",
                             "hf_model": repo_id}
    if req.thinking is not None:
        patch["thinking"] = bool(req.thinking)
    result = update_settings(**patch)
    result["local_model_path"] = str(p)

    status = engine.status()
    try:
        status = engine.start_load(str(p), device=req.device, dtype=req.dtype)
    except RuntimeError as exc:      # torch/transformers belum ada
        return {"error": str(exc), "settings": result, "engine": status}
    if status["state"] == "error":
        return {"error": status["error"], "settings": result,
                "engine": status}
    return {"ok": True, "repo_id": repo_id, "manifest": manifest,
            "settings": result, "engine": status}


@router.get("/hf/runtime")
async def hf_runtime_status():
    return engine.status()


@router.post("/hf/runtime/stop")
async def hf_runtime_stop():
    stopped = await engine.unload()
    return {"ok": True, "stopped": stopped, "engine": engine.status()}


@router.get("/health")
async def health():
    llm_reachable = False
    llm_error = None
    llm_status = None

    if settings.provider == "mock":
        # Mode demo offline tidak menyentuh jaringan apa pun: selalu sehat.
        # Tanpa cabang ini UI menampilkan banner "endpoint tidak menjawab" yang
        # menyesatkan justru saat orang mencoba mode offline.
        llm_reachable = True
    elif settings.provider == "huggingface" and settings.hf_mode != "server":
        # Mode lokal: "terjangkau" = model sudah dimuat (atau sedang dimuat).
        status = engine.status()
        llm_reachable = status["running"]
        llm_error = status.get("error") or (
            None if status["running"] else status.get("hint"))
        llm_status = None if status["running"] else 0
    elif settings.provider in ("huggingface", "openai"):
        base = (settings.hf_base_url if settings.provider == "huggingface"
                else settings.openai_base_url)
        key = (settings.hf_api_key if settings.provider == "huggingface"
               else settings.openai_api_key)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
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
        "hf_mode": settings.hf_mode,
        "model": settings.active_model_label(),
        "llm_reachable": llm_reachable,
        "llm_status": llm_status,
        "llm_error": llm_error,
        "local_llm": engine.ready(),
        "local_llm_state": engine.status()["state"],
    }
