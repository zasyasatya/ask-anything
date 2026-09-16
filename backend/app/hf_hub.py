"""HuggingFace Hub: model search + multi-model downloader into `models/`.

This module replaces the old curated GGUF catalog. The offline flow is now:

    search a repo by name ("deepseek-ai/DeepSeek-V4.1-Flash", "qwen3", …)
        → POST /api/hf/models/download
        → every needed file streams into `<models>/<org>/<name>/`
        → the folder is loaded straight into the process by
          `app/local_inference.py` (transformers) — no llama.cpp involved.

Downloads stream with `httpx` (no `huggingface_hub` dependency), resume per
file via HTTP `Range`, keep several models in flight at once, and publish
progress through a module-level registry that the UI polls
(`GET /api/hf/downloads`).

Only the files a causal LM actually needs are fetched: config, tokenizer and
`*.safetensors` weights. READMEs, images, ONNX/GGUF variants and the
`original/` folders some repos ship are skipped, which for most repos cuts the
download by hundreds of megabytes.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .config import settings

CHUNK = 1024 * 1024
SEARCH_LIMIT = 20
API_TIMEOUT = 20.0

#: Folders that never contain anything we need.
_SKIP_DIRS = ("original", "onnx", "openvino", "tensorrt", "gguf", "figures",
              ".cache", "assets", "images", "docs")

#: Extensions that are never needed for local inference.
_SKIP_EXT = (".md", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf",
             ".lock", ".gguf", ".ot", ".onnx", ".tflite", ".h5", ".msgpack",
             ".pt", ".pth", ".ipynb", ".arrow", ".npy", ".zip", ".tar", ".gz")

#: Config/tokenizer files, matched by exact name or by these suffixes.
_TEXT_FILES = ("config.json", "generation_config.json", "tokenizer_config.json",
               "tokenizer.json", "special_tokens_map.json", "added_tokens.json",
               "vocab.json", "vocab.txt", "merges.txt", "chat_template.jinja",
               "chat_template.json", "preprocessor_config.json",
               "processor_config.json", "sentencepiece.bpe.model", "spiece.model",
               "tokenizer.model")

MANIFEST_NAME = ".ask-anything.json"


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
def models_dir() -> Path:
    """Project folder that stores every downloaded model."""
    return settings.resolved_models_dir()


def _safe_segment(segment: str) -> str:
    """Filesystem-safe version of a repo id segment (never escape models/)."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", segment.strip())
    return cleaned or "_"


def repo_dir(repo_id: str) -> Path:
    """`models/<org>/<name>` — mirrors the Hub layout, keeps the UI obvious."""
    parts = [_safe_segment(p) for p in repo_id.strip("/").split("/") if p]
    return models_dir().joinpath(*parts) if parts else models_dir()


def manifest_path(repo_id: str) -> Path:
    return repo_dir(repo_id) / MANIFEST_NAME


