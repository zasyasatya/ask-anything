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

# ---------------------------------------------------------------------------
# Policy per peran (admin | member) — halaman Admin → Pipeline
# ---------------------------------------------------------------------------

def test_default_role_policies(clean_policy):
    """Member = playground (teks/diagram/rag); admin = semua fitur."""
    assert governance.effective_modes("admin") == {
        "text": True, "image": True, "diagram": True, "ppt": True,
        "rag": True, "research": True}
    assert governance.effective_modes("member") == {
        "text": True, "image": False, "diagram": True, "ppt": False,
        "rag": True, "research": False}
    assert set(governance.allowed_tools("member")) == {
        "web_search", "fetch_url", "create_diagram", "calculator"}
    assert governance.role_allows("member", "allow_offline_models") is False
    assert governance.role_allows("member", "allow_provider_settings") is False
    assert governance.role_allows("admin", "allow_offline_models") is True
    assert governance.role_setting("member", "chat_provider") == "openai"
    assert governance.role_setting("member", "tasks_scope") == "assigned"


def test_global_gate_always_wins_over_role(clean_policy):
    governance.update_policy({"modes": {"rag": False}})
    assert governance.mode_allowed("rag", "admin") is False
    assert governance.mode_allowed("rag", "member") is False
    governance.update_policy({"tools": {"calculator": False}})
    assert governance.tool_allowed("calculator", "admin") is False
    assert governance.tool_allowed("calculator", "member") is False


def test_role_override_does_not_touch_other_role(clean_policy):
    governance.update_policy({"roles": {"member": {
        "modes": {"rag": False, "image": True},
        "tools": {"generate_image": True},
        "allow_offline_models": True,
        "chat_provider": "auto",
        "tasks_scope": "all"}}})
    assert governance.mode_allowed("rag", "member") is False
    assert governance.mode_allowed("image", "member") is True
    assert governance.tool_allowed("generate_image", "member") is True
    assert governance.role_allows("member", "allow_offline_models") is True
    assert governance.role_setting("member", "chat_provider") == "auto"
    assert governance.role_setting("member", "tasks_scope") == "all"
    # admin tidak ikut berubah
    assert governance.role_setting("admin", "tasks_scope") == "all"
    assert governance.mode_allowed("ppt", "admin") is True
    assert governance.role_allows("admin", "allow_offline_models") is True


def test_role_patch_rejects_unknown_values(clean_policy):
    governance.update_policy({"roles": {"member": {
        "chat_provider": "model-offline",     # bukan pilihan yang sah
        "tasks_scope": "semuanya",
        "is_superuser": True,                 # key asing
        "modes": {"mode-asing": True}}}})
    assert governance.role_setting("member", "chat_provider") == "openai"
    assert governance.role_setting("member", "tasks_scope") == "assigned"
    assert "is_superuser" not in governance.role_policy("member")
    assert "mode-asing" not in governance.role_policy("member")["modes"]


def test_public_policy_reflects_caller_role(clean_policy):
    member = governance.public_policy("member")
    admin = governance.public_policy("admin")
    assert member["role"] == "member"
    assert member["modes"]["image"] is False and admin["modes"]["image"] is True
    assert member["tools"]["generate_ppt"] is False
    assert member["roles"]["member"]["allow_offline_models"] is False
    assert "admin_token" not in member


def test_role_gate_blocks_agent_tool_for_member(clean_policy, monkeypatch):
    """Tool yang bukan hak member tidak diiklankan & ditolak walau dipanggil."""
    from app import db
    from app.agent.loop import run_agent
    from app.config import settings
    from app.providers.base import BaseProvider, StreamEvent

    class StubbornProvider(BaseProvider):
        name = "stubborn"
        _called = set()

        def model_label(self) -> str:
            return "stubborn-test"

        async def stream(self, messages, tools, **kwargs):
            if "generate_ppt" in self._called:
                yield StreamEvent("delta", {"text": "baik, tanpa tool."})
                yield StreamEvent("done", {"finish_reason": "stop"})
                return
            self._called.add("generate_ppt")
            yield StreamEvent("tool_calls", {"calls": [{
                "id": "call_ppt", "name": "generate_ppt",
                "arguments": {"title": "Deck", "slides": [{"title": "A"}]}}]})
            yield StreamEvent("done", {"finish_reason": "tool_calls"})

    events: list[dict] = []

    async def emit(ev):
        events.append(ev)

    conv = db.new_conversation("role-gate")
    result = asyncio_run(run_agent(
        conversation_id=conv["id"], user_message="buat ppt",
        history=[], provider=StubbornProvider(), settings=settings,
        emit=emit, role="member"))
    types = [e["type"] for e in events]
    assert "policy" in types
    tr = next(e for e in events if e["type"] == "tool_result"
              and e.get("name") == "generate_ppt")
    assert tr["ok"] is False
    prompt_ev = next(e for e in events if e["type"] == "prompt")
    assert "generate_ppt" not in {t["function"]["name"]
                                  for t in prompt_ev["tools"]}
    assert result["error"] is None
    db.delete_conversation(conv["id"])

