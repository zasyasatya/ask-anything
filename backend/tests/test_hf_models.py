"""HuggingFace Hub client: file selection, search, and the downloader.

The Hub itself is replaced by an `httpx.MockTransport` that mimics the three
endpoints we use (`/api/models`, `/api/models/{repo}?blobs=true` and
`/{repo}/resolve/main/{file}`), including `Range` requests, so resume,
multi-file progress and multi-model downloads are all exercised for real.
"""
import asyncio
import json

import httpx
import pytest

from app import hf_hub
from app.config import settings

REPO = "deepseek-ai/DeepSeek-V4.1-Flash"
OTHER = "Qwen/Qwen3-1.7B"

#: what a repo on the Hub contains, with the junk we must NOT download
SIBLINGS = {
    REPO: [
        {"rfilename": "config.json", "size": 700},
        {"rfilename": "generation_config.json", "size": 120},
        {"rfilename": "tokenizer_config.json", "size": 3_000},
        {"rfilename": "tokenizer.json", "size": 7_000_000},
        {"rfilename": "model.safetensors.index.json", "size": 30_000},
        {"rfilename": "model-00001-of-00002.safetensors", "size": 40_000},
        {"rfilename": "model-00002-of-00002.safetensors", "size": 40_000},
        {"rfilename": "pytorch_model-00001-of-00002.bin", "size": 99_000},
        {"rfilename": "README.md", "size": 12_000},
        {"rfilename": "original/consolidated.00.pth", "size": 500_000},
        {"rfilename": "onnx/model.onnx", "size": 500_000},
        {"rfilename": "model-q4.gguf", "size": 500_000},
        {"rfilename": "figures/arch.png", "size": 90_000},
    ],
    OTHER: [
        {"rfilename": "config.json", "size": 600},
        {"rfilename": "tokenizer_config.json", "size": 2_000},
        {"rfilename": "tokenizer.model", "size": 1_000},
        {"rfilename": "model.safetensors", "size": 20_000},
    ],
}


def _hub_transport(chunks: int = 4) -> httpx.MockTransport:
    """A fake Hub. `chunks` controls how many pieces a file arrives in."""
    seen: dict[str, list[str]] = {"ranges": []}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/models":
            q = request.url.params.get("search", "")
            hits = [{"id": repo, "downloads": 1000, "likes": 10,
                     "pipeline_tag": "text-generation",
                     "safetensors": {"total": 1_700_000_000},
                     "tags": ["transformers", "region:us"]}
                    for repo in SIBLINGS if q.lower() in repo.lower()]
            return httpx.Response(200, json=hits)
        if path.startswith("/api/models/"):
            repo = path[len("/api/models/"):]
            if repo not in SIBLINGS:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(200, json={
                "id": repo, "sha": "deadbeef", "downloads": 1000,
                "safetensors": {"total": 1_700_000_000},
                "siblings": SIBLINGS[repo],
            })
        if "/resolve/" in path:
            # revision boleh "main" atau sha commit (yang dipakai downloader)
            repo, _, rest = path.partition("/resolve/")
            name = rest.split("/", 1)[1]
            payload = (f"{name}\n".encode() * 512)[:8_000]
            rng = request.headers.get("range")
            if rng:
                seen["ranges"].append(rng)
                start = int(rng.split("=")[1].rstrip("-"))
                return httpx.Response(206, content=payload[start:],
                                      headers={"content-length":
                                               str(len(payload) - start)})
            return httpx.Response(200, content=payload,
                                  headers={"content-length": str(len(payload))})
        return httpx.Response(404, text="nope")

    transport = httpx.MockTransport(handler)
    transport.seen = seen  # type: ignore[attr-defined]
    return transport


@pytest.fixture()
def tmp_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", str(tmp_path))
    hf_hub._jobs.clear()
    yield tmp_path
    hf_hub._jobs.clear()


