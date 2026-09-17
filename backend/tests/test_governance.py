"""Tests: pipeline governance (policy) — store, gate, dan enforcement."""
import pytest

from app import governance


@pytest.fixture()
def clean_policy(client):
    """Hapus semua override policy supaya tiap tes mulai dari default."""
    from app import db
    db.execute("DELETE FROM admin_policy")
    yield
    db.execute("DELETE FROM admin_policy")


def test_default_policy_complete(clean_policy):
    pol = governance.policy()
    for mode in ("text", "image", "diagram", "ppt", "rag", "research"):
        assert pol["modes"][mode] is True
    for tool in ("web_search", "fetch_url", "create_diagram", "calculator",
                 "generate_image", "generate_ppt", "save_memory"):
        assert tool in pol["tools"]
    assert pol["interpreter"]["always_on"] is True


def test_update_policy_partial_merge(clean_policy):
    out = governance.update_policy({"modes": {"image": False},
                                    "tools": {"generate_ppt": False}})
    assert out["modes"]["image"] is False
    assert out["modes"]["text"] is True          # section lain tak tersentuh
    assert out["tools"]["generate_ppt"] is False
    assert out["tools"]["web_search"] is True


def test_interpreter_cannot_be_disabled(clean_policy):
    out = governance.update_policy(
        {"interpreter": {"always_on": False, "record_logprobs": False}})
    assert out["interpreter"]["always_on"] is True   # dikunci
    assert out["interpreter"]["record_logprobs"] is False


def test_unknown_keys_ignored(clean_policy):
    before = governance.policy()
    out = governance.update_policy({"modes": {"haram": False},
                                    "nope": {"x": 1}})
    assert "haram" not in out["modes"]
    assert "nope" not in out
    assert out == before


def test_mode_and_tool_gates(clean_policy):
    assert governance.mode_allowed("text")
    governance.update_policy({"modes": {"rag": False}})
    assert not governance.mode_allowed("rag")
    governance.update_policy({"tools": {"web_search": False}})
    assert not governance.tool_allowed("web_search")
    assert governance.tool_allowed("calculator")


def test_public_policy_shape(clean_policy):
    pub = governance.public_policy()
    assert set(pub["modes"]) == {"text", "image", "diagram", "ppt",
                                 "rag", "research"}
    assert "admin_token" not in pub
    assert "top_k" in pub["rag"]


def test_chat_blocked_mode_streams_error(client, clean_policy):
    governance.update_policy({"modes": {"text": False, "ppt": False}})
    with client.stream("POST", "/api/chat",
                       json={"message": "halo", "mode": "ppt"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        body = "".join(r.iter_lines())
    assert "dimatikan" in body
    governance.update_policy({"modes": {"text": True}})


def test_blocked_tool_never_executes(client, clean_policy):
    """Model nyata bisa meng-hallusinate tool yang tidak diiklankan: gate di
    agent loop menolak mengeksekusinya, merecord event `policy`, dan model
    menerima pesan error — bukan hasil tool."""
    import json as _json
    from app import db
    from app.providers import BaseProvider
    from app.providers.base import StreamEvent

    governance.update_policy({"tools": {"create_diagram": False}})

    class StubbornProvider(BaseProvider):
        name = "stubborn"

        def model_label(self):
            return "stubborn-fake"

        async def stream(self, messages, tools, **kwargs):
            names = {t["function"]["name"] for t in tools or []}
            if "create_diagram" in self._called:
                yield StreamEvent("delta", {"text": "baik, lanjut tanpa tool."})
                yield StreamEvent("done", {"finish_reason": "stop"})
                return
            self._called.add("create_diagram")
            yield StreamEvent("thinking", {"text": "coba panggil tool blokir"})
            yield StreamEvent("tool_calls", {"calls": [{
                "id": "call_blocked", "name": "create_diagram",
                "arguments": {"kind": "flowchart", "title": "x",
                              "nodes": [], "edges": []}}]})
            yield StreamEvent("done", {"finish_reason": "tool_calls"})

    StubbornProvider._called = set()

    from app.agent.loop import run_agent
    from app.config import settings

    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    conv = db.new_conversation("gate-test")
    result = asyncio_run(run_agent(
        conversation_id=conv["id"], user_message="buat diagram",
        history=[], provider=StubbornProvider(), settings=settings, emit=emit))

    types = [e["type"] for e in events]
    assert "policy" in types                    # penolakan terecord
    pol_ev = next(e for e in events if e["type"] == "policy")
    assert pol_ev["tool"] == "create_diagram"
    tr = next(e for e in events if e["type"] == "tool_result"
              and e.get("name") == "create_diagram")
    assert tr["ok"] is False and "diblokir" in tr["summary"]
    assert not (tr.get("data") or {}).get("mermaid")   # tidak dieksekusi
    assert result["error"] is None
    # tool tidak diiklankan ke model saat run berjalan
    prompt_ev = next(e for e in events if e["type"] == "prompt")
    assert "create_diagram" not in {t["function"]["name"]
                                    for t in prompt_ev["tools"]}
    db.delete_conversation(conv["id"])
    governance.update_policy({"tools": {"create_diagram": True}})


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
