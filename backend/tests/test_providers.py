import json

import httpx

from app.providers import HuggingFaceProvider, MockProvider, OpenAIProtocolProvider
from app.config import Settings


def _sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


def _chunk(delta, finish=None, logprobs=None, usage=None):
    obj = {
        "id": "x", "object": "chat.completion.chunk", "created": 1, "model": "m",
        "choices": [{"index": 0, "delta": delta, "logprobs": logprobs,
                     "finish_reason": finish}],
    }
    if usage is not None:
        obj["usage"] = usage
        obj["choices"] = []
    return _sse(obj)


async def test_openai_protocol_parses_think_tools_logprobs():
    body = (
        _chunk({"role": "assistant"})
        + _chunk({"content": "<think>planning the an"})
        + _chunk({"content": "swer</think>"})
        + _chunk({"content": "Final answer."},
                 logprobs={"content": [
                     {"token": "Final", "logprob": -0.2,
                      "top_logprobs": [{"token": "Final", "logprob": -0.2}]}]})
        + _chunk({"tool_calls": [{"index": 0, "id": "c1", "type": "function",
                                  "function": {"name": "calc",
                                               "arguments": ""}}]})
        + _chunk({"tool_calls": [{"index": 0, "function":
                                  {"arguments": '{"expression": "1+1"}'}}]})
        + _chunk({}, finish="tool_calls")
        + _chunk({}, usage={"prompt_tokens": 5, "completion_tokens": 7,
                            "total_tokens": 12})
        + "data: [DONE]\n\n"
    )

    def handler(request):
        return httpx.Response(200, text=body)

    provider = OpenAIProtocolProvider("http://fake/v1",
                                      transport=httpx.MockTransport(handler))
    events = [e async for e in provider.stream(
        [{"role": "user", "content": "hi"}], [], logprobs=True)]
    types = [e.type for e in events]
    assert "thinking" in types and "delta" in types and "logprobs" in types
    assert "tool_calls" in types and "usage" in types and "done" in types

    thinking = "".join(e.data["text"] for e in events if e.type == "thinking")
    assert thinking == "planning the answer"
    delta = "".join(e.data["text"] for e in events if e.type == "delta")
    assert delta == "Final answer."
    calls = next(e for e in events if e.type == "tool_calls").data["calls"]
    assert calls[0]["name"] == "calc"
    assert calls[0]["arguments"] == {"expression": "1+1"}
    assert events[-1].data["finish_reason"] == "tool_calls"


async def test_openai_protocol_error_status():
    def handler(request):
        return httpx.Response(401, text="bad key")

    provider = OpenAIProtocolProvider("http://fake/v1",
                                      transport=httpx.MockTransport(handler))
    events = [e async for e in provider.stream([], [])]
    assert events[0].type == "error"
    assert "401" in events[0].data["message"]


async def test_hf_provider_wiring():
    s = Settings(hf_base_url="http://local:8081/v1/", hf_model="Qwen/X-GGUF")
    p = HuggingFaceProvider(s)
    assert p.base_url == "http://local:8081/v1"
    assert p.model_label() == "Qwen/X-GGUF (local)"


async def test_mock_provider_tool_then_answer():
    p = MockProvider()
    first = [e async for e in p.stream(
        [{"role": "user", "content": "buatkan diagram alur x"}], [])]
    assert first[0].type == "thinking"
    tc = [e for e in first if e.type == "tool_calls"]
    assert tc and tc[0].data["calls"][0]["name"] == "create_diagram"

    second = [e async for e in p.stream(
        [{"role": "user", "content": "buatkan diagram alur x"},
         {"role": "tool", "content": "{}"}], [])]
    assert any(e.type == "delta" for e in second)
    assert second[-1].type == "done"