# ---------------------------------------------------------------------------
# which files does a repo need?
# ---------------------------------------------------------------------------
def test_needed_files_keeps_weights_tokenizer_and_skips_junk():
    files = [f["path"] for f in hf_hub.needed_files(SIBLINGS[REPO])]
    assert "config.json" in files and "tokenizer.json" in files
    assert "model-00001-of-00002.safetensors" in files
    assert "model.safetensors.index.json" in files
    # safetensors wins: the pickle weights must not be downloaded as well
    assert not any(f.endswith(".bin") for f in files)
    assert not any(f.endswith((".md", ".pth", ".onnx", ".gguf", ".png"))
                   for f in files)
    assert not any(f.startswith(("original/", "onnx/", "figures/")) for f in files)


def test_needed_files_falls_back_to_bin_without_safetensors():
    files = hf_hub.needed_files([
        {"rfilename": "config.json", "size": 10},
        {"rfilename": "pytorch_model.bin", "size": 100},
    ])
    assert [f["path"] for f in files] == ["config.json", "pytorch_model.bin"]


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
async def test_search_by_name(tmp_models):
    transport = _hub_transport()
    out = await hf_hub.search_models("qwen3", transport=transport)
    assert out["ok"] is True
    assert [m["repo_id"] for m in out["models"]] == [OTHER]
    assert out["models"][0]["params"] == 1_700_000_000


async def test_search_resolves_exact_repo_id_first(tmp_models):
    """`deepseek-ai/DeepSeek-V4.1-Flash` harus muncul walau search biasa meleset."""
    out = await hf_hub.search_models(REPO, transport=_hub_transport())
    assert out["ok"] is True
    assert out["models"][0]["repo_id"] == REPO


async def test_search_failure_is_data_not_exception(tmp_models, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("no route to host")

    out = await hf_hub.search_models("qwen",
                                     transport=httpx.MockTransport(handler))
    assert out["ok"] is False and "no route to host" in out["error"]


async def test_repo_info_reports_real_download_size(tmp_models):
    info = await hf_hub.repo_info(REPO, transport=_hub_transport())
    assert info["ok"] is True
    assert info["size_bytes"] == sum(f["size"] for f in info["files"])
    assert info["revision"] == "deadbeef"


# ---------------------------------------------------------------------------
# download: progress, resume, several models at once, delete
# ---------------------------------------------------------------------------
async def test_download_writes_files_manifest_and_state(tmp_models):
    transport = _hub_transport()
    state = hf_hub.start_download(REPO, transport=transport)
    assert state["status"] == "downloading"

    final = await hf_hub.wait_download(REPO, timeout=30)
    assert final["status"] == "ready", final
    assert final["percent"] == 100.0
    assert final["file_count"] == len(hf_hub.needed_files(SIBLINGS[REPO]))

    folder = tmp_models / "deepseek-ai" / "DeepSeek-V4.1-Flash"
    assert (folder / "config.json").is_file()
    assert (folder / "model-00002-of-00002.safetensors").is_file()
    assert not list(folder.rglob("*.part")), "file .part harus sudah di-rename"
    manifest = json.loads((folder / hf_hub.MANIFEST_NAME).read_text())
    assert manifest["complete"] is True and manifest["repo_id"] == REPO

    info = hf_hub.local_info(REPO)
    assert info["ready"] is True and info["size_bytes"] > 0


class _SlowStream(httpx.AsyncByteStream):
    """Body yang benar-benar datang sedikit demi sedikit (bukan buffer jadi)."""

    def __init__(self, data: bytes, chunk: int, delay: float) -> None:
        self.data, self.chunk, self.delay = data, chunk, delay

    async def __aiter__(self):
        for i in range(0, len(self.data), self.chunk):
            yield self.data[i:i + self.chunk]
            await asyncio.sleep(self.delay)


async def test_download_progress_is_observable(tmp_models):
    """UI mem-poll state: percent harus benar-benar naik, bukan 0 → 100."""
    async def handler(request: httpx.Request) -> httpx.Response:
        if "/resolve/" in request.url.path:
            body = b"y" * 4_000
            return httpx.Response(200, stream=_SlowStream(body, 200, 0.004),
                                  headers={"content-length": str(len(body))})
        return httpx.Response(200, json={"id": OTHER, "sha": "x",
                                         "siblings": SIBLINGS[OTHER]})

    hf_hub.start_download(OTHER, transport=httpx.MockTransport(handler))
    percents = []
    for _ in range(400):
        state = hf_hub.download_state(OTHER) or {}
        percents.append(state.get("percent", 0.0))
        if state.get("status") == "ready":
            break
        await asyncio.sleep(0.004)

    assert percents[-1] == 100.0
    assert len({p for p in percents}) > 3, percents
    assert percents == sorted(percents), "progres tidak boleh turun"
    assert any(0 < p < 100 for p in percents), percents


async def test_download_resumes_with_range_header(tmp_models):
    folder = tmp_models / "Qwen" / "Qwen3-1.7B"
    folder.mkdir(parents=True)
    (folder / "model.safetensors.part").write_bytes(b"x" * 1_000)

    transport = _hub_transport()
    hf_hub.start_download(OTHER, transport=transport)
    final = await hf_hub.wait_download(OTHER, timeout=30)
    assert final["status"] == "ready", final
    assert transport.seen["ranges"], "resume harus memakai header Range"


async def test_two_models_download_in_parallel(tmp_models):
    transport = _hub_transport()
    hf_hub.start_download(REPO, transport=transport)
    hf_hub.start_download(OTHER, transport=transport)
    a = await hf_hub.wait_download(REPO, timeout=30)
    b = await hf_hub.wait_download(OTHER, timeout=30)
    assert a["status"] == "ready" and b["status"] == "ready"
    assert len(hf_hub.all_downloads()) == 2
    assert len(hf_hub.list_local()) == 2


async def test_download_error_is_reported(tmp_models):
    def handler(request):
        if "/resolve/" in request.url.path:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"id": REPO, "sha": "x",
                                         "siblings": SIBLINGS[REPO]})

    hf_hub.start_download(REPO, transport=httpx.MockTransport(handler))
    final = await hf_hub.wait_download(REPO, timeout=30)
    assert final["status"] == "error" and "boom" in final["error"]


