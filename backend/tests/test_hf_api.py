"""HTTP surface for the offline-model manager + provider settings."""
import httpx
import pytest

from app import hf_models
from app.api import routes as api_routes
from app.config import settings
from app.local_llm import runtime

RECOMMENDED = "qwen3-4b-instruct-2507-q4_k_m"


@pytest.fixture()
def tmp_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", str(tmp_path))
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_model", "Qwen/Qwen3-8B-GGUF")
    monkeypatch.setattr(settings, "hf_base_url", "http://127.0.0.1:8081/v1")
    hf_models._downloads.clear()
    hf_models._tasks.clear()
    yield tmp_path
    hf_models._downloads.clear()
    hf_models._tasks.clear()


def test_list_hf_models_endpoint(client, tmp_models):
    data = client.get("/api/hf/models").json()
    assert data["models_dir"] == str(tmp_models)
    ids = {m["id"] for m in data["models"]}
    assert RECOMMENDED in ids and "qwen3-8b-q4_k_m" in ids
    rec = next(m for m in data["models"] if m["id"] == RECOMMENDED)
    assert rec["recommended"] is True and rec["local"]["exists"] is False
    assert "runtime" in data and "available" in data["runtime"]
    assert data["active"]["hf_model"] == "Qwen/Qwen3-8B-GGUF"


def test_download_endpoint_kicks_off_and_reports_state(client, tmp_models,
                                                       monkeypatch):
    started = {}

    def fake_start(model_id, transport=None):
        started["model_id"] = model_id
        return {"model_id": model_id, "status": "downloading", "percent": 0.0}

    monkeypatch.setattr(hf_models, "start_download", fake_start)
    r = client.post(f"/api/hf/models/{RECOMMENDED}/download").json()
    assert r["ok"] is True and started["model_id"] == RECOMMENDED
    assert r["download"]["status"] == "downloading"
    assert r["models_dir"] == str(tmp_models)

    bad = client.post("/api/hf/models/does-not-exist/download").json()
    assert "error" in bad


def test_use_endpoint_requires_download(client, tmp_models):
    r = client.post(f"/api/hf/models/{RECOMMENDED}/use", json={}).json()
    assert "error" in r and "belum diunduh" in r["error"]


def test_use_endpoint_switches_provider_and_thinking(client, tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")

    r = client.post(f"/api/hf/models/{RECOMMENDED}/use",
                    json={"thinking": True}).json()
    assert r["ok"] is True
    assert r["settings"]["provider"] == "huggingface"
    assert r["settings"]["hf_model"] == spec.filename
    assert r["settings"]["thinking"] is True
    assert r["settings"]["local_model_path"].endswith(spec.filename)
    assert r["runtime"]["running"] is False  # run=False → no llama-server


def test_use_endpoint_reports_missing_llama_server(client, tmp_models,
                                                   monkeypatch):
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")
    monkeypatch.setattr("app.local_llm.find_binary", lambda: None)

    r = client.post(f"/api/hf/models/{RECOMMENDED}/use", json={"run": True}).json()
    assert "error" in r and "llama-server" in r["error"]
    assert r["runtime"]["install_hint"]


def test_delete_endpoint(client, tmp_models):
    spec = hf_models.get_spec(RECOMMENDED)
    (tmp_models / spec.filename).write_bytes(b"GGUF-fake")
    assert client.post(f"/api/hf/models/{RECOMMENDED}/delete").json()["ok"] is True
    assert not (tmp_models / spec.filename).exists()
    assert "error" in client.post(
        f"/api/hf/models/{RECOMMENDED}/delete").json()


def test_runtime_stop_endpoint(client):
    assert client.post("/api/hf/runtime/stop").json()["ok"] is True
    assert client.get("/api/hf/runtime").json()["running"] is False


def test_settings_accepts_full_endpoint_url(client):
    r = client.post("/api/settings", json={
        "provider": "openai",
        "openai_base_url": "https://ai.sumopod.com/v1/chat/completions",
        "openai_model": "qwen3.7-flash-2026-07-15",
        "openai_api_key": "random_token",
    }).json()
    assert r["openai_base_url"] == "https://ai.sumopod.com/v1"
    assert r["model"] == "qwen3.7-flash-2026-07-15"
    assert r["has_openai_key"] is True
    client.post("/api/settings", json={
        "provider": "mock",
        "openai_base_url": "https://api.openai.com/v1"})


def test_health_uses_normalised_url_and_api_key(client, monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(401, text="unauthorized")

    class _Client(httpx.AsyncClient):
        def __init__(self, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(**kw)

    monkeypatch.setattr(api_routes.httpx, "AsyncClient", _Client)
    client.post("/api/settings", json={
        "provider": "openai",
        "openai_base_url": "https://ai.sumopod.com/v1/chat/completions",
        "openai_api_key": "random_token"})
    h = client.get("/api/health").json()
    assert seen["url"] == "https://ai.sumopod.com/v1/models"
    assert seen["auth"] == "Bearer random_token"
    # server answered (401) → endpoint exists, only the key is wrong
    assert h["llm_reachable"] is True and h["llm_status"] == 401
    client.post("/api/settings", json={
        "provider": "mock", "openai_api_key": "",
        "openai_base_url": "https://api.openai.com/v1"})


def test_runtime_status_shape():
    st = runtime.status()
    assert set(st) >= {"binary", "available", "running", "base_url",
                       "install_hint"}
