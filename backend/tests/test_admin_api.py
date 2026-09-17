"""Tests: Admin API — policy CRUD, token auth, memori/artifact/feedback."""
import pytest

from app import governance


@pytest.fixture(autouse=True)
def _clean(client, monkeypatch):
    """Policy default + admin token nonaktif untuk tiap tes di modul ini."""
    from app import db
    from app.config import settings
    monkeypatch.setattr(settings, "admin_token", "")
    db.execute("DELETE FROM admin_policy")
    db.execute("DELETE FROM memories")
    db.execute("DELETE FROM feedback")
    yield
    monkeypatch.setattr(settings, "admin_token", "")
    db.execute("DELETE FROM admin_policy")
    db.execute("DELETE FROM memories")
    db.execute("DELETE FROM feedback")


def test_policy_roundtrip(client):
    pol = client.get("/api/admin/policy").json()["policy"]
    assert pol["modes"]["text"] is True
    r = client.put("/api/admin/policy",
                   json={"modes": {"image": False},
                         "rag": {"top_k": 7}})
    pol2 = r.json()["policy"]
    assert pol2["modes"]["image"] is False
    assert pol2["rag"]["top_k"] == 7
    assert pol2["modes"]["text"] is True

    pub = client.get("/api/policy").json()
    assert pub["modes"]["image"] is False
    assert pub["rag"]["top_k"] == 7


def test_policy_shape_rejected_values_dont_leak(client):
    r = client.put("/api/admin/policy",
                   json={"modes": {"image": "bukan-boolean-masih-disimpan"}})
    # nilai asing diterima apa adanya (admin punya kendali) tapi key asing tidak
    assert "haram" not in r.json()["policy"]["modes"]


def test_admin_token_required(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_token", "rahasia123")
    assert client.get("/api/admin/policy").status_code == 401
    assert client.get("/api/admin/overview",
                      headers={"X-Admin-Token": "salah"}).status_code == 401
    ok = client.get("/api/admin/overview",
                    headers={"X-Admin-Token": "rahasia123"})
    assert ok.status_code == 200
    assert ok.json()["admin_protected"] is True
    # endpoint publik tetap bisa diakses tanpa token
    assert client.get("/api/policy").status_code == 200


def test_memories_crud_via_api(client):
    m = client.post("/api/admin/memories", json={
        "scope": "global", "key": "tone", "content": "Jawab singkat"})
    assert m.status_code == 200
    mid = m.json()["id"]
    assert client.get("/api/admin/memories").json()["memories"]

    r = client.patch(f"/api/admin/memories/{mid}", json={"enabled": False})
    assert r.json()["enabled"] is False
    assert client.patch("/api/admin/memories/xxx",
                        json={"enabled": True}).status_code == 404
    assert client.delete(f"/api/admin/memories/{mid}").json()["ok"]
    # content kosong ditolak
    assert client.post("/api/admin/memories",
                       json={"content": "  "}).status_code == 422


def test_feedback_flow_via_api(client):
    fb = client.post("/api/feedback", json={
        "rating": "up", "comment": "mantap"}).json()["feedback"]
    fid = fb["id"]

    listed = client.get("/api/admin/feedback").json()
    assert any(f["id"] == fid for f in listed["feedback"])
    assert listed["stats"]["up"] >= 1

    r = client.patch(f"/api/admin/feedback/{fid}", json={"status": "reviewed"})
    assert r.json()["status"] == "reviewed"
    assert client.patch(f"/api/admin/feedback/{fid}",
                        json={"status": "aneh"}).status_code == 422

    applied = client.post(f"/api/admin/feedback/{fid}/apply").json()
    assert applied["memory"]["source"] == "feedback"

    assert client.delete(f"/api/admin/feedback/{fid}").json()["ok"]


def test_feedback_disabled_by_policy(client):
    governance.update_policy({"feedback": {"enabled": False}})
    r = client.post("/api/feedback", json={"rating": "up"})
    assert r.status_code == 403
    governance.update_policy({"feedback": {"enabled": True}})


def test_overview_counters(client):
    import asyncio

    from app import artifacts, memory
    from app.config import settings
    memory.add_memory("global", "tes overview")
    artifacts.register_artifact(
        settings=settings, kind="data", title="t", filename="t.bin",
        mime="application/octet-stream", data=b"\x00\x01")
    ov = client.get("/api/admin/overview").json()
    assert ov["counts"]["memories"] >= 1
    assert ov["counts"]["artifacts"] >= 1
    assert "feedback" in ov and "policy" in ov
    assert ov["counts"]["trace_events"] >= 0
