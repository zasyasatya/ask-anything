"""Ask Anything — FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, db
from .api.routes import router
from .config import settings
from .local_llm import runtime as llm_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db(settings.db_path)
    settings.resolved_models_dir().mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        # Never orphan a llama-server we started for an offline model.
        await llm_runtime.stop()


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
