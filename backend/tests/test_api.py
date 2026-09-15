import json


def _events(client, message, conv=None):
    payload = {"message": message}
    if conv:
        payload["conversation_id"] = conv
    with client.stream("POST", "/api/chat", json=payload) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        evs = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                evs.append(json.loads(line[6:]))
        return evs


def test_root_and_health(client):
    assert client.get("/").json()["name"] == "Ask Anything"
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["provider"] == "mock"


def test_settings_roundtrip(client):
    s = client.get("/api/settings").json()
    assert s["provider"] == "mock"
    r = client.post("/api/settings", json={"temperature": 0.3})
    assert r.json()["temperature"] == 0.3


def test_chat_diagram_flow(client):
    evs = _events(client, "buatkan diagram alur proses pemesanan")
    types = [e["type"] for e in evs]
    assert types[0] == "start"
    for expected in ("meta", "thinking", "tool_call", "tool_result", "delta",
                     "done", "agent_done"):
        assert expected in types, f"missing {expected} in {types}"
    tc = next(e for e in evs if e["type"] == "tool_call")
    assert tc["name"] == "create_diagram"
    tr = next(e for e in evs if e["type"] == "tool_result")
    assert "mermaid" in tr["data"]
    assert "flowchart" in tr["data"]["mermaid"]

    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    roles = [m["role"] for m in conv["messages"]]
    assert "user" in roles and "assistant" in roles and "tool" in roles
    trace_types = {t["type"] for t in conv["trace"]}
    assert {"prompt", "tool_call", "logprobs"} <= trace_types

    listed = client.get("/api/conversations").json()["conversations"]
    assert any(c["id"] == cid for c in listed)


def test_chat_search_flow_with_stubbed_tool(client, monkeypatch):
    from app.tools import get_tool

    async def fake_run(args, ctx):
        from app.tools.base import ToolResult

        return ToolResult(
            summary="web_search stub: 1 hasil",
            data={"results": [{"title": "Stub", "url": "https://x.test",
                               "snippet": "ok"}]},
        )

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)
    evs = _events(client, "cari berita AI terbaru hari ini")
    types = [e["type"] for e in evs]
    assert "tool_call" in types and "agent_done" in types
    tc = next(e for e in evs if e["type"] == "tool_call")
    assert tc["name"] == "web_search"


def test_delete_conversation(client):
    evs = _events(client, "halo")
    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    assert client.delete(f"/api/conversations/{cid}").json()["ok"] is True
    assert client.get(f"/api/conversations/{cid}").json()["error"] == "not found"


def test_chat_diagram_run_persists_renderable_diagram_artifact(client):
    """Diagram dari create_diagram harus bisa dirender tanpa disalin model.

    UI merender kartu diagram dari payload tool (`meta.diagrams` / event
    `agent_done`), jadi diagram tetap ada walau jawaban tidak memuat fence.
    """
    evs = _events(client, "buatkan diagram alur proses pemesanan")
    done = next(e for e in evs if e["type"] == "agent_done")
    assert done["diagrams"], "agent_done tidak membawa artefak diagram"
    art = done["diagrams"][0]
    assert art["tool"] == "create_diagram"
    assert art["title"] and "flowchart" in art["mermaid"]

    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    assistant = [m for m in conv["messages"] if m["role"] == "assistant"][-1]
    saved = assistant["meta"]["diagrams"]
    assert saved and saved[0]["mermaid"] == art["mermaid"]
    assert assistant["meta"]["diagram_origin"]["tool"] == "create_diagram"


class _NoFenceProvider:
    """Model sungguhan sering berhenti di "sudah saya buatkan" tanpa menyalin
    sumber Mermaid ke jawabannya. Diagram di UI tidak boleh bergantung pada itu.
    """

    name = "stub"

    def model_label(self) -> str:
        return "stub-model"

    async def stream(self, messages, tools, temperature=0.7, max_tokens=2048,
                     logprobs=False, top_logprobs=4):
        from app.providers.base import StreamEvent

        if not any(m.get("role") == "tool" for m in messages):
            yield StreamEvent("tool_calls", {"calls": [{
                "id": "c1", "name": "create_diagram",
                "arguments": {
                    "kind": "flowchart", "title": "Alur Pemesanan",
                    "nodes": [{"id": "a", "label": "Pesan"},
                              {"id": "b", "label": "Bayar"}],
                    "edges": [{"from": "a", "to": "b", "label": "lanjut"}],
                },
            }]})
            yield StreamEvent("done", {"finish_reason": "tool_calls"})
            return
        yield StreamEvent("delta", {"text": "Diagramnya sudah saya buatkan."})
        yield StreamEvent("done", {"finish_reason": "stop"})


def test_diagram_survives_model_that_never_copies_the_mermaid(client, monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes, "build_provider", lambda settings: _NoFenceProvider())
    evs = _events(client, "buatkan diagram alur proses pemesanan")
    done = next(e for e in evs if e["type"] == "agent_done")
    assert "```mermaid" not in done["answer"]          # model tidak menyalin
    assert done["diagrams"], "artefak diagram hilang"
    assert 'a["Pesan"]' in done["diagrams"][0]["mermaid"]
    assert "a -->|lanjut| b" in done["diagrams"][0]["mermaid"]
    assert done["diagrams"][0]["warnings"] == []

    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    assistant = [m for m in conv["messages"] if m["role"] == "assistant"][-1]
    assert assistant["meta"]["diagrams"][0]["title"] == "Alur Pemesanan"


def test_chat_search_run_exposes_citable_sources(client, monkeypatch):
    """Sumber bernomor + laporan sitasi tersedia live dan di riwayat."""
    from app.tools import get_tool

    async def fake_run(args, ctx):
        from app.tools.base import ToolResult

        return ToolResult(
            summary="web_search stub: 1 hasil",
            data={"results": [{"title": "Stub Sumber", "url": "https://x.test/a",
                               "snippet": "isi"}]},
            hits=1,
        )

    monkeypatch.setattr(get_tool("web_search"), "run", fake_run)
    evs = _events(client, "cari berita AI terbaru hari ini")
    sources_ev = next(e for e in evs if e["type"] == "sources")
    assert sources_ev["items"][0]["url"] == "https://x.test/a"
    assert sources_ev["items"][0]["index"] == 1

    done = next(e for e in evs if e["type"] == "agent_done")
    assert done["sources"][0]["url"] == "https://x.test/a"
    assert done["citations"]["total"] == 1
    assert done["citations"]["status"] in ("cited", "appended")

    cid = next(e for e in evs if e["type"] == "start")["conversation_id"]
    conv = client.get(f"/api/conversations/{cid}").json()
    assistant = [m for m in conv["messages"] if m["role"] == "assistant"][-1]
    assert assistant["meta"]["sources"][0]["index"] == 1
    assert assistant["meta"]["citations"]["total"] == 1


def test_chat_diagram_answer_embeds_mermaid_fence(client):
    """Jawaban final mock memuat fence ```mermaid supaya UI (DiagramBlock)
    punya sumber untuk mode Graph interaktif / Mermaid."""
    evs = _events(client, "buatkan diagram alur proses pemesanan")
    done = next(e for e in evs if e["type"] == "agent_done")
    assert "```mermaid" in done["answer"]
    assert "flowchart" in done["answer"]