# ---------------------------------------------------------------------------
# which files of a repo do we need?
# ---------------------------------------------------------------------------
def needed_files(siblings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick the files required to run a causal LM from a repo file list.

    `siblings` is the Hub's `[{"rfilename": ..., "size": ...}, …]` (sizes are
    present when the repo is fetched with `?blobs=true`).
    """
    files: list[dict[str, Any]] = []
    has_safetensors = False
    has_bin = False

    for item in siblings or []:
        name = (item.get("rfilename") or item.get("path") or "").strip()
        if not name:
            continue
        lowered = name.lower()
        if any(lowered.startswith(f"{d}/") for d in _SKIP_DIRS):
            continue
        if lowered.endswith(_SKIP_EXT) and not lowered.endswith("tokenizer.model"):
            continue
        keep = False
        if lowered.endswith(".safetensors"):
            keep, has_safetensors = True, True
        elif lowered.endswith(".bin") and "pytorch_model" in lowered:
            keep, has_bin = True, True
        elif lowered.endswith(".index.json"):
            keep = True
        elif lowered in _TEXT_FILES or Path(lowered).name in _TEXT_FILES:
            keep = True
        elif lowered.startswith(("configuration_", "modeling_", "tokenization_")) \
                and lowered.endswith(".py"):
            keep = True  # trust_remote_code repos
        if keep:
            files.append({"path": name, "size": int(item.get("size") or 0)})

    # Prefer safetensors; only fall back to the pickle weights when the repo
    # does not ship safetensors at all.
    if has_safetensors:
        files = [f for f in files
                 if not (f["path"].lower().endswith(".bin"))]
    elif not has_bin:
        files = [f for f in files if not f["path"].lower().endswith((".bin",))]
    return files


def weights_total(files: list[dict[str, Any]]) -> int:
    return sum(int(f.get("size") or 0) for f in files)


# ---------------------------------------------------------------------------
# Hub API (search / repo info) — never raises, the UI shows the error
# ---------------------------------------------------------------------------
def _endpoint() -> str:
    return (settings.hf_endpoint or "https://huggingface.co").rstrip("/")


def _hub_headers() -> dict[str, str]:
    headers = {"User-Agent": settings.user_agent}
    if settings.hf_token:
        headers["Authorization"] = f"Bearer {settings.hf_token}"
    return headers


async def _get_json(client: httpx.AsyncClient, url: str,
                    params: dict[str, Any] | None = None) -> Any:
    resp = await client.get(url, params=params, headers=_hub_headers())
    if resp.status_code in (401, 403):
        raise RuntimeError(
            f"HTTP {resp.status_code} dari {url} — repo privat/gated. "
            "Isi `ASK_HF_TOKEN` (token huggingface.co/settings/tokens) di "
            "Settings → Model offline.")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} dari {url}: "
                           f"{resp.text[:200]}")
    return resp.json()


def _repo_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise one search hit into what the dropdown/row needs."""
    repo_id = item.get("id") or item.get("modelId") or ""
    safetensors = item.get("safetensors") or {}
    params = safetensors.get("total") or item.get("params") or 0
    size = 0
    if params:
        # rough fp16 estimate; the real number comes from the file list
        size = int(params) * 2
    return {
        "repo_id": repo_id,
        "label": repo_id,
        "params": int(params or 0),
        "size_bytes": size,
        "downloads": int(item.get("downloads") or 0),
        "likes": int(item.get("likes") or 0),
        "pipeline_tag": item.get("pipeline_tag") or "",
        "tags": [t for t in (item.get("tags") or []) if not t.startswith("region:")][:6],
        "local": local_info(repo_id),
    }


async def search_models(query: str, limit: int = SEARCH_LIMIT,
                        transport: httpx.AsyncBaseTransport | None = None,
                        timeout: float = API_TIMEOUT) -> dict[str, Any]:
    """Search the Hub. `org/name` queries resolve to that repo first.

    Returns `{"ok": bool, "models": [...], "error": str|None}`; never raises.
    """
    query = (query or "").strip()
    if not query:
        return {"ok": True, "query": "", "models": [], "error": None}

    base = _endpoint()
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport,
                                     follow_redirects=True) as client:
            hits: list[dict[str, Any]] = []
            exact = ""
            if re.fullmatch(r"[^/\s]+/[^/\s]+", query):
                # A repo id was typed/pasted — resolve it directly so an exact
                # match always shows even when Hub search ranks it lower.
                try:
                    info = await _get_json(client, f"{base}/api/models/{query}")
                    hits.append(info)
                    exact = info.get("id") or query
                except RuntimeError:
                    exact = ""  # not a repo id after all → plain search

            params = {"search": query, "limit": limit, "sort": "downloads",
                      "direction": "-1", "full": "false"}
            for hit in await _get_json(client, f"{base}/api/models", params):
                if (hit.get("id") or "") != exact:
                    hits.append(hit)

            models = [_repo_summary(h) for h in hits]
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return {"ok": False, "query": query, "models": [],
                "error": f"tidak bisa mencari di {base}: {exc}"}

    # Local models first, then by popularity.
    models.sort(key=lambda m: (not m["local"]["exists"], -m["downloads"]))
    return {"ok": True, "query": query, "models": models[:limit + 1],
            "error": None}


async def repo_info(repo_id: str,
                    transport: httpx.AsyncBaseTransport | None = None,
                    timeout: float = API_TIMEOUT) -> dict[str, Any]:
    """Repo metadata incl. the file list with sizes (`?blobs=true`)."""
    base = _endpoint()
    url = f"{base}/api/models/{repo_id.strip('/')}"
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport,
                                     follow_redirects=True) as client:
            info = await _get_json(client, url, {"blobs": "true"})
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        return {"ok": False, "repo_id": repo_id, "error": str(exc), "files": [],
                "size_bytes": 0}

    files = needed_files(info.get("siblings") or [])
    summary = _repo_summary(info)
    summary["files"] = files
    summary["size_bytes"] = weights_total(files)
    summary["revision"] = info.get("sha") or "main"
    summary["error"] = None
    summary["ok"] = True
    return summary


