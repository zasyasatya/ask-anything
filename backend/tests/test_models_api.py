"""`POST /api/models` — model list of an OpenAI-compatible endpoint.

The endpoint feeds the dropdown in *Settings provider*, so it has to normalise
every shape a real server answers with and never blow up when the server is
down or the key is wrong.
"""
import httpx
import pytest

from app.api import routes


def _probe(client, payload):
    r = client.post("/api/models", json=payload)
    assert r.status_code == 200
    return r.json()


@pytest.fixture()
def stub(monkeypatch):
    """Route the discovery HTTP call through an httpx.MockTransport."""

    def install(handler):
        monkeypatch.setattr(routes, "DISCOVERY_TRANSPORT",
                            httpx.MockTransport(handler))
    return install


def test_openai_shape(client, stub):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"object": "list", "data": [
            {"id": "gpt-4o-mini", "object": "model"},
            {"id": "gpt-4o", "object": "model"},
        ]})

    stub(handler)
    out = _probe(client, {"provider": "openai",
                          "base_url": "https://api.openai.com/v1",
                          "api_key": "sk-test"})
    assert out["ok"] is True
    assert [m["id"] for m in out["models"]] == ["gpt-4o-mini", "gpt-4o"]
    assert out["count"] == 2
    assert seen["url"] == "https://api.openai.com/v1/models"
    assert seen["auth"] == "Bearer sk-test"


def test_llamacpp_shape_is_deduplicated(client, stub):
    """llama.cpp answers with BOTH `data` and `models` for the same model."""

    def handler(request):
        return httpx.Response(200, json={
            "models": [{"model": "/models/Qwen3-4B-Q4_K_M.gguf", "type": "model"}],
            "object": "list",
            "data": [{"id": "/models/Qwen3-4B-Q4_K_M.gguf", "owned_by": "llamacpp"}],
        })

    stub(handler)
    out = _probe(client, {"provider": "huggingface",
                          "base_url": "http://127.0.0.1:8081/v1", "api_key": ""})
    assert out["count"] == 1
    m = out["models"][0]
    assert m["id"] == "/models/Qwen3-4B-Q4_K_M.gguf"      # what the API expects
    assert m["label"] == "Qwen3-4B-Q4_K_M"                 # what a human reads


def test_bare_list_shape(client, stub):
    stub(lambda request: httpx.Response(200, json=["a-model", "b-model"]))
    out = _probe(client, {"provider": "openai", "base_url": "https://gw/v1"})
    assert [m["id"] for m in out["models"]] == ["a-model", "b-model"]


def test_curl_style_url_is_normalised(client, stub):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"data": [{"id": "qwen3.7-flash"}]})

    stub(handler)
    out = _probe(client, {"provider": "openai",
                          "base_url": "https://ai.sumopod.com/v1/chat/completions",
                          "api_key": "random_token"})
    assert seen["url"] == "https://ai.sumopod.com/v1/models"
    assert out["ok"] is True and out["count"] == 1


def test_auth_failure_is_reported_not_raised(client, stub):
    stub(lambda request: httpx.Response(401, text="invalid api key"))
    out = _probe(client, {"provider": "openai", "base_url": "https://gw/v1",
                          "api_key": "wrong"})
    assert out["ok"] is False
    assert out["status"] == 401
    assert "401" in out["error"]
    assert out["models"] == []


def test_unreachable_endpoint(client, stub):
    def handler(request):
        raise httpx.ConnectError("All connection attempts failed")

    stub(handler)
    out = _probe(client, {"provider": "huggingface",
                          "base_url": "http://127.0.0.1:9/v1"})
    assert out["ok"] is False and out["status"] is None
    assert "dihubungi" in out["error"]


def test_empty_base_url(client, stub):
    stub(lambda request: httpx.Response(200, json={"data": []}))
    out = _probe(client, {"provider": "openai", "base_url": ""})
    assert out["ok"] is False and "kosong" in out["error"]


def test_mock_provider_needs_no_network(client, stub):
    stub(lambda request: pytest.fail("mock tidak boleh menyentuh jaringan"))
    out = _probe(client, {"provider": "mock"})
    assert out["ok"] is True
    assert out["models"][0]["id"] == "mock-agent"


def test_unknown_provider(client, stub):
    stub(lambda request: pytest.fail("provider tak dikenal tidak boleh probing"))
    out = _probe(client, {"provider": "gemini"})
    assert out["ok"] is False and "gemini" in out["error"]


def test_defaults_to_active_provider(client, monkeypatch, stub):
    """No body at all → probe whatever the app is currently configured with."""
    from app.config import settings, update_settings

    def handler(request):
        assert str(request.url) == "http://127.0.0.1:8081/v1/models"
        return httpx.Response(200, json={"data": [{"id": "local-model"}]})

    stub(handler)
    update_settings(provider="huggingface", hf_base_url="http://127.0.0.1:8081/v1")
    out = _probe(client, {})
    assert out["provider"] == settings.provider == "huggingface"
    assert out["models"][0]["id"] == "local-model"
