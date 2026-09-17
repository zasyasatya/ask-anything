"""Tests: memory management + feedback → guidance loop."""
import pytest

from app import feedback, memory


@pytest.fixture(autouse=True)
def _clean(client):
    from app import db
    db.execute("DELETE FROM memories")
    db.execute("DELETE FROM feedback")
    yield
    db.execute("DELETE FROM memories")
    db.execute("DELETE FROM feedback")


# --------------------------- memory ---------------------------------------

def test_memory_crud_and_prompt_block():
    m = memory.add_memory("global", "Selalu jawab ringkas dan santun",
                          key="tone", source="admin")
    assert m["enabled"] is True and m["scope"] == "global"

    block = memory.prompt_block({})
    assert "ringkas dan santun" in block

    # disabled → hilang dari blok prompt
    memory.update_memory(m["id"], {"enabled": False})
    assert "ringkas dan santun" not in memory.prompt_block({})

    # fitur memori dimatikan → blok kosong
    memory.update_memory(m["id"], {"enabled": True})
    assert memory.prompt_block({"enabled": False}) == ""

    assert memory.delete_memory(m["id"]) is True
    assert memory.get_memory(m["id"]) is None


def test_memory_add_rejects_empty():
    with pytest.raises(ValueError):
        memory.add_memory("global", "   ")


def test_save_memory_tool(client):
    import asyncio
    from app.config import settings
    from app.tools import ToolContext, get_tool

    tool = get_tool("save_memory")
    ctx = ToolContext(settings=settings)
    res = asyncio.run(tool.run({"content": "User pakai bahasa Indonesia",
                                "key": "bahasa"}, ctx))
    assert res.ok and res.data["memory"]["source"] == "ai"
    assert any("bahasa Indonesia" in m["content"]
               for m in memory.list_memories())


# --------------------------- feedback -------------------------------------

def test_feedback_crud_and_stats():
    fb = feedback.add_feedback("up", comment="bagus")
    assert fb["status"] == "new"
    with pytest.raises(ValueError):
        feedback.add_feedback("meh")
    feedback.set_status(fb["id"], "reviewed")
    assert feedback.get_feedback(fb["id"])["status"] == "reviewed"
    stats = feedback.stats()
    assert stats["total"] >= 1 and stats["up"] >= 1
    assert feedback.delete_feedback(fb["id"])


def test_feedback_apply_creates_guidance_memory():
    fb = feedback.add_feedback("down", comment="Jangan terlalu panjang")
    out = feedback.apply_feedback(fb["id"])
    assert out["memory"]["source"] == "feedback"
    assert "Jangan terlalu panjang" in out["memory"]["content"]
    # idempotent: apply kedua tidak menduplikasi memori
    out2 = feedback.apply_feedback(fb["id"])
    assert out2["memory"]["id"] == out["memory"]["id"]
    # dan masuk ke blok pedoman prompt
    block = feedback.guidance_block()
    assert "Jangan terlalu panjang" in block


def test_auto_guidance_for_down_with_comment():
    pol = {"auto_guidance": True}
    fb = feedback.add_feedback("down", comment="Hindari bullet terlalu dalam")
    applied = feedback.maybe_auto_apply(fb["id"], pol)
    assert applied and applied["feedback"]["status"] == "applied"
    # tanpa komentar → tidak auto-apply
    fb2 = feedback.add_feedback("down")
    assert feedback.maybe_auto_apply(fb2["id"], pol) is None
    # policy mati → tidak auto-apply
    fb3 = feedback.add_feedback("down", comment="x")
    assert feedback.maybe_auto_apply(fb3["id"], {"auto_guidance": False}) is None


def test_chat_then_feedback_records_context(client):
    """Feedback terhubung ke jawaban: cuplikan + mode ikut terecord."""
    import json as _json
    with client.stream("POST", "/api/chat",
                       json={"message": "siapa kamu", "mode": "text"}) as r:
        mid = None
        cid = None
        for line in r.iter_lines():
            if line.startswith("data: "):
                ev = _json.loads(line[6:])
                if ev["type"] == "start":
                    cid = ev["conversation_id"]
                if ev["type"] == "agent_done":
                    mid = ev.get("message_id")
    assert cid and mid
    res = client.post("/api/feedback", json={
        "rating": "down", "conversation_id": cid, "message_id": mid,
        "comment": "Terlalu bertele-tele"})
    assert res.status_code == 200
    body = res.json()
    ctx = body["feedback"]["context"]
    assert ctx["answer_snippet"]          # cuplikan jawaban terecord
    assert ctx["mode"] == "text"
    assert body["auto_guidance"] is True  # 👎 + komentar → pedoman otomatis
    assert "bertele-tele" in body["guidance"]["content"]


def test_memory_and_feedback_reach_next_prompt(client):
    """Memori + pedoman feedback benar-benar masuk system prompt run berikut."""
    import json as _json
    memory.add_memory("global", "Panggil user dengan sapaan 'Kak'")
    fb = feedback.add_feedback("down", comment="Jawab maksimal 3 kalimat")
    feedback.apply_feedback(fb["id"])

    with client.stream("POST", "/api/chat",
                       json={"message": "halo"}) as r:
        system = None
        for line in r.iter_lines():
            if line.startswith("data: "):
                ev = _json.loads(line[6:])
                if ev["type"] == "prompt":
                    system = ev.get("system") or ""
    assert "Kak" in system
    assert "maksimal 3 kalimat" in system