# ---------------------------------------------------------------------------
# local state of downloaded models
# ---------------------------------------------------------------------------
def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def local_info(repo_id: str) -> dict[str, Any]:
    """What we already have on disk for a repo id."""
    path = repo_dir(repo_id)
    manifest = _read_manifest(manifest_path(repo_id))
    ready = (path / "config.json").is_file() and bool(manifest.get("complete"))
    if not path.is_dir():
        return {"exists": False, "ready": False, "path": str(path),
                "size_bytes": 0, "downloaded_at": None, "files": 0,
                "partial": False}
    size = _dir_size(path)
    return {
        "exists": True,
        "ready": ready,
        "path": str(path),
        "size_bytes": size,
        "downloaded_at": manifest.get("downloaded_at"),
        "files": int(manifest.get("file_count") or 0),
        "partial": not ready,
    }


def list_local() -> list[dict[str, Any]]:
    """Every model folder under `models/` (org/name or a bare name)."""
    root = models_dir()
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out

    def entry(path: Path, repo_id: str) -> None:
        manifest = _read_manifest(path / MANIFEST_NAME)
        info = local_info(repo_id)
        out.append({
            "repo_id": repo_id,
            "label": repo_id,
            "params": int(manifest.get("params") or 0),
            "size_bytes": info["size_bytes"],
            "files": info["files"],
            "downloaded_at": info["downloaded_at"],
            "path": info["path"],
            "ready": info["ready"],
            "partial": info["partial"],
            "manifest": manifest.get("params") and {
                "params": manifest.get("params"),
                "tags": manifest.get("tags") or [],
            } or None,
            "download": download_state(repo_id),
        })

    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if (child / "config.json").is_file() or (child / MANIFEST_NAME).is_file():
            entry(child, child.name)
            continue
        for sub in sorted(p for p in child.iterdir() if p.is_dir()):
            if (sub / "config.json").is_file() or (sub / MANIFEST_NAME).is_file():
                entry(sub, f"{child.name}/{sub.name}")
    return out


def resolve_local(repo_id: str) -> Path | None:
    """Directory of a fully downloaded model, or None."""
    path = repo_dir(repo_id)
    return path if (path / "config.json").is_file() else None


# ---------------------------------------------------------------------------
# download registry (polled by the UI) + worker
# ---------------------------------------------------------------------------
@dataclass
class _Job:
    repo_id: str
    state: dict[str, Any] = field(default_factory=dict)
    task: asyncio.Task | None = None


_jobs: dict[str, _Job] = {}


def download_state(repo_id: str) -> dict[str, Any] | None:
    job = _jobs.get(repo_id)
    return dict(job.state) if job else None


def all_downloads() -> list[dict[str, Any]]:
    return [dict(j.state) for j in _jobs.values()]


def _state_ref(repo_id: str) -> dict[str, Any]:
    """The *live* state dict of a job.

    The downloader mutates this object while it streams, and `GET
    /api/hf/downloads` reads it — mutating a copy would freeze the progress bar
    at 0 % forever, so every writer has to go through here.
    """
    job = _jobs.setdefault(repo_id, _Job(repo_id=repo_id))
    if not job.state:
        job.state = {
            "repo_id": repo_id, "status": "idle", "stage": "",
            "downloaded": 0, "total": 0, "percent": 0.0, "speed_bps": 0.0,
            "file": "", "file_index": 0, "file_count": 0,
            "error": None, "started_at": None, "finished_at": None,
        }
    return job.state


def _set_state(repo_id: str, **kw: Any) -> dict[str, Any]:
    """Update the live state and return a snapshot (for HTTP responses)."""
    state = _state_ref(repo_id)
    state.update(kw)
    if state["total"]:
        state["percent"] = round(
            100.0 * state["downloaded"] / state["total"], 1)
    return dict(state)


def resolve_file_url(repo_id: str, filename: str, revision: str = "main") -> str:
    return (f"{_endpoint()}/{repo_id.strip('/')}/resolve/{revision}/"
            f"{filename}?download=true")


