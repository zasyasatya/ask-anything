"""HTTP API: SSE chat stream, conversations CRUD, settings, health.

Semua endpoint di sini (kecuali `/api/health`) melewati dependency
`auth.current_principal`: mode `ASK_AUTH_MODE=required` menolak 401 tanpa sesi
login, mode `open` memperlakukan request sebagai admin anonim (test/demo).
Penegakan **peran** (admin vs member) mengikuti policy `governance.roles`:

  * member  → provider OpenAI saja (model offline diblokir), `/api/hf/*`,
              `POST /api/settings`, dan unggah dokumen RAG ditolak 403,
  * admin   → semuanya, sesuai policy global.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import HTTPException, Request, UploadFile

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from .. import (artifacts, auth, db, feedback, governance, hf_hub, ocr, quota,
                rag, startup)
from ..agent.loop import run_agent
from ..agent.rag_loop import run_rag_query
from ..auth import current_principal, require_admin
from ..config import HF_MODES, Settings, settings, update_settings
from ..local_inference import dependencies, engine
from ..providers import BaseProvider, build_provider
from ..providers.diagnostics import probe_endpoint
from ..providers.discovery import list_remote_models
from ..providers.url_utils import models_url

#: Router aplikasi — butuh sesi login (kecuali mode `open`).
router = APIRouter(prefix="/api", dependencies=[Depends(current_principal)])
#: Router publik: **hanya** health check. run.py & HEALTHCHECK Docker memanggil
#: `/api/health` tanpa kredensial, jadi endpoint ini tidak boleh ikut dijaga.
public_router = APIRouter(prefix="/api")

# Test seams: tests replace these with an httpx.MockTransport so discovery,
# diagnostics and Hub access can be exercised without a live server.
DISCOVERY_TRANSPORT: httpx.AsyncBaseTransport | None = None
DIAGNOSTICS_TRANSPORT: httpx.AsyncBaseTransport | None = None
HUB_TRANSPORT: httpx.AsyncBaseTransport | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    #: mode pipeline yang dipilih user di composer (gate oleh policy admin).
    mode: str = "text"
    #: playbook instruksi advanced yang dipilih eksplisit (opsional) —
    #: playbook `activation="manual"` hanya menyala lewat jalur ini.
    playbook_ids: list[str] | None = None


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


def _user_key(request: Request,
              principal: dict[str, Any] | None = None) -> str:
    """Identitas end user untuk kuota token.

    Urutan sumber, dari yang paling dipercaya:

    1. sesi login sungguhan (`principal["username"]`) — tidak bisa dipalsukan
       klien, jadi kuota menempel pada akun dan bukan pada perangkat;
    2. header `X-User-Id` — dipakai skrip/CLI dan `ASK_AUTH_MODE=open`;
    3. IP klien — supaya pemanggil anonim tetap terkena batas.

    Principal anonim mode `open` (`anonymous=True`) sengaja **tidak** dipakai:
    seluruh pemanggil akan berbagi satu kunci `user:anon` dan header identitas
    yang dikirim klien jadi tidak berpengaruh.
    """
    person = principal or {}
    username = ("" if person.get("anonymous")
                else (person.get("username") or "")).strip()
    if username:
        return quota.normalise_user(f"user:{username}")
    client_ip = request.client.host if request.client else ""
    return quota.normalise_user(request.headers.get(quota.USER_HEADER),
                                fallback_ip=client_ip)


def _quota_event(verdict: dict[str, Any], user_key: str) -> dict[str, Any]:
    """Payload event `quota` untuk Mechanistic Interpreter."""
    snapshot = verdict.get("status") or {}
    return {
        "user_key": user_key,
        "enabled": snapshot.get("enabled"),
        "limits": snapshot.get("limits"),
        "used": snapshot.get("used"),
        "remaining": snapshot.get("remaining"),
        "period": snapshot.get("period"),
        "over_limit": bool(verdict.get("over_limit")),
        "note": verdict.get("reason") or "",
    }


@router.get("/quota/me")
async def quota_me(request: Request,
                   principal: dict[str, Any] = Depends(current_principal)
                   ) -> dict:
    """Sisa kuota pemanggil — dipakai UI untuk menampilkan indikator kuota."""
    user_key = _user_key(request, principal)
    quota.touch_user(user_key)
    return quota.status(user_key)


# SSE keep-alive: a comment frame, ignored by clients but enough to stop
# proxies from closing a stream that is silent while the LLM thinks.
KEEPALIVE = ": keep-alive\n\n"
KEEPALIVE_S = 10.0


# ---------------------------------------------------------------------------
# Peran (admin | member) → penyedia LLM & pesan penolakan
# ---------------------------------------------------------------------------

def _scoped_settings(role: str) -> tuple[Settings, bool]:
    """Settings untuk peran ini; kembalikan (settings, dipaksa_openai).

    Role member tidak boleh menyentuh model offline. Bila policy-nya
    `chat_provider=openai` dan provider global bukan OpenAI (mis. HuggingFace
    lokal), request ini memakai salinan settings yang diarahkan ke OpenAI —
    tanpa mengubah setelan global yang dipakai admin.
    """
    forced = governance.role_setting(role, "chat_provider", "auto")
    if forced == "openai" and settings.provider not in ("openai", "mock"):
        scoped = copy.copy(settings)
        scoped.provider = "openai"
        scoped.hf_mode = "server"
        return scoped, True
    return settings, False


def _provider_for_role(role: str) -> tuple[BaseProvider | None, str | None]:
    """Provider + pesan error siap-tampil (tanpa melempar)."""
    scoped, forced = _scoped_settings(role)
    if forced and not (scoped.openai_api_key or "").strip():
        return None, (
            "Role member hanya memakai model OpenAI, tetapi API key OpenAI "
            "belum diatur. Minta admin mengisi Settings → Provider OpenAI "
            "(atau ubah akses per peran di Admin → Pipeline)."
        )
    return build_provider(scoped), None


def _mode_blocked_message(mode: str, role: str) -> str:
    if governance.mode_allowed(mode):
        return (f"Mode '{mode}' tidak diizinkan untuk role {role}. Admin bisa "
                "mengaktifkannya di halaman Admin → Pipeline (Akses per peran).")
    return f"Mode '{mode}' dimatikan oleh admin (halaman Admin → Pipeline)."


def _forbidden(message: str) -> HTTPException:
    return HTTPException(403, message)


def _owns_conversation(cid: str, principal: dict[str, Any]) -> bool:
    """Admin bebas; member hanya percakapan miliknya sendiri (manajemen sesi)."""
    if (principal or {}).get("role") == "admin":
        return True
    owner = db.conversation_owner(cid)
    return bool(owner) and owner == (principal or {}).get("id")


@router.post("/chat")
async def chat(req: ChatRequest, request: Request,
               principal: dict[str, Any] = Depends(current_principal)):
    role = (principal or {}).get("role") or "member"
    mode = (req.mode or "text").strip().lower()
    if not governance.mode_allowed(mode, role):
        return _sse_error_response(_mode_blocked_message(mode, role))

    provider, provider_error = _provider_for_role(role)
    if provider is None:
        return _sse_error_response(provider_error or "Provider tidak siap.")

    # --- gate kuota token per end user (sebelum model disentuh) -------------
    user_key = _user_key(request, principal)
    verdict = quota.check(user_key)
    if not verdict["allowed"]:
        quota.record_rejection(user_key, verdict["reason"], mode=mode)
        return _sse_error_response(verdict["reason"])

    conv = None
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id)
        if conv is not None and not _owns_conversation(conv["id"], principal):
            return _sse_error_response(
                "Percakapan ini milik user lain — buka percakapan sendiri.")
    if conv is None:
        conv = db.new_conversation(title=req.message[:64],
                                   user_id=(principal or {}).get("id") or "")
    cid = conv["id"]
    history = db.list_messages(cid)

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            result = await run_agent(
                conversation_id=cid,
                user_message=req.message,
                history=history,
                provider=provider,
                settings=settings,
                emit=emit,
                mode=mode,
                quota_status=_quota_event(verdict, user_key),
                playbook_ids=req.playbook_ids or None,
                role=role,
            )
            # Catat pemakaian nyata; kuota harian/mingguan memakai angka ini.
            snapshot = quota.record(
                user_key, result.get("usage"),
                conversation_id=cid, run_id=result.get("run_id", ""),
                mode=mode, provider=settings.provider,
                model=settings.active_model_label(),
            )
            # Snapshot akhir (bukan hanya teks): UI memakai ini untuk menyegarkan
            # kartu diagram + bar sitasi tanpa harus menunggu reload riwayat.
            await queue.put({"type": "agent_done", "conversation_id": cid,
                             "answer": result.get("answer", ""),
                             "message_id": result.get("message_id", ""),
                             "sources": result.get("sources") or [],
                             "citations": result.get("citations") or {},
                             "diagrams": result.get("diagrams") or [],
                             "quota": snapshot,
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
async def deep_research(req: DeepResearchRequest,
                        principal: dict[str, Any] = Depends(current_principal)):
    """Run deep research on a topic, streaming nodes for the canvas."""
    from ..deep_research import run_deep_research

    role = (principal or {}).get("role") or "member"
    if not governance.mode_allowed("research", role):
        return _sse({"type": "error",
                     "message": _mode_blocked_message("research", role)})
    topic = (req.topic or "").strip()
    if not topic:
        return {"error": "topic tidak boleh kosong"}

    # Apply per-request overrides without mutating the global settings.
    research_settings, _forced = _scoped_settings(role)
    if req.max_queries or req.max_results_per_query:
        # Shallow copy of settings for this request only.
        research_settings = copy.copy(research_settings)
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
async def list_conversations(
    principal: dict[str, Any] = Depends(current_principal),
):
    """Admin melihat semua sesi (lengkap pemiliknya), member hanya miliknya."""
    role = (principal or {}).get("role") or "member"
    if role == "admin":
        return {"conversations": db.list_conversations(), "scope": "all"}
    return {"conversations": db.list_conversations((principal or {}).get("id")),
            "scope": "own"}


@router.get("/conversations/{cid}")
async def get_conversation(cid: str,
                           principal: dict[str, Any] = Depends(current_principal)):
    conv = db.get_conversation(cid)
    if conv is None:
        return {"error": "not found"}
    if not _owns_conversation(cid, principal):
        raise HTTPException(403, "Percakapan ini milik user lain")
    return {
        "conversation": conv,
        "messages": db.list_messages(cid),
        "trace": db.list_trace(cid),
    }


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str,
                              principal: dict[str, Any] = Depends(current_principal)):
    if db.get_conversation(cid) is None:
        return {"ok": True}
    if not _owns_conversation(cid, principal):
        raise HTTPException(403, "Percakapan ini milik user lain")
    db.delete_conversation(cid)
    return {"ok": True}


@router.get("/settings")
async def get_settings(principal: dict[str, Any] = Depends(current_principal)):
    """Setelan publik. Key selalu termask; member tidak bisa mengubah apa pun."""
    role = (principal or {}).get("role") or "member"
    return {
        **settings.as_public_dict(),
        "role": role,
        "can_manage": governance.role_allows(role, "allow_provider_settings"),
        "capabilities": auth.capabilities(principal),
    }


@router.post("/settings")
async def post_settings(update: SettingsUpdate,
                        principal: dict[str, Any] = Depends(current_principal)):
    role = (principal or {}).get("role") or "member"
    if not governance.role_allows(role, "allow_provider_settings"):
        raise _forbidden(
            "Role member tidak bisa mengubah provider/model (Settings). "
            "Hubungi admin — lihat Admin → Pipeline → Akses per peran.")
    return update_settings(**update.model_dump())


# ---------------------------------------------------------------------------
# Model list of an OpenAI-compatible endpoint (dropdown in *Settings provider*)
# ---------------------------------------------------------------------------
@router.post("/models", dependencies=[Depends(require_admin)])
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


@router.post("/models/test", dependencies=[Depends(require_admin)])
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
@router.get("/hf/search", dependencies=[Depends(require_admin)])
async def search_hf_models(q: str = "", limit: int = 20):
    result = await hf_hub.search_models(q, limit=limit, transport=HUB_TRANSPORT)
    return result


@router.get("/hf/models", dependencies=[Depends(require_admin)])
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


@router.get("/hf/downloads", dependencies=[Depends(require_admin)])
async def hf_downloads():
    return {"downloads": hf_hub.all_downloads(),
            "models": hf_hub.list_local()}


@router.post("/hf/models/download", dependencies=[Depends(require_admin)])
async def download_hf_model(req: RepoRequest):
    try:
        state = hf_hub.start_download(req.repo_id, transport=HUB_TRANSPORT)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True, "repo_id": req.repo_id, "download": state,
            "models_dir": str(hf_hub.models_dir())}


@router.post("/hf/models/cancel", dependencies=[Depends(require_admin)])
async def cancel_hf_download(req: RepoRequest):
    return {"ok": hf_hub.cancel_download(req.repo_id),
            "download": hf_hub.download_state(req.repo_id)}


@router.post("/hf/models/delete", dependencies=[Depends(require_admin)])
async def delete_hf_model(req: RepoRequest):
    if engine.ready() and (engine.repo_id or "") == req.repo_id.strip("/"):
        await engine.unload()
    removed = hf_hub.delete_model(req.repo_id)
    if not removed:
        return {"error": "folder model tidak ditemukan"}
    return {"ok": True, "repo_id": req.repo_id}


@router.post("/hf/models/use", dependencies=[Depends(require_admin)])
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


@router.post("/hf/models/load", dependencies=[Depends(require_admin)])
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


@router.get("/hf/runtime", dependencies=[Depends(require_admin)])
async def hf_runtime_status():
    return engine.status()


@router.post("/hf/runtime/stop", dependencies=[Depends(require_admin)])
async def hf_runtime_stop():
    stopped = await engine.unload()
    return {"ok": True, "stopped": stopped, "engine": engine.status()}


@public_router.get("/health")
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

    from ..main import AUTOLOAD_STATE

    return {
        "status": "ok",
        "provider": settings.provider,
        "hf_mode": settings.hf_mode,
        # Kenapa backend jalan dalam mode terbatas (model lokal rusak, paket
        # opsional hilang, …). Dipakai run.py & UI agar sebabnya kelihatan.
        "warnings": startup.notes(),
        "autoload": dict(AUTOLOAD_STATE),
        "model": settings.active_model_label(),
        "llm_reachable": llm_reachable,
        "llm_status": llm_status,
        "llm_error": llm_error,
        "local_llm": engine.ready(),
        "local_llm_state": engine.status()["state"],
        # Kesiapan OCR ikut dilaporkan: mode RAG untuk dokumen scan bergantung
        # padanya, dan UI harus bisa mengatakan "belum aktif" alih-alih
        # menghasilkan index kosong tanpa penjelasan.
        "ocr": ocr.dependencies(),
    }


@router.get("/rag/ocr")
async def rag_ocr_status() -> dict:
    """Status mesin OCR + parameter yang sedang berlaku (panel RAG & admin)."""
    pol = governance.policy()["rag"]
    deps = ocr.dependencies()
    return {
        "deps": deps,
        "engine_selected": ocr.pick_engine(str(pol.get("ocr_engine") or "auto")),
        "policy": {k: v for k, v in pol.items() if k.startswith("ocr_")},
        "accepts": [".pdf", *rag.IMAGE_EXTENSIONS],
    }


# ---------------------------------------------------------------------------
# Pipeline governance (publik): UI membaca ini untuk menampilkan/menyembunyikan
# mode & tombol. Penegakan tetap server-side — endpoint ini bukan lapisan
# keamanan, hanya proyeksi policy yang aman untuk browser.
# ---------------------------------------------------------------------------

@router.get("/policy")
async def public_policy(
    principal: dict[str, Any] = Depends(current_principal),
) -> dict:
    """Policy efektif **untuk peran pemanggil** (member ↔ admin bisa berbeda)."""
    return governance.public_policy((principal or {}).get("role") or "member")


def _sse_error_response(message: str) -> StreamingResponse:
    """Chat-like endpoint menolak via SSE `error` event (bukan HTTP 4xx)
    supaya UI menampilkannya di dalam ruang chat, bukan sebagai fetch error."""
    async def gen() -> AsyncIterator[str]:
        yield _sse({"type": "error", "message": message})
    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Feedback 👍/👎 — terecord penuh, bisa menjadi pedoman perilaku (auto/apply)
# ---------------------------------------------------------------------------

class FeedbackIn(BaseModel):
    rating: str                 # "up" | "down"
    conversation_id: str = ""
    message_id: str = ""
    comment: str = ""

    @field_validator("rating")
    @classmethod
    def _known_rating(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in feedback.RATINGS:
            raise ValueError("rating harus 'up' atau 'down'")
        return v


@router.post("/feedback")
async def post_feedback(item: FeedbackIn) -> dict:
    pol = governance.policy()
    if not pol["feedback"]["enabled"]:
        raise HTTPException(403, "Feedback dimatikan oleh admin")
    # Konteks run ikut direcord supaya feedback bisa dianalisis & dipelajari.
    context: dict[str, Any] = {
        "model": settings.active_model_label(),
        "provider": settings.provider,
    }
    if item.message_id:
        msg = db.get_message(item.message_id)
        if msg is not None:
            context["answer_snippet"] = (msg.get("content") or "")[:400]
            meta = {}
            try:
                import json as _json
                meta = _json.loads(msg.get("meta") or "{}")
            except Exception:  # noqa: BLE001
                meta = {}
            context["mode"] = meta.get("mode", "text")
            tools_used = sorted({
                (t.get("name") or "") for t in (meta.get("tool_calls") or [])
                if t.get("name")
            })
            if tools_used:
                context["tools_used"] = tools_used
    fb = feedback.add_feedback(
        rating=item.rating, conversation_id=item.conversation_id,
        message_id=item.message_id, comment=item.comment, context=context,
    )
    applied = feedback.maybe_auto_apply(fb["id"], pol["feedback"])
    return {"feedback": fb,
            "auto_guidance": bool(applied),
            "guidance": (applied or {}).get("memory")}


# ---------------------------------------------------------------------------
# Artifact download (publik read — file dibuat oleh pipeline, bukan upload user)
# ---------------------------------------------------------------------------

@router.get("/artifacts/{aid}/download")
async def download_artifact(aid: str):
    from starlette.responses import Response

    found = artifacts.read_artifact(aid, settings=settings)
    if not found:
        raise HTTPException(404, "artifact tidak ditemukan")
    art, data = found
    return Response(
        content=data, media_type=art["mime"],
        headers={"Content-Disposition":
                 f'attachment; filename="{art["filename"]}"'},
    )


# ---------------------------------------------------------------------------
# RAG: upload PDF → parsing → chunking → embedding → index, lalu query
# ---------------------------------------------------------------------------

class RagQuery(BaseModel):
    question: str
    conversation_id: str | None = None
    document_ids: list[str] | None = None


#: Diisi bila `python-multipart` absen (lihat _register_rag_upload).
MULTIPART_HINT = ""


def _register_rag_upload() -> None:
    """Daftarkan POST /api/rag/upload — aman walau `python-multipart` hilang.

    FastAPI memvalidasi signature endpoint multipart saat *dekorasi route*
    (`ensure_multipart_is_installed`) dan melempar RuntimeError. Dulu itu
    terjadi saat import `app.api.routes`, sehingga seluruh backend gagal
    start hanya karena satu paket opsional tidak ter-install — gejalanya di
    `run.py` cuma "backend did not become healthy". Sekarang route-nya
    diganti versi 503 yang menjelaskan cara memperbaikinya.
    """
    global MULTIPART_HINT
    try:
        @router.post("/rag/upload")
        async def rag_upload(file: UploadFile, wait: bool = False,
                             principal: dict[str, Any] = Depends(current_principal)
                             ) -> dict:
            pol = governance.policy()
            role = (principal or {}).get("role") or "member"
            if not governance.mode_allowed("rag", role):
                raise HTTPException(403, _mode_blocked_message("rag", role))
            if not governance.role_allows(role, "allow_rag_upload"):
                raise HTTPException(
                    403,
                    "Role member tidak bisa menambah dokumen ke knowledge base. "
                    "Minta admin mengunggahnya (Admin → Pipeline → Akses per peran "
                    "bisa mengizinkan bila memang diinginkan).")
            data = await file.read()
            max_bytes = int(pol["rag"]["max_upload_mb"]) * 1024 * 1024
            if len(data) > max_bytes:
                raise HTTPException(413, f"PDF melebihi batas "
                                         f"{pol['rag']['max_upload_mb']} MB")
            name = file.filename or "dokumen.pdf"
            lowered = name.lower()
            allowed = (".pdf",) + rag.IMAGE_EXTENSIONS
            if not lowered.endswith(allowed):
                raise HTTPException(
                    415, "Format tidak didukung. Terima: PDF dan gambar ("
                         + ", ".join(e.lstrip('.') for e in rag.IMAGE_EXTENSIONS)
                         + ") — gambar & PDF hasil scan dibaca lewat OCR.")
            if lowered.endswith(rag.IMAGE_EXTENSIONS) and not ocr.available():
                raise HTTPException(
                    503, "Upload gambar butuh mesin OCR. " + ocr.INSTALL_HINT)
            # Default: proses di background. OCR halaman scan bisa memakan
            # puluhan detik per halaman, jadi memprosesnya inline membuat
            # request (dan proxy di depannya) timeout untuk dokumen tebal.
            # Klien memantau lewat GET /api/rag/documents — statusnya sudah
            # ditampilkan panel RAG per tahap.
            if wait:
                doc = rag.ingest_file(settings=settings, filename=name,
                                      data=data)
            else:
                doc = rag.ingest_file_background(settings=settings,
                                                 filename=name, data=data)
            return {"document": doc}

        return
    except RuntimeError as exc:  # python-multipart tidak ter-install
        MULTIPART_HINT = str(exc)

    startup.add("multipart", "Mode RAG: upload PDF tidak aktif karena paket "
                             "`python-multipart` tidak ter-install.",
                hint="pip install python-multipart (atau jalankan: "
                     "python run.py --install-only)",
                detail=MULTIPART_HINT)

    router.add_api_route("/rag/upload", rag_upload_unavailable,
                         methods=["POST"])


async def rag_upload_unavailable() -> dict:
    """Fallback mode RAG saat `python-multipart` tidak ada (bukan crash 500)."""
    raise HTTPException(
        503,
        "Upload PDF butuh paket `python-multipart` di environment backend. "
        "Jalankan: pip install python-multipart — atau `python run.py "
        "--install-only` dari root proyek.",
    )


_register_rag_upload()


@router.get("/rag/documents")
async def rag_documents() -> dict:
    return {"documents": rag.list_documents()}


@router.delete("/rag/documents/{doc_id}", dependencies=[Depends(require_admin)])
async def rag_delete_document(doc_id: str) -> dict:
    if not rag.delete_document(doc_id, settings=settings):
        raise HTTPException(404, "dokumen tidak ditemukan")
    return {"ok": True}


@router.post("/rag/query")
async def rag_query(req: RagQuery, request: Request,
                    principal: dict[str, Any] = Depends(current_principal)):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(422, "question wajib diisi")
    role = (principal or {}).get("role") or "member"
    if not governance.mode_allowed("rag", role):
        return _sse_error_response(_mode_blocked_message("rag", role))
    provider, provider_error = _provider_for_role(role)
    if provider is None:
        return _sse_error_response(provider_error or "Provider tidak siap.")
    # Query RAG juga memanggil LLM → ikut kuota token end user.
    user_key = _user_key(request, principal)
    verdict = quota.check(user_key)
    if not verdict["allowed"]:
        quota.record_rejection(user_key, verdict["reason"], mode="rag")
        return _sse_error_response(verdict["reason"])
    ready = [d for d in rag.list_documents() if d["status"] == "ready"]
    if not ready:
        return _sse_error_response(
            "Belum ada dokumen RAG yang siap — upload PDF dulu di panel RAG.")
    conv = None
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id)
        if conv is not None and not _owns_conversation(conv["id"], principal):
            return _sse_error_response(
                "Percakapan ini milik user lain — buka percakapan sendiri.")
    if conv is None:
        conv = db.new_conversation(title=f"RAG: {question[:56]}",
                                   user_id=(principal or {}).get("id") or "")
    cid = conv["id"]

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            result = await run_rag_query(
                conversation_id=cid, question=question, provider=provider,
                settings=settings, emit=emit,
                document_ids=req.document_ids or None,
                quota_status=_quota_event(verdict, user_key),
            )
            snapshot = quota.record(
                user_key, result.get("usage"),
                conversation_id=cid, run_id=result.get("run_id", ""),
                mode="rag", provider=settings.provider,
                model=settings.active_model_label(),
            )
            await queue.put({"type": "agent_done", "conversation_id": cid,
                             "answer": result.get("answer", ""),
                             "message_id": result.get("message_id", ""),
                             "pipeline": "rag",
                             "sources": result.get("sources") or [],
                             "citations": result.get("citations") or {},
                             "quota": snapshot,
                             "diagrams": [], "error": result.get("error")})
            db.touch_conversation(cid)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def gen() -> AsyncIterator[str]:
        try:
            yield _sse({"type": "start", "conversation_id": cid,
                        "pipeline": "rag"})
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
