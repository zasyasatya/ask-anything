"""Provenance (browser vs diagram tool) and citation enforcement.

These tests pin the two guarantees the UI relies on:
  * every browser tool result becomes a numbered, citable source — and a
    diagram result never does;
  * an answer that used web evidence always ends up verifiable, and an answer
    with no browser data is labelled as such instead of faking citations.
"""
import json

from app.sources import SourceRegistry, finalize_answer
from app.tools import get_tool, tool_source
from app.tools.base import SOURCE_LABELS


# --------------------------------------------------------------------- registry
def test_registry_numbers_urls_and_dedupes():
    r = SourceRegistry()
    r.add("https://a.test/x", title="X", tool="web_search", snippet="s")
    r.add("https://b.test/y", title="Y", tool="web_search")
    again = r.add("https://a.test/x", title="X updated", tool="fetch_url",
                  read=True)
    assert [s.index for s in r.items] == [1, 2]
    assert again.index == 1 and again.read is True
    assert again.title == "X updated"          # richer title wins
    assert "https://a.test/x" in r.as_marked_list()
    assert r.as_marked_list().startswith("[1] ")


def test_register_tool_result_ignores_non_browser_payloads():
    r = SourceRegistry()
    added = r.register_tool_result(
        "web_search", {"query": "q"},
        {"query": "q", "results": [
            {"title": "A", "url": "https://a.test/1", "snippet": "sa"},
            {"title": "B", "url": "https://b.test/2", "snippet": "sb"},
        ]},
    )
    assert added == 2
    # A diagram payload must never become a "source".
    assert r.register_tool_result(
        "create_diagram", {}, {"mermaid": "flowchart TD\n A-->B"}) == 0
    # fetch_url marks its payload as read.
    assert r.register_tool_result("fetch_url", {"url": "https://b.test/2"},
                                  {"url": "https://b.test/2",
                                   "title": "B full"}) == 0
    assert r.items[1].read is True
    assert r.items[1].tool == "web_search"     # origin of the number is kept
    # failed browser call yields nothing
    assert r.register_tool_result("web_search", {}, {"error": "boom",
                                                      "results": []}) == 0


def test_empty_browser_result_prompt_forbids_fabricated_citations():
    r = SourceRegistry()
    block = r.prompt_block()
    assert "no usable web evidence" in block
    assert "Do NOT" in block


# ------------------------------------------------------------------- citations
def test_report_cited_uncited_and_out_of_range():
    r = SourceRegistry()
    for i in range(3):
        r.add(f"https://s.test/{i}", title=f"S{i}", tool="web_search")
    rep = r.report("Klaim A [1]. Klaim B [2]. Klaim liar [9].")
    assert rep["cited"] == [1, 2]
    assert rep["uncited"] == [3]
    assert rep["invalid"] == [9]
    assert rep["status"] == "cited"


def test_finalize_appends_source_block_when_model_cites_nothing():
    r = SourceRegistry()
    r.add("https://only.test/page", title="Only", tool="fetch_url", read=True)
    answer, rep = finalize_answer("Jawaban tanpa marker sama sekali.", r)
    assert rep["status"] == "appended"
    assert "## Sumber" in answer
    assert "1. [Only](https://only.test/page)" in answer


def test_finalize_with_no_evidence_is_labelled_not_faked():
    r = SourceRegistry()
    answer, rep = finalize_answer("Hanya pengetahuan model.", r)
    assert rep["status"] == "no-evidence"
    assert rep["total"] == 0
    assert "Sumber" not in answer          # nothing to list → nothing injected


def test_finalize_keeps_model_markers_intact():
    r = SourceRegistry()
    r.add("https://x.test/1", title="Satu", tool="web_search")
    r.add("https://x.test/2", title="Dua", tool="web_search")
    answer, rep = finalize_answer("Fakta satu [1] dan fakta dua [2].", r)
    assert answer.startswith("Fakta satu [1] dan fakta dua [2].")
    assert rep["cited"] == [1, 2] and rep["uncited"] == []
    assert "## Sumber" not in answer


# ------------------------------------------------------------------ provenance
def test_tool_source_classes_are_declared():
    assert tool_source("web_search") == "browser"
    assert tool_source("fetch_url") == "browser"
    assert tool_source("create_diagram") == "diagram"
    assert tool_source("calculator") == "compute"
    # unknown tool must not masquerade as web evidence
    assert tool_source("made_up_tool") == "compute"
    assert SOURCE_LABELS["diagram"] == "Tool diagram"


