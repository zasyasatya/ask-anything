"""Argument repair: tool calls from real models are rarely clean JSON.

These tests pin the shapes seen in practice (fenced JSON, single quotes,
trailing commas, a nested array sent as a JSON *string*, truncated output) and
the promise that a tool never receives silently-empty arguments.
"""
import json

import httpx
import pytest

from app.config import Settings
from app.providers.openai_provider import OpenAIProtocolProvider
from app.tools import get_tool
from app.tools.args import as_int, as_list, parse_loose, repair_arguments
from app.tools.base import ToolContext


def test_plain_json_object_passes_through():
    raw = '{"query": "berita", "max_results": 3}'
    assert repair_arguments(raw) == {"query": "berita", "max_results": 3}


def test_fenced_and_prose_wrapped_json():
    raw = 'Tentu, ini argumennya:\n```json\n{"query": "harga emas"}\n```'
    assert repair_arguments(raw)["query"] == "harga emas"


@pytest.mark.parametrize("raw", [
    "{'query': 'kabar', 'max_results': 2}",               # single quotes
    '{"query": "kabar", "max_results": 2,}',              # trailing comma
    '{"query": "kabar", "max_results": 2, "fresh": True}',  # python literal
    '{"query": "kabar", "max_results": 2}\n\nSemoga membantu!',
])
def test_almost_json_is_repaired(raw):
    args = repair_arguments(raw)
    assert args["query"] == "kabar"
    assert args["max_results"] == 2


def test_nested_json_string_becomes_structure():
    raw = json.dumps({"nodes": '[{"id": "a", "label": "Mulai"}]',
                      "edges": '[{"from": "a", "to": "b"}]'})
    args = repair_arguments(raw)
    assert isinstance(args["nodes"], list)
    assert args["nodes"][0]["label"] == "Mulai"
    assert args["edges"][0]["to"] == "b"


def test_unparseable_keeps_raw_instead_of_dropping_it():
    args = repair_arguments("{'kind': 'flowchart'")
    assert "_raw" in args and "kind" in args["_raw"]


def test_helpers_are_tolerant():
    assert as_int("max 7 hasil", 5) == 7
    assert as_int(None, 5) == 5
    assert as_list('{"id": "a"}') == [{"id": "a"}]
    assert as_list(None) == []
    assert parse_loose("bukan json") is None


async def test_create_diagram_accepts_json_string_arguments():
    """Model yang mengirim nodes/edges sebagai string tetap dapat diagram."""
    res = await get_tool("create_diagram").run(
        {
            "kind": "flowchart",
            "title": "Alur",
            "nodes": '[{"id": "a", "label": "Mulai"}, {"id": "b", "label": "Selesai"}]',
            "edges": '[{"from": "a", "to": "b", "label": "oke"}]',
        },
        ToolContext(settings=Settings()),
    )
    assert res.ok is True
    assert 'a["Mulai"]' in res.data["mermaid"]
    assert "a -->|oke| b" in res.data["mermaid"]


async def test_create_diagram_accepts_aliases_and_string_edges():
    res = await get_tool("create_diagram").run(
        {
            "type": "alur",
            "title": "Alias",
            "nodes": {"a": "Mulai", "b": "Proses"},
            "edges": ["a -> b", "b --> c: lanjut"],
        },
        ToolContext(settings=Settings()),
    )
    assert res.ok is True
    mermaid = res.data["mermaid"]
    assert 'a["Mulai"]' in mermaid and 'b["Proses"]' in mermaid
    assert "a --> b" in mermaid
    assert "b -->|lanjut| c" in mermaid
    # endpoint `c` tidak dideklarasikan → dibuat otomatis, edge tidak hilang
    assert 'c["c"]' in mermaid
    assert any("dibuat otomatis" in w for w in res.data["warnings"])


