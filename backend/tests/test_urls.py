"""Base-URL canonicalisation + provider wiring for pasted endpoint URLs."""
import json

import httpx

from app.config import Settings, update_settings
from app.providers import HuggingFaceProvider, OpenAIProtocolProvider
from app.providers.url_utils import (chat_completions_url,
                                     normalize_openai_base_url)

SUMOPOD = "https://ai.sumopod.com/v1/chat/completions"


def test_normalize_openai_base_url_shapes():
    cases = {
        SUMOPOD: "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com/v1/chat/completions/": "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com/v1": "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com/v1/": "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com": "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com/v1/models": "https://ai.sumopod.com/v1",
        "https://ai.sumopod.com/v1/chat": "https://ai.sumopod.com/v1",
        "https://AI.SumoPod.com:8443/V1/Chat/Completions": "https://ai.sumopod.com:8443/v1",
        "ai.sumopod.com/v1/chat/completions": "https://ai.sumopod.com/v1",
        "http://127.0.0.1:8081/v1/": "http://127.0.0.1:8081/v1",
        "http://127.0.0.1:8081": "http://127.0.0.1:8081/v1",
        # gateway with a non-versioned prefix is left alone
        "https://gw.example.com/openai/chat/completions": "https://gw.example.com/openai",
        "https://gw.example.com/api/v1beta/chat/completions":
            "https://gw.example.com/api/v1beta",
        "": "",
    }
    for raw, expected in cases.items():
        assert normalize_openai_base_url(raw) == expected, raw


def test_normalize_tolerates_pasted_markdown_and_quotes():
    pasted = '[https://ai.sumopod.com/v1/chat/completions](https://ai.sumopod.com/v1/chat/completions)'
    assert normalize_openai_base_url(pasted) == "https://ai.sumopod.com/v1"
    assert normalize_openai_base_url(
        '  "https://ai.sumopod.com/v1/chat/completions"  '
    ) == "https://ai.sumopod.com/v1"


def test_chat_completions_url_never_duplicates_path():
    assert chat_completions_url(SUMOPOD) == SUMOPOD
    assert chat_completions_url("https://ai.sumopod.com") == SUMOPOD


def _one_chunk(text="hi"):
    return ('data: {"choices":[{"index":0,"delta":{"content":"%s"}}]}\n\n'
            'data: [DONE]\n\n' % text)


async def test_provider_posts_to_single_chat_completions_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, text=_one_chunk())

    provider = OpenAIProtocolProvider(
        SUMOPOD, api_key="random_token", model="qwen3.7-flash-2026-07-15",
        transport=httpx.MockTransport(handler))
    assert provider.base_url == "https://ai.sumopod.com/v1"
    events = [e async for e in provider.stream(
        [{"role": "user", "content": "Say hello in a creative way"}], [])]
    assert seen["url"] == SUMOPOD
    assert seen["auth"] == "Bearer random_token"
    assert [e.type for e in events] == ["delta", "done"]


async def test_empty_stream_is_reported_not_swallowed():
    """200 + hanya `data: [DONE]` = jawaban kosong tanpa penjelasan (bug lama)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="data: [DONE]\n\n")

    provider = OpenAIProtocolProvider(
        SUMOPOD, model="qwen3.7-flash-2026-07-15",
        transport=httpx.MockTransport(handler))
    events = [e async for e in provider.stream([{"role": "user", "content": "hi"}], [])]
    assert [e.type for e in events] == ["error"]
    assert "kosong" in events[0].data["message"]


async def test_provider_retries_without_stream_options_on_400():
    requests_seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests_seen.append(body)
        if "stream_options" in body:
            return httpx.Response(400, text='{"error":"stream_options unsupported"}')
        return httpx.Response(200, text='data: {"choices":[{"index":0,'
                                        '"delta":{"content":"hi"}}]}\n\n'
                                        'data: [DONE]\n\n')

    provider = OpenAIProtocolProvider(
        SUMOPOD, transport=httpx.MockTransport(handler))
    events = [e async for e in provider.stream(
        [{"role": "user", "content": "hi"}], [], logprobs=True)]
    assert len(requests_seen) == 2
    assert "stream_options" in requests_seen[0]
    assert "stream_options" not in requests_seen[1]
    assert "logprobs" not in requests_seen[1]
    assert any(e.type == "note" for e in events)
    assert "".join(e.data["text"] for e in events if e.type == "delta") == "hi"


async def test_hf_provider_sends_enable_thinking_flag():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, text="data: [DONE]\n\n")

    s = Settings(provider="huggingface", hf_base_url=SUMOPOD,
                 hf_api_key="random_token", hf_model="qwen3-4b-q4_k_m",
                 thinking=True)
    provider = HuggingFaceProvider(s)
    provider.transport = httpx.MockTransport(handler)
    assert provider.base_url == "https://ai.sumopod.com/v1"
    assert provider.extra_body == {"chat_template_kwargs":
                                   {"enable_thinking": True}}
    [e async for e in provider.stream([{"role": "user", "content": "x"}], [])]
    assert seen["chat_template_kwargs"] == {"enable_thinking": True}

    s.thinking = False
    provider = HuggingFaceProvider(s)
    provider.transport = httpx.MockTransport(handler)
    [e async for e in provider.stream([{"role": "user", "content": "x"}], [])]
    assert seen["chat_template_kwargs"] == {"enable_thinking": False}


def test_update_settings_canonicalises_pasted_base_urls():
    out = update_settings(openai_base_url=SUMOPOD, hf_base_url=SUMOPOD)
    assert out["openai_base_url"] == "https://ai.sumopod.com/v1"
    assert out["hf_base_url"] == "https://ai.sumopod.com/v1"
    # restore defaults so other tests are unaffected
    update_settings(openai_base_url="https://api.openai.com/v1",
                    hf_base_url="http://127.0.0.1:8081/v1")