async def test_calculator_and_diagram_report_no_hits():
    """hits=None means "not a browser result" — distinct from hits=0."""
    from app.tools.base import ToolContext
    from app.config import Settings

    ctx = ToolContext(settings=Settings())
    dia = await get_tool("create_diagram").run(
        {"kind": "flowchart", "title": "T",
         "nodes": [{"id": "a", "label": "A"}], "edges": []}, ctx)
    assert dia.ok is True and dia.hits is None

    calc = await get_tool("calculator").run({"expression": "1+1"}, ctx)
    assert calc.hits is None


async def test_web_search_zero_results_is_explicitly_empty():
    """The UI shows "belum ada hasil" — it needs ok=True with hits=0."""
    import httpx

    from app.config import Settings
    from app.tools.base import ToolContext

    def handler(request):
        return httpx.Response(200, text="<html><body>kosong</body></html>")

    ctx = ToolContext(settings=Settings(),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "tiada hasil"}, ctx)
    assert res.hits == 0 and res.ok is True
    assert "tidak ada hasil" in res.summary


async def test_web_search_network_error_is_not_ok():
    import httpx

    from app.config import Settings
    from app.tools.base import ToolContext

    def handler(request):
        raise httpx.ConnectError("blocked")

    ctx = ToolContext(settings=Settings(),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "q"}, ctx)
    assert res.ok is False and res.hits == 0
    assert "error" in res.data


# ----------------------------------------------------------- traced through API
def _events(client, message):
    with client.stream("POST", "/api/chat", json={"message": message}) as r:
        return [json.loads(line[6:]) for line in r.iter_lines()
                if line.startswith("data: ")]


def test_diagram_run_tags_provenance_and_no_sources(client):
    evs = _events(client, "buatkan diagram alir pendaftaran")
    calls = [e for e in evs if e["type"] == "tool_call"]
    assert calls and calls[0]["source"] == "diagram"
    results = [e for e in evs if e["type"] == "tool_result"]
    assert results[0]["source"] == "diagram"
    assert results[0]["ok"] is True
    assert results[0]["hits"] is None
    assert results[0]["duration_ms"] >= 0

    cit = next(e for e in evs if e["type"] == "citations")
    assert cit["status"] == "no-evidence" and cit["total"] == 0

    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    meta = conv["messages"][-1]["meta"]
    assert meta["diagram_origin"]["tool"] == "create_diagram"
    assert meta["citations"]["status"] == "no-evidence"


def test_empty_browser_run_records_note_and_zero_hits(client):
    """Browser yielded nothing → explicit note, hits=0, no fabricated sources."""
    evs = _events(client, "cari berita teknologi terkini")
    result = next(e for e in evs if e["type"] == "tool_result")
    assert result["source"] == "browser"
    assert result["hits"] == 0
    notes = [e for e in evs if e["type"] == "note"
             and e.get("status") == "no-results"]
    assert notes, "expected an explicit 'no results' note in the trace"

    cit = next(e for e in evs if e["type"] == "citations")
    assert cit["status"] == "no-evidence"


def test_browser_run_with_results_creates_citable_sources(client, monkeypatch):
    from app.tools import get_tool

    async def fake_run(args, ctx):
        from app.tools.base import ToolResult
        return ToolResult(
            summary="web_search 'q': 2 hasil",
            data={"query": "q", "results": [
                {"title": "Sumber Satu", "url": "https://satu.test/a",
                 "snippet": "ringkasan satu"},
                {"title": "Sumber Dua", "url": "https://dua.test/b",
                 "snippet": "ringkasan dua"},
            ]},
            hits=2,
        )

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)
    evs = _events(client, "cari berita teknologi terkini")

    src_ev = next(e for e in evs if e["type"] == "sources")
    assert src_ev["total"] == 2
    assert src_ev["items"][0]["origin"] == "browser"
    assert src_ev["items"][0]["index"] == 1

    cit = next(e for e in evs if e["type"] == "citations")
    # Mock answer cites [1] when real hits exist → status "cited".
    assert cit["status"] == "cited"
    assert 1 in cit["cited"]

    done = next(e for e in evs if e["type"] == "done")
    assert "[1]" in done["answer"]


