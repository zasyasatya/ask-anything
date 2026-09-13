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


def test_chat_diagram_answer_embeds_mermaid_fence(client):
    """Jawaban final mock memuat fence ```mermaid supaya UI (DiagramBlock)
    punya sumber untuk mode Graph interaktif / Mermaid."""
    evs = _events(client, "buatkan diagram alur proses pemesanan")
    done = next(e for e in evs if e["type"] == "agent_done")
    assert "```mermaid" in done["answer"]
    assert "flowchart" in done["answer"]
