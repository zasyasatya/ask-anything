import httpx

from app.config import Settings
from app.tools import get_tool
from app.tools.base import ToolContext
from app.tools.calculator import safe_eval
from app.tools.diagrams import build_mermaid

SETTINGS = Settings()


def _ctx(transport=None):
    return ToolContext(
        settings=SETTINGS,
        http=httpx.AsyncClient(transport=transport) if transport else None,
    )


async def test_calculator():
    assert safe_eval("2+3*4") == 14
    assert safe_eval("(2+3)**2") == 25
    res = await get_tool("calculator").run({"expression": "10/4"}, _ctx())
    assert res.data["result"] == 2.5
    bad = await get_tool("calculator").run({"expression": "__import__('os')"},
                                           _ctx())
    assert "error" in bad.data


async def test_diagram_flowchart():
    mermaid, problems = build_mermaid(
        "flowchart", "t",
        [{"id": "a", "label": "Mulai"}, {"id": "b", "label": "Selesai [x]"}],
        [{"from": "a", "to": "b", "label": "oke"}],
    )
    assert problems == []
    assert mermaid.startswith("flowchart TD")
    assert 'a["Mulai"]' in mermaid
    assert "a -->|oke| b" in mermaid
    assert "[" not in mermaid.split('b["')[1].split('"]')[0]


async def test_diagram_unknown_edge_reported():
    mermaid, problems = build_mermaid(
        "graph", "t", [{"id": "a", "label": "A"}],
        [{"from": "a", "to": "zzz_missing", "label": ""}],
    )
    assert any("tidak dikenal" in p for p in problems)
    assert "a[" in mermaid


async def test_create_diagram_tool_end_to_end():
    res = await get_tool("create_diagram").run(
        {"kind": "graph", "title": "G", "nodes": [
            {"id": "x", "label": "X"}, {"id": "y", "label": "Y"}],
         "edges": [{"from": "x", "to": "y"}]},
        _ctx(),
    )
    assert "flowchart LR" in res.data["mermaid"]
    assert "x --> y" in res.data["mermaid"]  # edge tanpa label tetap valid


DDG_HTML = """
<html><body><table>
<tr><td><a rel="nofollow" href="https://example.com/a">Result One</a></td></tr>
<tr><td>Snippet one text</td></tr>
<tr><td><a rel="nofollow" href="https://example.com/b">Result Two</a></td></tr>
<tr><td>Snippet two text</td></tr>
<tr><td><a href="https://duckduckgo.com/x">internal</a></td></tr>
</table></body></html>
"""


async def test_web_search_ddg_parsing():
    def handler(request):
        assert "q=" in str(request.url) or "q" in request.url.params
        return httpx.Response(200, text=DDG_HTML)

    ctx = _ctx(httpx.MockTransport(handler))
    res = await get_tool("web_search").run({"query": "test", "max_results": 5},
                                           ctx)
    urls = [r["url"] for r in res.data["results"]]
    assert urls == ["https://example.com/a", "https://example.com/b"]
    assert res.data["results"][0]["title"] == "Result One"
    assert res.data["results"][0]["snippet"] == "Snippet one text"


async def test_fetch_url_extraction():
    html = ("<html><head><title>My Page</title></head><body>"
            "<script>var x=1;</script><p>Hello world content</p></body></html>")

    def handler(request):
        return httpx.Response(200, text=html)

    ctx = _ctx(httpx.MockTransport(handler))
    res = await get_tool("fetch_url").run({"url": "https://example.com/p"}, ctx)
    assert res.data["title"] == "My Page"
    assert "Hello world content" in res.data["text"]
    assert "var x=1" not in res.data["text"]

    bad = await get_tool("fetch_url").run({"url": "ftp://nope"}, ctx)
    assert "error" in bad.data