async def _fetch_file(client: httpx.AsyncClient, repo_id: str,
                      filename: str, dest: Path, state: dict[str, Any],
                      revision: str, started: float, resume_base: int) -> None:
    """Stream one file into `dest`, updating the shared progress state."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.is_file() else 0
    headers = dict(_hub_headers())
    if have:
        headers["Range"] = f"bytes={have}-"

    async with client.stream("GET", resolve_file_url(repo_id, filename, revision),
                             headers=headers) as resp:
        if resp.status_code not in (200, 206):
            body = (await resp.aread()).decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {resp.status_code} untuk {filename}: "
                               f"{body[:200]}")
        if resp.status_code != 206 and have:
            part.unlink(missing_ok=True)  # server ignored Range
            have = 0
        state["file"] = filename
        mode = "ab" if have else "wb"
        with part.open(mode) as fh:
            async for chunk in resp.aiter_bytes(CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                state["downloaded"] += len(chunk)
                if state["total"]:
                    state["percent"] = round(
                        100.0 * state["downloaded"] / state["total"], 1)
                elapsed = max(time.time() - started, 0.001)
                state["speed_bps"] = round(
                    (state["downloaded"] - resume_base) / elapsed, 1)
    if dest.exists():
        dest.unlink()
    part.replace(dest)


async def _download(repo_id: str,
                    transport: httpx.AsyncBaseTransport | None = None) -> None:
    _set_state(repo_id, status="downloading", stage="memeriksa repo",
               error=None, started_at=time.time(), finished_at=None)
    state = _state_ref(repo_id)
    try:
        info = await repo_info(repo_id, transport=transport)
        if not info.get("ok"):
            raise RuntimeError(info.get("error") or "repo tidak ditemukan")
        files = info.get("files") or []
        if not files:
            raise RuntimeError(
                "repo ini tidak punya file yang bisa dipakai untuk inference "
                "lokal (config.json / *.safetensors tidak ditemukan)")

        total = weights_total(files) or 1
        dest_root = repo_dir(repo_id)
        dest_root.mkdir(parents=True, exist_ok=True)
        state.update(status="downloading", stage="mengunduh", total=total,
                     file_count=len(files))

        # Resume: whatever is already complete on disk counts as downloaded.
        done_bytes = 0
        for f in files:
            target = dest_root / f["path"]
            if target.is_file():
                done_bytes += target.stat().st_size
        state["downloaded"] = done_bytes
        if state["total"]:
            state["percent"] = round(100.0 * done_bytes / state["total"], 1)

        timeout = httpx.Timeout(connect=20.0, read=600.0, write=60.0, pool=30.0)
        started = time.time()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                     transport=transport) as client:
            for index, f in enumerate(files, start=1):
                target = dest_root / f["path"]
                if target.is_file():
                    state["file_index"] = index
                    continue
                state["file_index"] = index
                await _fetch_file(client, repo_id, f["path"], target, state,
                                  info.get("revision") or "main", started,
                                  done_bytes)

        manifest = {
            "repo_id": repo_id,
            "revision": info.get("revision") or "main",
            "downloaded_at": int(time.time()),
            "file_count": len(files),
            "size_bytes": total,
            "params": int(info.get("params") or 0),
            "tags": info.get("tags") or [],
            "complete": True,
        }
        (dest_root / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _set_state(repo_id, status="ready", stage="selesai", percent=100.0,
                   downloaded=total, total=total, file="",
                   finished_at=time.time())
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        _set_state(repo_id, status="error", stage="gagal", error=str(exc),
                   finished_at=time.time())
    finally:
        job = _jobs.get(repo_id)
        if job is not None:
            job.task = None


def start_download(repo_id: str,
                   transport: httpx.AsyncBaseTransport | None = None
                   ) -> dict[str, Any]:
    """Start (or resume) a download in the background; returns its state.

    Several models can download at the same time — each repo has its own task
    and its own progress entry.
    """
    repo_id = (repo_id or "").strip().strip("/")
    if not repo_id or "/" not in repo_id:
        raise ValueError("repo_id harus berbentuk `organisasi/nama-model`")
    job = _jobs.get(repo_id)
    if job and job.task is not None and not job.task.done():
        return dict(job.state)
    existing = resolve_local(repo_id)
    if existing is not None and _read_manifest(manifest_path(repo_id)).get("complete"):
        return _set_state(repo_id, status="ready", stage="sudah terunduh",
                          percent=100.0, error=None)
    job = _jobs.setdefault(repo_id, _Job(repo_id=repo_id))
    _set_state(repo_id, status="downloading", stage="memulai", downloaded=0,
               percent=0.0, error=None)
    job.task = asyncio.create_task(_download(repo_id, transport))
    return dict(job.state)


async def wait_download(repo_id: str, timeout: float | None = None
                        ) -> dict[str, Any]:
    """Await a download (used by run.py / tests)."""
    job = _jobs.get(repo_id)
    if job is not None and job.task is not None:
        await asyncio.wait_for(asyncio.shield(job.task), timeout)
    return download_state(repo_id) or {}


def cancel_download(repo_id: str) -> bool:
    job = _jobs.get(repo_id)
    if job is None or job.task is None or job.task.done():
        return False
    job.task.cancel()
    _set_state(repo_id, status="idle", stage="dibatalkan")
    return True


def delete_model(repo_id: str) -> bool:
    """Remove a downloaded model folder (and cancel a running download)."""
    path = repo_dir(repo_id)
    if not path.is_dir():
        return False
    cancel_download(repo_id)
    for p in sorted(path.rglob("*.part"), reverse=True):
        p.unlink(missing_ok=True)
    for p in sorted((f for f in path.rglob("*") if f.is_file()), reverse=True):
        p.unlink(missing_ok=True)
    for d in sorted((d for d in path.rglob("*") if d.is_dir()), reverse=True):
        d.rmdir()
    try:
        path.rmdir()
    except OSError:
        pass
    _jobs.pop(repo_id, None)
    return True


def use_model(repo_id: str, thinking: bool | None = None) -> dict[str, Any]:
    """Point the app at a downloaded model (provider → huggingface/local)."""
    from .config import update_settings

    path = resolve_local(repo_id)
    if path is None:
        raise FileNotFoundError(
            f"model belum terunduh lengkap: {repo_id} "
            f"(config.json tidak ada di {repo_dir(repo_id)})")
    patch: dict[str, Any] = {"provider": "huggingface", "hf_mode": "local",
                             "hf_model": repo_id.strip("/")}
    if thinking is not None:
        patch["thinking"] = bool(thinking)
    result = update_settings(**patch)
    set_active(repo_id.strip("/"), str(path))
    result["local_model_path"] = str(path)
    return result


# ---------------------------------------------------------------------------
# model aktif: siapa yang harus di-load otomatis saat backend (re)start
# ---------------------------------------------------------------------------
ACTIVE_FILE = ".active.json"


def active_file() -> Path:
    return models_dir() / ACTIVE_FILE


def set_active(repo_id: str, path: str | Path) -> None:
    """Ingat model terakhir yang dipakai + lokasi foldernya.

    Path disimpan (bukan hanya repo id) agar model yang di-load dari folder
    di luar `models/` pun tetap bisa di-muat-ulang otomatis saat restart.
    """
    try:
        d = models_dir()
        d.mkdir(parents=True, exist_ok=True)
        active_file().write_text(
            json.dumps({"repo_id": repo_id, "path": str(path)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    except OSError:
        pass  # memuat ulang model tetap mungkin lewat repo id / auto-pick


def active_model() -> tuple[str, Path] | None:
    """Model terakhir yang dipakai bila foldernya masih ada di disk."""
    try:
        data = json.loads(active_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    repo_id = str(data.get("repo_id") or "").strip("/")
    path = Path(str(data.get("path") or "")).expanduser()
    if repo_id and (path / "config.json").is_file():
        return repo_id, path
    return None


def auto_pick_model() -> tuple[str, Path] | None:
    """Model terunduh paling baru yang lengkap — fallback saat startup.

    Ini yang membuat "apapun modelnya yang di-download, langsung jalan":
    backend memilihkan sendiri model di `models/` bila user belum memilih.
    """
    candidates = [m for m in list_local() if m.get("ready")]
    if not candidates:
        return None
    newest = max(
        candidates,
        key=lambda m: (int(m.get("downloaded_at") or 0), m["repo_id"]))
    return newest["repo_id"], Path(newest["path"])


def register_model_folder(path: Path,
                          repo_id: str = "") -> tuple[str, dict[str, Any]]:
    """Daftarkan folder model apa pun (di dalam/luar `models/`) ke app.

    Menulis manifest bila belum ada (agar `list_local()`/`local_info()`
    menganggapnya model lengkap) dan mengembalikan repo id-nya.
    """
    path = Path(path).expanduser()
    if not (path / "config.json").is_file():
        raise FileNotFoundError(
            f"bukan folder model HuggingFace (config.json tidak ada): {path}")
    path = path.resolve()

    repo_id = (repo_id or "").strip().strip("/")
    if not repo_id:
        manifest = _read_manifest(path / MANIFEST_NAME)
        repo_id = str(manifest.get("repo_id") or "").strip("/")
    if not repo_id:
        try:
            rel = path.relative_to(models_dir())
            repo_id = rel.as_posix()
        except ValueError:
            repo_id = path.name
    if not repo_id:
        repo_id = "model-lokal"

    if not (path / MANIFEST_NAME).is_file():
        try:
            (path / MANIFEST_NAME).write_text(
                json.dumps({
                    "repo_id": repo_id,
                    "revision": "local",
                    "downloaded_at": int(time.time()),
                    "file_count": sum(1 for p in path.rglob("*") if p.is_file()),
                    "size_bytes": _dir_size(path),
                    "complete": True,
                    "source": "folder-lokal",
                }, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except OSError:
            pass
    return repo_id, _read_manifest(path / MANIFEST_NAME)