async def test_download_rejects_non_repo_id(tmp_models):
    with pytest.raises(ValueError):
        hf_hub.start_download("bukan-repo-id")


async def test_delete_removes_folder(tmp_models):
    transport = _hub_transport()
    hf_hub.start_download(OTHER, transport=transport)
    await hf_hub.wait_download(OTHER, timeout=30)
    assert (tmp_models / "Qwen" / "Qwen3-1.7B").is_dir()
    assert hf_hub.delete_model(OTHER) is True
    assert not (tmp_models / "Qwen" / "Qwen3-1.7B").exists()
    assert hf_hub.delete_model(OTHER) is False


# ---------------------------------------------------------------------------
# use_model: provider → huggingface lokal
# ---------------------------------------------------------------------------
async def test_use_model_points_app_at_local_model(tmp_models, monkeypatch):
    monkeypatch.setattr(settings, "provider", "mock")
    transport = _hub_transport()
    hf_hub.start_download(OTHER, transport=transport)
    await hf_hub.wait_download(OTHER, timeout=30)

    out = hf_hub.use_model(OTHER, thinking=False)
    assert out["provider"] == "huggingface"
    assert out["hf_mode"] == "local"
    assert out["hf_model"] == OTHER
    assert out["thinking"] is False
    assert out["local_model_path"].endswith("Qwen3-1.7B")

    with pytest.raises(FileNotFoundError):
        hf_hub.use_model("Qwen/Qwen3-99B")


async def test_list_local_finds_org_and_bare_folders(tmp_models):
    (tmp_models / "org" / "name").mkdir(parents=True)
    (tmp_models / "org" / "name" / "config.json").write_text("{}")
    (tmp_models / "solo").mkdir()
    (tmp_models / "solo" / "config.json").write_text("{}")
    ids = sorted(m["repo_id"] for m in hf_hub.list_local())
    assert ids == ["org/name", "solo"]
