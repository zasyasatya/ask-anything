"""Ask Anything — FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, db, hf_hub
from .api.admin import router as admin_router
from .api.routes import router
from .config import settings
from .local_inference import dependencies as _deps, engine as llm_engine


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
        return
    if not _deps()["available"]:
        print("[autoloader] torch/transformers belum ter-install — "
              "model lokal tidak di-load otomatis. "
              "python run.py --install-local", flush=True)
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
        print("[autoloader] belum ada model offline di models/ — "
              "unduh lewat Settings → Model offline (HuggingFace)", flush=True)
        return

    repo_id, path = target
    if settings.hf_model != repo_id:
        settings.hf_model = repo_id
        hf_hub.set_active(repo_id, path)
    try:
        llm_engine.start_load(path)
        print(f"[autoloader] memuat model {repo_id} dari {path} …", flush=True)
    except RuntimeError as exc:
        print(f"[autoloader] gagal memulai load: {exc}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db(settings.db_path)
    settings.resolved_models_dir().mkdir(parents=True, exist_ok=True)
    try:
        _autoload_local_model()
        yield
    finally:
        # Lepas model lokal (bebaskan RAM/VRAM) saat aplikasi berhenti.
        await llm_engine.unload()


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
