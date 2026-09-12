"""Settings semantics + the provider retry ladder + the agent's max_steps guard.

All three were found by driving the app against a real llama.cpp server:
  * an API key could not be cleared (the UI always posts the field),
  * a chat template without `enable_thinking` answered HTTP 400 and the retry
    kept the offending key, so the turn failed,
  * a model that keeps asking for tools ended the turn with an empty answer and
    no error at all.
"""
import json

import httpx

from app.config import settings, update_settings
from app.providers import HuggingFaceProvider


def _sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


def _final(text="Paris."):
    return (
        _sse({"choices": [{"index": 0, "delta": {"role": "assistant"}}]})
        + _sse({"choices": [{"index": 0, "delta": {"content": text}}]})
        + _sse({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        + "data: [DONE]\n\n"
    )


# --------------------------------------------------------------------------
# API keys: absent = untouched, "" = clear it
# --------------------------------------------------------------------------
def test_api_key_can_be_cleared(client):
    s = client.post("/api/settings", json={"hf_api_key": "sk-local-1234"}).json()
    assert s["has_hf_key"] is True
    assert s["hf_api_key_masked"]

    s = client.post("/api/settings", json={"hf_api_key": ""}).json()
    assert s["has_hf_key"] is False, "key kosong harus menghapus key tersimpan"
    assert s["hf_api_key_masked"] == ""


def test_key_field_absent_keeps_the_stored_key(client):
    client.post("/api/settings", json={"openai_api_key": "sk-openai-9999"})
    s = client.post("/api/settings", json={"temperature": 0.4}).json()
    assert s["has_openai_key"] is True
    assert s["temperature"] == 0.4


def test_unknown_provider_is_rejected(client):
    r = client.post("/api/settings", json={"provider": "gemini"})
    assert r.status_code == 422
    assert "provider" in r.text
    assert settings.provider != "gemini"


def test_base_url_normalised_on_save(client):
    s = client.post("/api/settings", json={
        "provider": "openai",
        "openai_base_url": "https://ai.sumopod.com/v1/chat/completions",
    }).json()
    assert s["openai_base_url"] == "https://ai.sumopod.com/v1"
    update_settings(provider="mock")


# --------------------------------------------------------------------------
# Retry ladder: the last attempt must drop chat_template_kwargs
# --------------------------------------------------------------------------
async def test_retry_drops_chat_template_kwargs():
    attempts = []

    def handler(request):
        payload = json.loads(request.content)
        attempts.append(payload)
        if "chat_template_kwargs" in payload:
            return httpx.Response(
                400, json={"error": "template error: undefined function"})
        return httpx.Response(200, text=_final())

    provider = HuggingFaceProvider(settings)
    provider.transport = httpx.MockTransport(handler)
    events = [e async for e in provider.stream(
        [{"role": "user", "content": "hi"}], [], logprobs=True)]

    types = [e.type for e in events]
    assert "note" in types, "downgrade payload harus terlihat di Interpreter"
    assert len(attempts) == 3, [sorted(p) for p in attempts]
    assert "stream_options" in attempts[0] and "logprobs" in attempts[0]
    assert "stream_options" not in attempts[1] and "logprobs" not in attempts[1]
    assert "chat_template_kwargs" in attempts[1]        # extras still there
    assert "chat_template_kwargs" not in attempts[2]    # bare payload works
    assert "".join(e.data["text"] for e in events if e.type == "delta") == "Paris."


async def test_retry_on_500_logprobs_with_tools():
    """Real llama.cpp: `logprobs is not supported with tools + stream` → HTTP 500."""
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if payload.get("logprobs") and payload.get("tools"):
            return httpx.Response(500, json={"error": {
                "code": 500, "type": "server_error",
                "message": "logprobs is not supported with tools + stream"}})
        return httpx.Response(200, text=_final())

    provider = HuggingFaceProvider(settings)
    provider.transport = httpx.MockTransport(handler)
    events = [e async for e in provider.stream(
        [{"role": "user", "content": "hi"}],
        [{"type": "function", "function": {"name": "web_search"}}],
        logprobs=True)]

    assert any(e.type == "note" for e in events)
    assert "".join(e.data["text"] for e in events if e.type == "delta") == "Paris."
    assert len(seen) == 2 and "logprobs" not in seen[1]

    # the second turn must not pay for the failing rung again
    again = [e async for e in provider.stream(
        [{"role": "user", "content": "hi"}],
        [{"type": "function", "function": {"name": "web_search"}}],
        logprobs=True)]
    assert len(seen) == 3, "provider harus ingat payload yang ditolak server"
    assert "logprobs" not in seen[2]
    assert not any(e.type == "note" for e in again)


async def test_no_retry_when_the_first_attempt_works():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, text=_final("ok"))

    provider = HuggingFaceProvider(settings)
    provider.transport = httpx.MockTransport(handler)
    [e async for e in provider.stream([{"role": "user", "content": "hi"}], [])]
    assert len(calls) == 1
    assert calls[0]["chat_template_kwargs"] == {
        "enable_thinking": bool(settings.thinking)}


# --------------------------------------------------------------------------
# Agent: running out of steps must not produce a silent empty answer
# --------------------------------------------------------------------------
def test_max_steps_without_final_answer_is_reported(client, monkeypatch):
    from app.tools import get_tool
    from app.tools.base import ToolResult

    async def fake_run(args, ctx):  # no real network in this test
        return ToolResult(summary="stub", data={"results": []})

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)
    client.post("/api/settings", json={"provider": "mock", "max_steps": 1})
    try:
        with client.stream("POST", "/api/chat",
                           json={"message": "cari berita terbaru"}) as r:
            evs = [json.loads(l[6:]) for l in r.iter_lines()
                   if l.startswith("data: ")]
    finally:
        client.post("/api/settings", json={"max_steps": 6})

    types = [e["type"] for e in evs]
    assert "tool_call" in types
    note = next(e for e in evs if e["type"] == "note")
    assert "langkah" in note["message"]
    done = next(e for e in evs if e["type"] == "done")
    assert done["stopped_reason"] == "max_steps"
    assert done["answer"].strip(), "jawaban kosong tanpa penjelasan = bug"
    assert next(e for e in evs if e["type"] == "agent_done")["answer"]


# --------------------------------------------------------------------------
# SSE keep-alive: a silent stream must not be killed by the proxy
# --------------------------------------------------------------------------
def test_sse_keepalive_is_sent_while_the_llm_thinks(client, monkeypatch):
    import asyncio

    from app.api import routes
    from app.tools import get_tool
    from app.tools.base import ToolResult

    async def slow_run(args, ctx):          # LLM + tool yang lambat
        await asyncio.sleep(0.35)
        return ToolResult(summary="stub", data={"results": []})

    monkeypatch.setattr(get_tool("web_search"), "run", slow_run)
    monkeypatch.setattr(routes, "KEEPALIVE_S", 0.05)

    with client.stream("POST", "/api/chat",
                       json={"message": "cari berita AI"}) as r:
        raw = b"".join(r.iter_raw()).decode()
    assert ": keep-alive" in raw, "stream diam harus tetap mengirim keep-alive"
    assert "agent_done" in raw
