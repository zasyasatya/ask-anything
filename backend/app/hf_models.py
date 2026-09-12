"""Offline (HuggingFace) model manager: curated GGUF catalog + downloader.

The catalog is tuned for **8 GB laptops**: Q4_K_M quants of 1.7B–4B models fit
in ~2–4 GB of RAM, leaving room for OS + browser; the 8B option is included for
machines with swap. Files download straight into the project's `models/`
folder (`ASK_MODELS_DIR`) and can then be selected to run — with thinking
(reasoning) on or off — through llama.cpp's `llama-server`
(see `app/local_llm.py`).

Downloads stream with `httpx` (no extra dependency), support resume via HTTP
`Range`, and report progress through the module-level registry that
`GET /api/hf/models` polls.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .config import settings

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    repo_id: str
    filename: str
    quant: str
    params: str
    size_bytes: int
    ram: str
    thinking: bool          # template understands `enable_thinking`
    tools: bool             # native tool calling in the chat template
    note: str
    recommended: bool = False


#: Curated for a laptop with 8 GB RAM (sizes verified against the HF Hub).
CATALOG: list[ModelSpec] = [
    ModelSpec(
        id="qwen3-4b-instruct-2507-q4_k_m",
        name="Qwen3 4B Instruct 2507",
        repo_id="bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF",
        filename="Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        quant="Q4_K_M", params="4B", size_bytes=2_497_280_736,
        ram="≈3–4 GB", thinking=False, tools=True, recommended=True,
        note="Pilihan utama laptop 8 GB: cepat, tool-calling kuat, hemat RAM.",
    ),
    ModelSpec(
        id="qwen3-4b-q4_k_m",
        name="Qwen3 4B (hybrid thinking)",
        repo_id="Qwen/Qwen3-4B-GGUF",
        filename="Qwen3-4B-Q4_K_M.gguf",
        quant="Q4_K_M", params="4B", size_bytes=2_497_280_256,
        ram="≈3–4.5 GB", thinking=True, tools=True,
        note="Bisa berpikir (enable_thinking) — pilih ini untuk panel thinking.",
    ),
    ModelSpec(
        id="gemma-3-4b-it-q4_k_m",
        name="Gemma 3 4B IT",
        repo_id="ggml-org/gemma-3-4b-it-GGUF",
        filename="gemma-3-4b-it-Q4_K_M.gguf",
        quant="Q4_K_M", params="4B", size_bytes=2_489_757_856,
        ram="≈3–4 GB", thinking=False, tools=False,
        note="Multilingual kuat; tool-calling terbatas (template tanpa tools).",
    ),
    ModelSpec(
        id="llama-3.2-3b-instruct-q4_k_m",
        name="Llama 3.2 3B Instruct",
        repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
        filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        quant="Q4_K_M", params="3B", size_bytes=2_019_377_696,
        ram="≈2.5–3 GB", thinking=False, tools=True,
        note="Paling ringan & cepat di 8 GB; paling baik untuk bahasa Inggris.",
    ),
    ModelSpec(
        id="qwen3-1.7b-q8_0",
        name="Qwen3 1.7B (Q8_0)",
        repo_id="Qwen/Qwen3-1.7B-GGUF",
        filename="Qwen3-1.7B-Q8_0.gguf",
        quant="Q8_0", params="1.7B", size_bytes=1_834_426_016,
        ram="≈2–2.5 GB", thinking=True, tools=True,
        note="Ultra-ringan dengan kualitas Q8; mesin 4–8 GB tetap lancar.",
    ),
    ModelSpec(
        id="qwen3-8b-q4_k_m",
        name="Qwen3 8B",
        repo_id="Qwen/Qwen3-8B-GGUF",
        filename="Qwen3-8B-Q4_K_M.gguf",
        quant="Q4_K_M", params="8B", size_bytes=5_027_783_488,
        ram="≈6–7 GB", thinking=True, tools=True,
        note="Paling cerdas yang masih muat — di RAM 8 GB pakai ctx ≤ 4096 "
             "+ swap, atau GPU 8 GB.",
    ),
]

_BY_ID = {m.id: m for m in CATALOG}

# model_id -> live download state (polled by the UI).
_downloads: dict[str, dict[str, Any]] = {}
_tasks: dict[str, asyncio.Task] = {}


def get_spec(model_id: str) -> ModelSpec | None:
    return _BY_ID.get(model_id)


def models_dir() -> Path:
    return settings.resolved_models_dir()


def resolve_url(spec: ModelSpec) -> str:
    base = (settings.hf_endpoint or "https://huggingface.co").rstrip("/")
    return f"{base}/{spec.repo_id}/resolve/main/{spec.filename}?download=true"


def candidate_paths(spec: ModelSpec) -> list[Path]:
    """Where the GGUF may already live (original name wins, then our id)."""
    d = models_dir()
    return [d / spec.filename, d / f"{spec.id}.gguf"]


def local_file(spec: ModelSpec) -> Path:
    paths = candidate_paths(spec)
    for p in paths:
        if p.is_file():
            return p
    return paths[0]


def _local_info(spec: ModelSpec) -> dict[str, Any]:
    path = local_file(spec)
    if path.is_file():
        st = path.stat()
        return {"exists": True, "path": str(path), "size_bytes": st.st_size,
                "downloaded_at": int(st.st_mtime)}
    return {"exists": False, "path": str(path), "size_bytes": 0,
            "downloaded_at": None}


def custom_ggufs() -> list[dict[str, Any]]:
    """GGUFs sitting in the models folder that are not part of the catalog."""
    known = {p.name for m in CATALOG for p in candidate_paths(m)}
    d = models_dir()
    out: list[dict[str, Any]] = []
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.gguf")):
        if p.name in known:
            continue
        st = p.stat()
        out.append({
            "id": f"file:{p.name}",
            "name": p.stem,
            "repo_id": "",
            "filename": p.name,
            "quant": "",
            "params": "",
            "size_bytes": st.st_size,
            "ram": "–",
            "thinking": True,
            "tools": True,
            "note": "GGUF lokal (di luar katalog)",
            "recommended": False,
            "custom": True,
            "local": {"exists": True, "path": str(p), "size_bytes": st.st_size,
                      "downloaded_at": int(st.st_mtime)},
            "download": None,
        })
    return out


def download_state(model_id: str) -> dict[str, Any] | None:
    return _downloads.get(model_id)


def _set_state(model_id: str, **kw: Any) -> dict[str, Any]:
    state = _downloads.setdefault(model_id, {
        "model_id": model_id, "status": "idle", "downloaded": 0, "total": 0,
        "percent": 0.0, "speed_bps": 0.0, "error": None, "started_at": None,
        "finished_at": None,
    })
    state.update(kw)
    if state["total"]:
        state["percent"] = round(100.0 * state["downloaded"] / state["total"], 1)
    return state


def list_models() -> list[dict[str, Any]]:
    out = []
    for spec in CATALOG:
        d = asdict(spec)
        d["local"] = _local_info(spec)
        d["download"] = download_state(spec.id)
        out.append(d)
    out.extend(custom_ggufs())
    return out


def resolve_local(model_id: str) -> Path | None:
    """Path of a downloaded model (catalog id or `file:<name>.gguf`)."""
    if model_id.startswith("file:"):
        p = models_dir() / Path(model_id[5:]).name
        return p if p.is_file() else None
    spec = get_spec(model_id)
    if spec is None:
        return None
    path = local_file(spec)
    return path if path.is_file() else None


async def _download(model_id: str,
                    transport: httpx.AsyncBaseTransport | None = None) -> None:
    spec = get_spec(model_id)
    assert spec is not None  # validated by start_download
    models_dir().mkdir(parents=True, exist_ok=True)
    target = local_file(spec)
    part = target.with_suffix(target.suffix + ".part")

    resume = part.stat().st_size if part.is_file() else 0
    state = _set_state(model_id, status="downloading", downloaded=resume,
                       total=spec.size_bytes, error=None,
                       started_at=time.time(), finished_at=None)
    headers = {"User-Agent": settings.user_agent}
    if resume:
        headers["Range"] = f"bytes={resume}-"

    t0 = time.time()
    try:
        timeout = httpx.Timeout(connect=20.0, read=300.0, write=60.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                     transport=transport) as client:
            async with client.stream("GET", resolve_url(spec),
                                     headers=headers) as resp:
                if resp.status_code not in (200, 206):
                    body = (await resp.aread()).decode("utf-8", "replace")
                    raise RuntimeError(
                        f"HTTP {resp.status_code} dari {resolve_url(spec)}: "
                        f"{body[:200]}")
                length = resp.headers.get("content-length")
                total = (int(length) + resume) if (
                    length and resp.status_code == 206) else (
                    int(length) if length else spec.size_bytes)
                if resp.status_code != 206 and part.is_file():
                    part.unlink()  # server ignored Range → start over
                    state["downloaded"] = 0
                state["total"] = total or spec.size_bytes
                mode = "ab" if (resume and resp.status_code == 206) else "wb"
                with part.open(mode) as fh:
                    async for chunk in resp.aiter_bytes(CHUNK):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        state["downloaded"] += len(chunk)
                        if state["total"]:
                            state["percent"] = round(
                                100.0 * state["downloaded"] / state["total"], 1)
                        elapsed = max(time.time() - t0, 0.001)
                        state["speed_bps"] = round(
                            (state["downloaded"] - (resume if mode == "ab" else 0))
                            / elapsed, 1)
        if target.exists():
            target.unlink()
        part.replace(target)
        _set_state(model_id, status="ready", downloaded=target.stat().st_size,
                   total=target.stat().st_size, percent=100.0,
                   finished_at=time.time())
    except (httpx.HTTPError, OSError, RuntimeError) as exc:
        _set_state(model_id, status="error", error=str(exc),
                   finished_at=time.time())
    finally:
        _tasks.pop(model_id, None)


def start_download(model_id: str,
                   transport: httpx.AsyncBaseTransport | None = None
                   ) -> dict[str, Any]:
    """Kick off (or resume) a download in the background. Returns its state."""
    if get_spec(model_id) is None:
        raise KeyError(model_id)
    state = download_state(model_id)
    if state and state["status"] == "downloading":
        return state
    if resolve_local(model_id) is not None:
        return _set_state(model_id, status="ready", percent=100.0,
                          downloaded=resolve_local(model_id).stat().st_size,
                          total=resolve_local(model_id).stat().st_size)
    task = asyncio.create_task(_download(model_id, transport))
    _tasks[model_id] = task
    return _set_state(model_id, status="downloading", downloaded=0,
                      total=get_spec(model_id).size_bytes, percent=0.0,
                      error=None)


async def wait_download(model_id: str, timeout: float | None = None) -> dict[str, Any]:
    """Await completion of a download (used by run.py / tests)."""
    task = _tasks.get(model_id)
    if task is not None:
        await asyncio.wait_for(asyncio.shield(task), timeout)
    return download_state(model_id) or {}


def delete_model(model_id: str) -> bool:
    path = resolve_local(model_id)
    if path is None:
        return False
    task = _tasks.get(model_id)
    if task is not None and not task.done():
        task.cancel()
    path.unlink(missing_ok=True)
    for p in (models_dir() / Path(model_id).with_suffix(".gguf.part"),):
        p.unlink(missing_ok=True)
    _downloads.pop(model_id, None)
    return True


def use_model(model_id: str, thinking: bool | None = None) -> dict[str, Any]:
    """Point the app at a downloaded GGUF (and switch the provider to it)."""
    from .config import update_settings

    path = resolve_local(model_id)
    if path is None:
        raise FileNotFoundError(f"model belum diunduh: {model_id}")
    spec = get_spec(model_id)
    patch: dict[str, Any] = {
        "provider": "huggingface",
        "hf_model": path.name,
    }
    if thinking is not None:
        patch["thinking"] = bool(thinking)
    elif spec is not None and not spec.thinking:
        patch["thinking"] = False  # template without an enable_thinking switch
    result = update_settings(**patch)
    result["local_model_path"] = str(path)
    return result


@dataclass
class CatalogSummary:
    """Small helper so docs/tests can assert the 8 GB story stays true."""
    entries: list[ModelSpec] = field(default_factory=lambda: list(CATALOG))

    def fits_8gb(self) -> list[ModelSpec]:
        return [m for m in self.entries if m.size_bytes <= 3 * 1024**3]
