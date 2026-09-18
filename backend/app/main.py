"""Ask Anything — FastAPI application entry point.

Prinsip startup: **server harus selalu hidup**. Model lokal (torch/transformers)
bersifat opsional dan sering rusak di Windows (`OSError WinError 1114` pada
`c10.dll`); kalau itu sampai melempar dari `lifespan`, uvicorn mati sebelum
membuka port dan `run.py` cuma melaporkan "backend did not become healthy".
Karena itu semua langkah opsional dibungkus, dicatat di `app.startup`, dan
dijalankan di background — health check tetap membalas walau model gagal.
"""
from __future__ import annotations

import threading
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, db, hf_hub, startup, tasks
from .api.admin import router as admin_router
from .api.routes import router
from .api.tasks import router as tasks_router
from .config import settings
from .local_inference import dependencies as _deps, engine as llm_engine

#: Hasil autoload terakhir (dibaca `/api/health`, bukan sumber kebenaran).
AUTOLOAD_STATE: dict[str, str] = {"state": "idle", "detail": ""}


def _autoload_local_model() -> None:
    """Muat model offline secara otomatis saat backend (re)start.

    Urutan prioritas:
      1. `settings.hf_model` bila foldernya ada di `models/`,
      2. model terakhir yang dipakai (`models/.active.json` — mencakup
         model dari folder di luar `models/`),
      3. model terunduh paling baru yang lengkap di `models/`.

    Load berjalan di background: server langsung sehat & UI menampilkan
    layar "memuat model…"; begitu engine siap, chat langsung bisa dipakai.
    """
    if settings.provider != "huggingface" or (settings.hf_mode or "local") != "local":
        AUTOLOAD_STATE.update(state="skipped", detail="provider bukan huggingface lokal")
        return

    deps = _deps()  # tak pernah melempar, termasuk saat DLL torch rusak
    if not deps["available"]:
        AUTOLOAD_STATE.update(state="unavailable", detail=deps.get("install_hint") or "")
        print("[autoloader] torch/transformers belum siap — model lokal tidak "
              "di-load otomatis. python run.py --install-local", flush=True)
        startup.add(
            "autoloader",
            "PyTorch/transformers belum bisa dijalankan, model lokal tidak dimuat.",
            hint="python run.py --install-local (mendeteksi torch rusak & "
                 "pasang ulang otomatis), atau jalankan dengan "
                 "--provider openai / --demo.",
            detail=deps.get("install_hint") or "",
        )
        return

    target: tuple[str, str] | None = None
    if settings.hf_model:
        path = hf_hub.resolve_local(settings.hf_model)
        if path is not None:
            target = (settings.hf_model, str(path))
        else:
            active = hf_hub.active_model()
            if active and active[0] == settings.hf_model:
                target = active
    if target is None:
        active = hf_hub.active_model()
        if active is not None:
            target = active
    if target is None:
        picked = hf_hub.auto_pick_model()
        if picked is not None:
            target = picked

    if target is None:
        AUTOLOAD_STATE.update(state="no-model", detail="")
        print("[autoloader] belum ada model offline di models/ — "
              "unduh lewat Settings → Model offline (HuggingFace)", flush=True)
        return

    repo_id, path = target
    if settings.hf_model != repo_id:
        settings.hf_model = repo_id
        hf_hub.set_active(repo_id, path)
    try:
        llm_engine.start_load(path)
    except Exception as exc:  # noqa: BLE001 - load model tidak boleh mematikan server
        AUTOLOAD_STATE.update(state="error", detail=f"{type(exc).__name__}: {exc}")
        print(f"[autoloader] gagal memulai load: {exc}", flush=True)
        startup.add("autoloader", f"Gagal memuat model {repo_id}.",
                    hint="Periksa folder model / coba model lebih kecil.",
                    detail=traceback.format_exc())
        return
    AUTOLOAD_STATE.update(state="loading", detail=repo_id)
    print(f"[autoloader] memuat model {repo_id} dari {path} …", flush=True)


def _run_autoload_in_background() -> None:
    """Jalankan autoload di thread daemon (startup tidak pernah tersandera)."""
    def worker() -> None:
        try:
            _autoload_local_model()
        except BaseException as exc:  # noqa: BLE001 - apa pun tak boleh mematikan server
            AUTOLOAD_STATE.update(state="error", detail=f"{type(exc).__name__}: {exc}")
            startup.add("autoloader", f"Autoload gagal: {type(exc).__name__}.",
                        detail=traceback.format_exc())

    threading.Thread(target=worker, name="model-autoload", daemon=True).start()


def _init_storage() -> None:
    """Siapkan SQLite + folder model/artifact. Gagal → pesan yang bisa ditindak."""
    try:
        db.init_db(settings.db_path)
    except Exception as exc:  # noqa: BLE001 - bungkus jadi pesan jelas
        raise RuntimeError(
            f"Tidak bisa menyiapkan database SQLite di '{settings.db_path}': "
            f"{type(exc).__name__}: {exc}\n"
            "Periksa apakah foldernya bisa ditulis (OneDrive/antivirus kadang "
            "mengunci file). Set ASK_DB_PATH ke lokasi lain bila perlu."
        ) from exc

    try:
        settings.resolved_models_dir().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        startup.add("storage",
                    f"Folder model '{settings.resolved_models_dir()}' tidak bisa dibuat.",
                    hint="Set ASK_MODELS_DIR ke folder lain yang bisa ditulis.",
                    detail=f"{type(exc).__name__}: {exc}")

    # Task management: isi papan dengan rencana RAG pada boot pertama.
    if settings.tasks_autoseed:
        try:
            created = tasks.seed_if_empty()
            if created:
                print(f"[tasks] {len(created)} task rencana dimuat ke papan "
                      f"(halaman /tasks)", flush=True)
        except Exception as exc:  # noqa: BLE001 - fitur tracker, bukan jalur kritis
            startup.add("tasks", "Gagal memuat task rencana ke papan.",
                        detail=f"{type(exc).__name__}: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_storage()
    _run_autoload_in_background()
    try:
        yield
    finally:
        # Lepas model lokal (bebaskan RAM/VRAM) saat aplikasi berhenti.
        try:
            await llm_engine.unload()
        except Exception:  # noqa: BLE001 - shutdown tidak boleh melempar
            pass


app = FastAPI(
    title="Ask Anything",
    version=__version__,
    description="Agentic AI chatbot: browsing + diagrams + mechanistic "
                "interpreter. HuggingFace local & OpenAI API providers.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
# Konsol admin: policy pipeline, memori, artifact, feedback (/api/admin/*).
app.include_router(admin_router)
# Task management: papan rencana RAG + integrasi branch GitLab (/api/tasks/*).
app.include_router(tasks_router)

# Serve docs/ (slides & metodologi) at /slides — frontend proxies /slides/*.
_DOCS = Path(__file__).resolve().parents[2] / "docs"
if _DOCS.is_dir():
    app.mount("/slides", StaticFiles(directory=_DOCS, html=True), name="slides")

# Screenshot dokumentasi (docs/images) — dipakai halaman /panduan & /developer.
_IMAGES = _DOCS / "images"
if _IMAGES.is_dir():
    app.mount("/docs-images", StaticFiles(directory=_IMAGES), name="docs-images")


@app.get("/")
async def root():
    return {
        "name": "Ask Anything",
        "version": __version__,
        "provider": settings.provider,
        "model": settings.active_model_label(),
        "hint": "frontend runs separately; API lives under /api",
    }
