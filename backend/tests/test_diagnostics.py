"""`POST /api/models/test` — diagnostik hidup endpoint OpenAI-compatible.

Inilah yang menjawab "kenapa masih error?": setiap request dilaporkan apa
adanya (status + pesan server), sehingga key salah (401), nama model tidak ada,
dan payload ditolak (400) tidak lagi terlihat sama.
"""
import json

import httpx
import pytest

from app.api import routes as api_routes
from app.config import settings
from app.providers.diagnostics import probe_endpoint

BASE = "https://ai.sumopod.com/v1"
KEY = "sk-xW256xO7uSnF6cgb0ZdDfQ"
MODEL = "qwen3.7-flash-2026-07-15"

MODELS = {"object": "list", "data": [
    {"id": MODEL, "object": "model"},
    {"id": "qwen3.7-pro-2026-07-15", "object": "model"},
]}


def _gateway(handler):
    return httpx.MockTransport(handler)


@pytest.fixture()
def stub(monkeypatch):
    def install(handler):
        monkeypatch.setattr(api_routes, "DIAGNOSTICS_TRANSPORT",
                            httpx.MockTransport(handler))
    return install


# ---------------------------------------------------------------------------
# kasus sehat
# ---------------------------------------------------------------------------
async def test_everything_ok():
    def handler(request):
        assert request.headers["authorization"] == f"Bearer {KEY}"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS)
        payload = json.loads(request.content)
        assert payload["model"] == MODEL
        if payload.get("stream"):
            return httpx.Response(200, text='data: {"choices":[{"index":0,'
                                            '"delta":{"content":"Halo"}}]}\n\n'
                                            'data: [DONE]\n\n')
        return httpx.Response(200, json={"choices": [
            {"index": 0, "message": {"content": "Halo! 🌟"},
             "finish_reason": "stop"}]})

    report = await probe_endpoint(BASE, KEY, MODEL, transport=_gateway(handler))
    assert report["ok"] is True, report
    assert report["base_url"] == BASE
    assert report["chat_url"] == f"{BASE}/chat/completions"
    names = [c["name"] for c in report["checks"]]
    assert any("non-streaming" in n for n in names)
    assert any("streaming" in n for n in names)
    assert all(c["ok"] for c in report["checks"]), report["checks"]
    assert any("Halo" in str(c.get("detail", "")) for c in report["checks"])


# ---------------------------------------------------------------------------
# key salah
# ---------------------------------------------------------------------------
async def test_bad_key_is_named_as_such():
    def handler(request):
        return httpx.Response(401, json={"error": {
            "message": "Authentication Error, No api key passed in.",
            "type": "auth_error", "code": "401"}})

    report = await probe_endpoint(BASE, "sk-salah", MODEL,
                                  transport=_gateway(handler))
    assert report["ok"] is False
    assert report["hint"] and "API key" in report["hint"]
    failing = [c for c in report["checks"] if not c["ok"]]
    assert all(c["status"] == 401 for c in failing)


# ---------------------------------------------------------------------------
# nama model tidak terdaftar di endpoint
# ---------------------------------------------------------------------------
async def test_unknown_model_is_pointed_out_with_the_real_list():
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS)
        return httpx.Response(404, json={"error": {
            "message": "The model `qwen-typo` does not exist",
            "type": "invalid_request_error", "code": "model_not_found"}})

    report = await probe_endpoint(BASE, KEY, "qwen-typo",
                                  transport=_gateway(handler))
    assert report["ok"] is False
    check = next(c for c in report["checks"] if c["name"] == "Nama model")
    assert check["ok"] is False and "qwen-typo" in check["error"]
    assert MODEL in check["detail"], "daftar model asli harus ditampilkan"
    assert "Muat model" in (report["hint"] or "")


# ---------------------------------------------------------------------------
# endpoint menolak payload chat (tapi /models hidup)
# ---------------------------------------------------------------------------
async def test_payload_rejection_shows_server_message():
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS)
        return httpx.Response(400, json={"error": {
            "message": "max_tokens must be <= 8192", "type": "bad_request"}})

    report = await probe_endpoint(BASE, KEY, MODEL, transport=_gateway(handler))
    assert report["ok"] is False
    assert "max_tokens" in (report["hint"] or "") or \
        any("max_tokens" in str(c.get("error", "")) for c in report["checks"])


# ---------------------------------------------------------------------------
# endpoint mati total
# ---------------------------------------------------------------------------
async def test_unreachable_endpoint():
    def handler(request):
        raise httpx.ConnectError("Temporary failure in name resolution")

    report = await probe_endpoint(BASE, KEY, MODEL, transport=_gateway(handler))
    assert report["ok"] is False
    assert any("name resolution" in str(c.get("error", ""))
               for c in report["checks"])


async def test_empty_base_url():
    report = await probe_endpoint("", KEY, MODEL)
    assert report["ok"] is False and "Base URL kosong" in (report["hint"] or "")


# ---------------------------------------------------------------------------
# endpoint HTTP
# ---------------------------------------------------------------------------
def test_models_test_endpoint_uses_stored_settings(client, stub):
    client.post("/api/settings", json={
        "provider": "openai", "openai_base_url": BASE,
        "openai_api_key": KEY, "openai_model": MODEL})
    try:
        def handler(request):
            if request.url.path.endswith("/models"):
                return httpx.Response(200, json=MODELS)
            return httpx.Response(200, json={"choices": [
                {"index": 0, "message": {"content": "Halo!"},
                 "finish_reason": "stop"}]})

        stub(handler)
        r = client.post("/api/models/test", json={}).json()
        assert r["ok"] is True
        assert r["provider"] == "openai"
        assert r["base_url"] == BASE
        assert len(r["checks"]) == 3
    finally:
        client.post("/api/settings", json={"provider": "mock"})


def test_models_test_endpoint_accepts_typed_values(client, stub):
    """Key/URL yang baru diketik harus diuji sebelum disimpan."""
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    stub(handler)
    r = client.post("/api/models/test", json={
        "provider": "openai", "base_url": f"{BASE}/chat/completions",
        "api_key": "sk-baru", "model": MODEL}).json()
    assert r["ok"] is False
    assert r["base_url"] == BASE, "URL yang ditempel harus dinormalkan"
    assert any(c["status"] == 401 for c in r["checks"])


def test_models_test_for_mock_provider(client):
    r = client.post("/api/models/test", json={"provider": "mock"}).json()
    assert r["ok"] is True and r["checks"][0]["name"] == "mode mock"


async def test_model_not_in_list_fails_even_when_chat_works():
    """Gateway bisa saja tetap menjawab, tapi model yang dikonfigurasi tidak ada."""
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=MODELS)
        return httpx.Response(200, json={"choices": [
            {"index": 0, "message": {"content": "Halo!"},
             "finish_reason": "stop"}]})

    report = await probe_endpoint(BASE, KEY, "qwen-typo",
                                  transport=_gateway(handler))
    assert report["ok"] is False, "nama model salah harus terlihat sebagai masalah"
    assert "Muat model" in (report["hint"] or "")
    assert all(c["ok"] for c in report["checks"]
               if c["name"].startswith("POST")), "chat-nya sendiri jalan"
