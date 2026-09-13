"""Perilaku provider OpenAI-compatible terhadap gateway "rewel" (LiteLLM dkk.).

Semua kasus di sini adalah bentuk jawaban server nyata:
  * 400 karena `logprobs` / `stream_options` / `tools` ditolak,
  * 401 karena API key salah,
  * 200 OK tetapi error dikirim **di dalam** stream (`data: {"error": …}`),
  * 200 OK tetapi badan kosong,
  * semua bentuk streaming ditolak → fallback non-streaming (bentuk curl).
"""
import json

import httpx

from app.providers import OpenAIProtocolProvider

BASE = "https://ai.sumopod.com/v1"


def _sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


def _final(text="Halo! 🌟"):
    return (_sse({"choices": [{"index": 0, "delta": {"content": text}}]})
            + _sse({"choices": [{"index": 0, "delta": {},
                                 "finish_reason": "stop"}]})
            + "data: [DONE]\n\n")


def _plain_json(text="Halo! 🌟"):
    return {"id": "x", "object": "chat.completion", "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4,
                      "total_tokens": 13}}


def _provider(handler, model="qwen3.7-flash-2026-07-15"):
    return OpenAIProtocolProvider(BASE, api_key="sk-xW256xO7uSnF6cgb0ZdDfQ",
                                  model=model,
                                  transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# error di dalam stream (200 OK!) harus terlihat, bukan jadi jawaban kosong
# ---------------------------------------------------------------------------
async def test_error_frame_inside_stream_is_surfaced():
    def handler(request):
        return httpx.Response(200, text=_sse({"error": {
            "message": "Model not found or access denied",
            "type": "invalid_request_error", "code": "model_not_found"}})
            + "data: [DONE]\n\n")

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "hi"}], [])]
    assert [e.type for e in events] == ["error"]
    message = events[0].data["message"]
    assert "Model not found" in message
    assert "Muat model" in message, "harus ada petunjuk yang bisa ditindaklanjuti"


async def test_401_reports_auth_hint_and_no_retry():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(401, json={"error": {
            "message": "Authentication Error, No api key passed in.",
            "type": "auth_error", "code": "401"}})

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "hi"}], [])]
    assert [e.type for e in events] == ["error"]
    assert "API key ditolak" in events[0].data["message"]
    assert len(seen) == 1, "401 tidak boleh memicu retry ladder"


# ---------------------------------------------------------------------------
# ladder: tools ditolak → rung terakhir tanpa tools
# ---------------------------------------------------------------------------
async def test_rejects_tools_then_succeeds_without_them():
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if "tools" in payload:
            return httpx.Response(400, json={"error": {
                "message": "tools is not supported by this model"}})
        return httpx.Response(200, text=_final())

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "hi"}],
        [{"type": "function", "function": {"name": "web_search"}}],
        logprobs=True)]
    assert "".join(e.data["text"] for e in events if e.type == "delta") == "Halo! 🌟"
    assert len(seen) == 4, [sorted(p) for p in seen]
    assert "tools" not in seen[3]
    assert any(e.type == "note" for e in events)


# ---------------------------------------------------------------------------
# fallback non-streaming: kalau curl jalan, chat pun jalan
# ---------------------------------------------------------------------------
async def test_falls_back_to_non_streaming_when_stream_is_rejected():
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        if payload.get("stream"):
            return httpx.Response(400, json={"error": {
                "message": "streaming is disabled for this deployment"}})
        return httpx.Response(200, json=_plain_json())

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "Say hello in a creative way"}], [])]
    types = [e.type for e in events]

    assert "".join(e.data["text"] for e in events if e.type == "delta") == "Halo! 🌟"
    assert "done" in types and "usage" in types
    note = next(e for e in events if e.type == "note"
                and e.data.get("status") == "fallback")
    assert "non-streaming" in note.data["message"]
    assert seen[-1]["stream"] is False, "request terakhir harus non-streaming"
    assert "stream_options" not in seen[-1]


async def test_non_streaming_fallback_parses_tool_calls():
    def handler(request):
        payload = json.loads(request.content)
        if payload.get("stream"):
            return httpx.Response(500, text="nope")
        return httpx.Response(200, json={
            "choices": [{"index": 0, "finish_reason": "tool_calls",
                         "message": {"role": "assistant", "content": "",
                                     "tool_calls": [{
                                         "id": "call_1", "type": "function",
                                         "function": {
                                             "name": "calculator",
                                             "arguments":
                                                 '{"expression": "2+2"}'}}]}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3,
                      "total_tokens": 8}})

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "2+2?"}],
        [{"type": "function", "function": {"name": "calculator"}}])]
    call = next(e for e in events if e.type == "tool_calls").data["calls"][0]
    assert call["name"] == "calculator"
    assert call["arguments"] == {"expression": "2+2"}


async def test_all_shapes_rejected_reports_the_server_message():
    def handler(request):
        return httpx.Response(404, json={"error": {
            "message": "The model `qwen3.7-flash-2026-07-15` does not exist",
            "type": "invalid_request_error", "code": "model_not_found"}})

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "hi"}], [])]
    assert events[-1].type == "error", [e.type for e in events]
    assert "does not exist" in events[-1].data["message"]
    assert "Muat model" in events[-1].data["message"]
    # seluruh ladder + fallback harus terlihat di Interpreter, bukan senyap
    assert sum(e.type == "note" for e in events) >= 4


async def test_connection_error_is_reported():
    def handler(request):
        raise httpx.ConnectError("name or service not known")

    events = [e async for e in _provider(handler).stream(
        [{"role": "user", "content": "hi"}], [])]
    assert events[-1].type == "error", [e.type for e in events]
    assert "connection error" in events[-1].data["message"]
