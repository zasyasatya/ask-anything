"""HTTP surface for the offline-model manager (HuggingFace Hub → models/)."""
import json

import httpx
import pytest

from app import hf_hub
from app.api import routes as api_routes
from app.config import settings
from app.local_inference import engine

REPO = "Qwen/Qwen3-1.7B"

SIBLINGS = [
    {"rfilename": "config.json", "size": 600},
    {"rfilename": "tokenizer_config.json", "size": 2_000},
    {"rfilename": "model.safetensors", "size": 20_000},
]


def _hub(request: httpx.Request) -> httpx.Response:
    """Fake Hub: search, repo info and file download."""
    path = request.url.path
    if path == "/api/models":
        return httpx.Response(200, json=[{"id": REPO, "downloads": 5,
                                          "safetensors": {"total": 1_7e9}}])
    if path.startswith("/api/models/"):
        return httpx.Response(200, json={"id": REPO, "sha": "abc",
                                         "siblings": SIBLINGS})
    if "/resolve/" in path:
        return httpx.Response(200, content=b"z" * 500,
                              headers={"content-length": "500"})
    return httpx.Response(404, text="nope")


@pytest.fixture()
def tmp_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", str(tmp_path))
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "hf_model", "")
    monkeypatch.setattr(api_routes, "HUB_TRANSPORT", httpx.MockTransport(_hub))
    hf_hub._jobs.clear()
    yield tmp_path
    hf_hub._jobs.clear()


def test_list_hf_models_endpoint(client, tmp_models):
    data = client.get("/api/hf/models").json()
    assert data["models_dir"] == str(tmp_models)
    assert data["models"] == []
    assert data["engine"]["state"] in ("idle", "ready", "error")
    assert "available" in data["deps"]
    assert data["active"]["hf_mode"] == "local"


def test_search_endpoint_reaches_the_hub(client, tmp_models):
    r = client.get("/api/hf/search", params={"q": "qwen3"}).json()
    assert r["ok"] is True
    assert [m["repo_id"] for m in r["models"]] == [REPO]


def test_download_endpoint_and_progress_polling(client, tmp_models):
    r = client.post("/api/hf/models/download", json={"repo_id": REPO}).json()
    assert r["ok"] is True
    assert r["download"]["status"] == "downloading"
    assert r["models_dir"] == str(tmp_models)

    # UI polls this until status == "ready"
    for _ in range(200):
        data = client.get("/api/hf/downloads").json()
        state = next(d for d in data["downloads"] if d["repo_id"] == REPO)
        if state["status"] == "ready":
            break
    assert state["status"] == "ready", state
    assert state["percent"] == 100.0
    assert (tmp_models / "Qwen" / "Qwen3-1.7B" / "config.json").is_file()

    listed = client.get("/api/hf/models").json()["models"]
    assert [m["repo_id"] for m in listed] == [REPO]
    assert listed[0]["ready"] is True


def test_download_endpoint_rejects_bad_repo_id(client, tmp_models):
    r = client.post("/api/hf/models/download", json={"repo_id": "bukanrepo"})
    assert "error" in r.json()


def test_use_endpoint_requires_a_complete_download(client, tmp_models):
    r = client.post("/api/hf/models/use", json={"repo_id": REPO}).json()
    assert "error" in r and "belum terunduh" in r["error"]


def test_use_endpoint_switches_provider_to_local(client, tmp_models):
    client.post("/api/hf/models/download", json={"repo_id": REPO})
    for _ in range(200):
        if client.get("/api/hf/downloads").json()["downloads"][0]["status"] == "ready":
            break

    r = client.post("/api/hf/models/use",
                    json={"repo_id": REPO, "thinking": False,
                          "load": False}).json()
    assert r["ok"] is True
    s = r["settings"]
    assert s["provider"] == "huggingface"
    assert s["hf_mode"] == "local"
    assert s["hf_model"] == REPO
    assert s["thinking"] is False
    assert r["engine"]["state"] in ("idle", "ready", "error")

    stored = client.get("/api/settings").json()
    assert stored["hf_model"] == REPO and stored["hf_mode"] == "local"


def test_delete_endpoint_removes_the_model(client, tmp_models):
    client.post("/api/hf/models/download", json={"repo_id": REPO})
    for _ in range(200):
        if client.get("/api/hf/downloads").json()["downloads"][0]["status"] == "ready":
            break
    assert (tmp_models / "Qwen" / "Qwen3-1.7B").is_dir()

    assert client.post("/api/hf/models/delete",
                       json={"repo_id": REPO}).json()["ok"] is True
    assert not (tmp_models / "Qwen" / "Qwen3-1.7B").exists()
    assert client.get("/api/hf/models").json()["models"] == []


def test_runtime_endpoints(client, tmp_models):
    st = client.get("/api/hf/runtime").json()
    assert st["state"] in ("idle", "ready", "error")
    assert "hint" in st and "install_hint" in st

    stopped = client.post("/api/hf/runtime/stop").json()
    assert stopped["ok"] is True and stopped["engine"]["state"] == "idle"


def test_health_reports_local_model_state(client, tmp_models, monkeypatch):
    monkeypatch.setattr(engine, "model", None)
    monkeypatch.setattr(engine, "state", "idle")
    h = client.get("/api/health").json()
    assert h["provider"] == "huggingface" and h["hf_mode"] == "local"
    assert h["local_llm"] is False
    assert h["llm_reachable"] is False
    assert h["llm_error"], "tanpa model harus ada pesan yang bisa ditindaklanjuti"


async def test_manifest_is_written_for_the_ui(tmp_models):
    hf_hub.start_download(REPO, transport=httpx.MockTransport(_hub))
    state = await hf_hub.wait_download(REPO, timeout=30)
    assert state["status"] == "ready", state
    manifest = json.loads(
        (tmp_models / "Qwen" / "Qwen3-1.7B" / hf_hub.MANIFEST_NAME).read_text())
    assert manifest["repo_id"] == REPO and manifest["complete"] is True
    assert manifest["file_count"] == len(SIBLINGS)