def test_llm_request_and_response_events_disclose_the_blackbox(client):
    evs = _events(client, "cari berita teknologi terkini")
    reqs = [e for e in evs if e["type"] == "llm_request"]
    resps = [e for e in evs if e["type"] == "llm_response"]
    assert len(reqs) == len(resps) >= 2      # tool turn + final answer turn
    assert resps[0]["tool_calls"][0]["name"] == "web_search"
    assert resps[0]["duration_ms"] >= 0
    assert resps[1]["text"]                  # raw completion of the final turn
    assert resps[0]["finish_reason"] == "tool_calls"
    # every traced event carries a run-relative timestamp for the log view
    # (only the route-level `start`/`agent_done` envelopes are not traced)
    traced = [e for e in evs if e["type"] not in ("start", "agent_done")]
    assert traced
    assert all(e["t_ms"] >= 0 for e in traced)


def test_trace_is_replayable_from_sqlite(client):
    evs = _events(client, "cari berita teknologi terkini")
    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    trace = client.get(f"/api/conversations/{cid}").json()["trace"]
    live = [e["type"] for e in evs if e["type"] not in ("start", "agent_done")]
    assert [t["type"] for t in trace] == live
    assert all("t_ms" in t and "step" in t for t in trace)


async def test_search_endpoint_is_configurable():
    """ASK_SEARCH_DDG_URL mengarahkan web_search ke gateway lain.

    Ini bukan hanya untuk demo: gateway pencarian internal/self-host dipakai
    sungguhan, dan endpoint yang sama memungkinkan uji E2E UI tanpa internet.
    """
    import httpx

    from app.config import Settings
    from app.tools import get_tool
    from app.tools.base import ToolContext

    seen: list[str] = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(
            200,
            text='<html><table><tr><td><a href="https://internal.test/x">'
                 "Hasil Internal</a></td></tr>"
                 "<tr><td>ringkasan internal</td></tr></table></html>",
        )

    cfg = Settings(search_ddg_url="http://127.0.0.1:9/lite/")
    ctx = ToolContext(settings=cfg, http=httpx.AsyncClient(
        transport=httpx.MockTransport(handler)))
    res = await get_tool("web_search").run({"query": "q"}, ctx)
    assert seen and seen[0].startswith("http://127.0.0.1:9/lite/?q=q")
    assert res.data["results"][0]["url"] == "https://internal.test/x"
    assert res.hits == 1


def test_tool_outcome_persisted_for_history(client, monkeypatch):
    """Riwayat harus se-informatif live: hasil tool ikut disimpan di meta.

    Tool di-stub supaya deterministik (lingkungan uji tidak punya internet) —
    dua keadaan diuji: 0 hasil dan kegagalan.
    """
    from app.tools import get_tool
    from app.tools.base import ToolResult

    async def fake_run(args, ctx):
        return ToolResult(summary="web_search: tidak ada hasil untuk 'q'",
                          data={"results": []}, ok=True, hits=0)

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)

    evs = _events(client, "cari berita teknologi terkini")
    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    tool = next(m for m in msgs if m["role"] == "tool")
    meta = tool["meta"]
    assert meta["name"] == "web_search"
    assert meta["source"] == "browser"
    assert meta["ok"] is True
    assert meta["hits"] == 0            # nol pun tersimpan, bukan hilang
    assert meta["summary"].startswith("web_search")
    assert isinstance(meta["duration_ms"], (int, float))
    # pasangan call-nya ada di pesan assistant_toolcalls sebelumnya
    tc = next(m for m in msgs if m["role"] == "assistant_toolcalls")
    assert tc["meta"]["tool_calls"][0]["id"] == meta["tool_call_id"]


def test_failed_tool_outcome_persisted(client, monkeypatch):
    """Kegagalan tool ikut tersimpan — replay tidak boleh tampak sukses."""
    from app.tools import get_tool
    from app.tools.base import ToolResult

    async def boom(args, ctx):
        return ToolResult(summary="web_search gagal (network)",
                          data={"error": "connect error", "results": []},
                          ok=False, hits=0)

    monkeypatch.setattr(get_tool("web_search"), "run", boom)
    evs = _events(client, "cari berita teknologi terkini")
    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    meta = next(m for m in msgs if m["role"] == "tool")["meta"]
    assert meta["ok"] is False and meta["hits"] == 0
    result = next(e for e in evs if e["type"] == "tool_result")
    assert result["ok"] is False
