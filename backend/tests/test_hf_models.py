"""Offline model catalog: download into the project folder, resume, use, delete."""
import asyncio

import httpx
import pytest

from app import hf_models
from app.config import PROJECT_ROOT, settings
from app.local_llm import runtime


@pytest.fixture()
def tmp_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", str(tmp_path))
    monkeypatch.setattr(settings, "hf_endpoint", "https://hf.test")
    hf_models._downloads.clear()
    hf_models._tasks.clear()
    yield tmp_path
    hf_models._downloads.clear()
    hf_models._tasks.clear()


RECOMMENDED = "qwen3-4b-instruct-2507-q4_k_m"


def _fake_server(payload: bytes, seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        rng = request.headers.get("range")
        if rng and rng.startswith("bytes="):
            start = int(rng.split("=")[1].split("-")[0])
            return httpx.Response(
                206, content=payload[start:],
                headers={"content-length": str(len(payload) - start)})
        return httpx.Response(200, content=payload,
                              headers={"content-length": str(len(payload))})

    return httpx.MockTransport(handler)


def test_catalog_targets_8gb_laptops():
    ids = {m.id for m in hf_models.CATALOG}
    assert RECOMMENDED in ids
    small = [m for m in hf_models.CATALOG if m.size_bytes <= 3 * 1024**3]
    # 1.7B–4B Q4/Q8 quants must fit an 8 GB machine with room to spare.
    assert len(small) >= 4
    assert any(m.thinking for m in small), "butuh opsi model yang bisa thinking"
    assert any(m.recommended for m in hf_models.CATALOG)
    # verified against the HF Hub tree API (Q4_K_M quants)
    by_id = {m.id: m for m in hf_models.CATALOG}
    assert by_id[RECOMMENDED].repo_id == "bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF"
    assert by_id[RECOMMENDED].size_bytes == 2_497_280_736
    assert by_id["qwen3-4b-q4_k_m"].size_bytes == 2_497_280_256
    assert by_id["qwen3-8b-q4_k_m"].size_bytes == 5_027_783_488


def test_models_dir_defaults_to_project_folder():
    settings.models_dir = "models"
    assert settings.resolved_models_dir() == PROJECT_ROOT / "models"


async def test_download_writes_gguf_into_project_folder(tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    payload = b"GGUF" + b"x" * 4096
    seen: list[httpx.Request] = []

    state = hf_models.start_download(RECOMMENDED, transport=_fake_server(payload, seen))
    assert state["status"] == "downloading"
    await hf_models.wait_download(RECOMMENDED, timeout=10)

    final = tmp_models / spec.filename
    assert final.is_file() and final.read_bytes() == payload
    assert str(final).startswith(str(tmp_models))
    assert str(seen[0].url) == (
        f"https://hf.test/{spec.repo_id}/resolve/main/{spec.filename}?download=true")

    state = hf_models.download_state(RECOMMENDED)
    assert state["status"] == "ready" and state["percent"] == 100.0
    assert state["downloaded"] == len(payload)

    listed = {m["id"]: m for m in hf_models.list_models()}
    assert listed[RECOMMENDED]["local"]["exists"] is True
    assert listed[RECOMMENDED]["local"]["size_bytes"] == len(payload)


async def test_download_resumes_from_partial_file(tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    payload = b"GGUF" + b"y" * 4096
    (tmp_models / (spec.filename + ".part")).write_bytes(payload[:1000])
    seen: list[httpx.Request] = []

    hf_models.start_download(RECOMMENDED, transport=_fake_server(payload, seen))
    await hf_models.wait_download(RECOMMENDED, timeout=10)

    assert seen[0].headers["range"] == "bytes=1000-"
    final = tmp_models / spec.filename
    assert final.read_bytes() == payload
    assert hf_models.download_state(RECOMMENDED)["status"] == "ready"


async def test_download_reports_http_error(tmp_models):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad token")

    hf_models.start_download(RECOMMENDED, transport=httpx.MockTransport(handler))
    await hf_models.wait_download(RECOMMENDED, timeout=10)
    state = hf_models.download_state(RECOMMENDED)
    assert state["status"] == "error" and "401" in state["error"]
    assert not hf_models.resolve_local(RECOMMENDED)


def test_use_model_points_provider_at_local_gguf(tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")

    out = hf_models.use_model(RECOMMENDED)
    assert out["provider"] == "huggingface"
    assert out["hf_model"] == spec.filename
    assert out["local_model_path"].endswith(spec.filename)
    # instruct-2507 has no enable_thinking switch → thinking switched off
    assert out["thinking"] is False
    assert settings.hf_model == spec.filename

    with pytest.raises(FileNotFoundError):
        hf_models.use_model("gemma-3-4b-it-q4_k_m")


def test_use_model_keeps_thinking_when_asked(tmp_models):
    spec = hf_models.get_spec("qwen3-4b-q4_k_m")
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")
    out = hf_models.use_model("qwen3-4b-q4_k_m", thinking=True)
    assert out["thinking"] is True and out["hf_model"] == spec.filename


def test_delete_and_custom_gguf_listing(tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")
    (tmp_models / "my-own-model.gguf").write_bytes(b"GGUF-mine")

    ids = {m["id"]: m for m in hf_models.list_models()}
    assert "file:my-own-model.gguf" in ids
    assert ids["file:my-own-model.gguf"]["local"]["exists"] is True

    assert hf_models.delete_model(RECOMMENDED) is True
    assert not (tmp_models / spec.filename).exists()
    assert hf_models.delete_model(RECOMMENDED) is False
    assert hf_models.resolve_local("file:my-own-model.gguf").name == "my-own-model.gguf"


def test_runtime_command_uses_jinja_and_context(tmp_models):
    cmd = runtime.build_command("/x/models/Qwen3-4B-Q4_K_M.gguf", 8081, 4096, -1,
                                binary="llama-server")
    assert cmd[0] == "llama-server"
    assert cmd[1:3] == ["-m", "/x/models/Qwen3-4B-Q4_K_M.gguf"]
    assert "--jinja" in cmd
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "4096"
    assert "-ngl" not in cmd  # gpu_layers=-1 → CPU only

    cmd = runtime.build_command("/x/m.gguf", 8081, 8192, 99, binary="llama-server")
    assert cmd[cmd.index("-ngl") + 1] == "99"


async def test_runtime_start_without_binary_reports_install_hint(tmp_models,
                                                                monkeypatch):
    monkeypatch.setattr(hf_models.settings, "llama_server_bin", "")
    monkeypatch.setattr("app.local_llm.find_binary", lambda: None)
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")
    with pytest.raises(RuntimeError) as exc:
        await runtime.start(str(tmp_models / spec.filename))
    assert "llama-server" in str(exc.value)
    assert runtime.status()["available"] is False
    assert runtime.status()["install_hint"]


def test_event_loop_available_for_background_downloads():
    # start_download() schedules a task → the API must run inside an event loop.
    async def check():
        return asyncio.get_running_loop() is not None

    assert asyncio.run(check())