async def test_create_diagram_accepts_wrapped_and_pair_edges():
    res = await get_tool("create_diagram").run(
        {
            "kind": "flowchart",
            "title": "Wrapped",
            "nodes": {"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
            "edges": {"links": [["a", "b", "oke"]]},
        },
        ToolContext(settings=Settings()),
    )
    assert res.ok is True
    assert "a -->|oke| b" in res.data["mermaid"]
    assert res.data["warnings"] == []


async def test_create_diagram_accepts_raw_mermaid_source():
    res = await get_tool("create_diagram").run(
        {
            "kind": "flowchart",
            "title": "Dari model",
            "mermaid": "```mermaid\nflowchart LR\n  x[Mulai] --> y[Selesai]\n```",
        },
        ToolContext(settings=Settings()),
    )
    assert res.ok is True
    assert res.data["mermaid"] == "flowchart LR\n  x[Mulai] --> y[Selesai]"
    assert res.data["source"] == "model"


async def test_create_diagram_reports_when_nothing_can_be_read():
    res = await get_tool("create_diagram").run(
        {"kind": "flowchart", "title": "X", "_raw": "{'kind': 'flowchart'"},
        ToolContext(settings=Settings()),
    )
    assert res.ok is False
    assert "tidak ada node yang terbaca" in res.summary
    assert res.data.get("hint")


async def test_create_diagram_direction_override():
    res = await get_tool("create_diagram").run(
        {
            "kind": "flowchart",
            "title": "LR",
            "direction": "LR",
            "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}],
        },
        ToolContext(settings=Settings()),
    )
    assert res.data["mermaid"].startswith("flowchart LR")


# --------------------------------------------------------------- provider side
async def test_openai_provider_repairs_streamed_tool_arguments():
    """Argumen rusak tidak boleh sampai ke tool sebagai {"_raw": ...} kosong."""
    sse = "\n".join([
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
        '"function":{"name":"create_diagram","arguments":"{\'kind\': \'flowchart\', "}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"\'nodes\': [{\'id\': \'a\', \'label\': \'Mulai\'}]}"}}]}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
        "",
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sse,
                              headers={"content-type": "text/event-stream"})

    provider = OpenAIProtocolProvider("https://gw.test/v1", "k", "m",
                                      transport=httpx.MockTransport(handler))
    events = [ev async for ev in provider.stream([], [], logprobs=False)]
    calls = next(ev.data["calls"] for ev in events if ev.type == "tool_calls")
    assert calls[0]["name"] == "create_diagram"
    assert calls[0]["arguments"]["kind"] == "flowchart"
    assert calls[0]["arguments"]["nodes"][0]["label"] == "Mulai"


async def test_web_search_falls_back_to_second_endpoint():
    """Endpoint pertama kosong/diblokir → endpoint kedua yang menjawab dipakai."""
    from app.tools.base import ToolResult  # noqa: F401 - dokumentasi tipe

    html = ('<html><body><div class="result">'
            '<a class="result__a" href="https://real.test/halaman">Judul Asli</a>'
            '<span class="result__snippet">Cuplikan asli</span>'
            '</div></body></html>')

    def handler(request: httpx.Request) -> httpx.Response:
        if "lite.duckduckgo.com" in str(request.url):
            return httpx.Response(200, text="<html><body>kosong</body></html>")
        return httpx.Response(200, text=html)

    ctx = ToolContext(settings=Settings(),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "apa saja"}, ctx)
    assert res.ok is True
    assert res.hits == 1
    assert res.data["results"][0]["url"] == "https://real.test/halaman"
    assert "html.duckduckgo.com" in str(res.data["endpoint"])


async def test_web_search_unwraps_duckduckgo_redirect():
    """Sitasi harus menunjuk halaman aslinya, bukan tautan pelacak DDG."""
    html = ('<html><body><div class="result">'
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fasli.test%2Fp">'
            'Judul</a></div></body></html>')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    ctx = ToolContext(settings=Settings(),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "q"}, ctx)
    assert res.data["results"][0]["url"] == "https://asli.test/p"


async def test_web_search_block_page_is_reported_as_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>Detected unusual traffic "
                                        "from your network. Please solve CAPTCHA"
                                        "</body></html>")

    ctx = ToolContext(settings=Settings(),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "q"}, ctx)
    assert res.ok is False and res.hits == 0
    assert res.data["blocked"] is True
    assert "anti-bot" in res.summary or "gagal" in res.summary


async def test_web_search_missing_query_is_reported():
    ctx = ToolContext(settings=Settings(), http=None)
    res = await get_tool("web_search").run({}, ctx)
    assert res.ok is False
    assert "query" in res.summary
