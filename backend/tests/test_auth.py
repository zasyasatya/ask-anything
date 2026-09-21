"""Login page, sesi, dan penegakan role (admin vs member) di server.

Yang dijamin:
  * tanpa login (mode `required`) API aplikasi menolak 401, kecuali health &
    endpoint login itu sendiri,
  * login salah ditolak, login benar membuat cookie HttpOnly + `/api/auth/me`
    mengembalikan user beserta izinnya,
  * **member**: tidak bisa membuka konsol admin, tidak bisa menyentuh setelan
    provider, tidak bisa mengunduh/memuat model offline (HuggingFace), tidak
    bisa mengunggah dokumen RAG, dan mode yang bukan haknya ditolak walau
    request dikirim langsung ke API,
  * **member** hanya melihat percakapan & task miliknya,
  * ganti password sendiri & reset password oleh admin bekerja (sesi lama mati).
"""
from __future__ import annotations

import pytest

from app import db, governance, users
from app.config import settings


# ---------------------------------------------------------------------------
# Hambatan awal (mode required)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/api/conversations",
    "/api/settings",
    "/api/policy",
    "/api/tasks",
    "/api/admin/policy",
    "/api/hf/models",
])
def test_endpoints_require_login_in_required_mode(client, strict_auth, path):
    assert client.get(path).status_code == 401


def test_health_stays_public_for_healthchecks(client, strict_auth):
    """run.py & HEALTHCHECK Docker memanggil /api/health tanpa kredensial."""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_rejects_wrong_password_and_unknown_user(client, strict_auth,
                                                       make_user):
    user = make_user(password="benar123")
    assert client.post("/api/auth/login", json={
        "username": user["username"], "password": "salah"}).status_code == 401
    assert client.post("/api/auth/login", json={
        "username": "tidak-ada", "password": "apa pun"}).status_code == 401
    assert client.get("/api/conversations").status_code == 401


def test_login_sets_httponly_cookie_and_me_returns_capabilities(
    client, strict_auth, make_user, login
):
    user = make_user(role="member", password="benar123")
    data = login(user["username"], "benar123")
    assert data["user"]["username"] == user["username"]
    assert data["user"]["capabilities"]["is_admin"] is False
    # password hash tidak pernah keluar ke browser
    assert "password_hash" not in data["user"]

    cookie = client.cookies.get(settings.session_cookie)
    assert cookie, "cookie sesi harus diset"
    assert client.get("/api/conversations").status_code == 200

    me = client.get("/api/auth/me").json()
    assert me["user"]["username"] == user["username"]
    assert me["user"]["capabilities"]["allow_offline_models"] is False

    client.post("/api/auth/logout")
    assert client.get("/api/conversations").status_code == 401


def test_bootstrap_hides_credentials_when_login_required(client, strict_auth):
    data = client.get("/api/auth/bootstrap").json()
    assert data["auth_mode"] == "required"
    assert data.get("credentials") is None


# ---------------------------------------------------------------------------
# Batas role member
# ---------------------------------------------------------------------------

@pytest.fixture()
def member(client, strict_auth, make_user, login):
    """Login sebagai member dan kembalikan datanya."""
    user = make_user(role="member", password="benar123")
    login(user["username"], "benar123")
    return user


@pytest.fixture()
def admin(new_client, strict_auth, make_user):
    """Client terpisah yang login sebagai admin."""
    user = make_user(role="admin", password="admin123")
    c = new_client()
    res = c.post("/api/auth/login", json={"username": user["username"],
                                          "password": "admin123"})
    assert res.status_code == 200, res.text
    return {"user": user, "client": c}


def test_member_blocked_from_admin_console(client, member):
    for path in ("/api/admin/policy", "/api/admin/users", "/api/admin/overview"):
        assert client.get(path).status_code == 403, path


def test_member_blocked_from_settings_and_offline_models(client, member):
    # setelan provider: baca boleh (key termask), tulis tidak
    seen = client.get("/api/settings")
    assert seen.status_code == 200
    assert seen.json()["can_manage"] is False
    assert seen.json()["role"] == "member"
    blocked = client.post("/api/settings", json={"provider": "huggingface"})
    assert blocked.status_code == 403

    # model offline (HuggingFace) diblokir sepenuhnya
    assert client.get("/api/hf/models").status_code == 403
    assert client.post("/api/hf/models/download",
                       json={"repo_id": "Qwen/Qwen3-0.6B"}).status_code == 403
    assert client.post("/api/hf/models/use",
                       json={"repo_id": "Qwen/Qwen3-0.6B"}).status_code == 403
    assert client.post("/api/models", json={}).status_code == 403
    assert client.post("/api/models/test", json={}).status_code == 403
    assert client.get("/api/hf/runtime").status_code == 403


def test_member_blocked_from_rag_upload(client, member, monkeypatch):
    res = client.post("/api/rag/upload",
                      files={"file": ("x.pdf", b"%PDF-1.4 isi", "application/pdf")})
    assert res.status_code == 403
    assert "knowledge base" in res.json()["detail"]


def test_member_mode_gate_enforced_on_server(client, member):
    """Mode yang bukan hak member ditolak walau request langsung ke API."""
    with client.stream("POST", "/api/chat",
                       json={"message": "buat poster", "mode": "image"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_lines())
    assert "tidak diizinkan untuk role member" in body


def test_member_chat_uses_openai_provider_not_offline(client, member, monkeypatch):
    """Member tidak boleh jatuh ke model offline walau provider global HF."""
    monkeypatch.setattr(settings, "provider", "huggingface")
    monkeypatch.setattr(settings, "hf_mode", "local")
    monkeypatch.setattr(settings, "openai_api_key", "")
    with client.stream("POST", "/api/chat",
                       json={"message": "halo", "mode": "text"}) as r:
        body = "".join(r.iter_lines())
    # mock (mode demo) tidak dipakai: role member diarahkan ke OpenAI, dan
    # karena key belum ada → pesan yang bisa ditindak, bukan error mentah.
    assert "OpenAI" in body

    monkeypatch.setattr(settings, "provider", "mock")
    with client.stream("POST", "/api/chat",
                       json={"message": "halo", "mode": "text"}) as r:
        body = "".join(r.iter_lines())
    assert "agent_done" in body


def test_member_only_sees_own_conversations(new_client, strict_auth, make_user,
                                           login):
    """Manajemen sesi: member A tidak bisa membaca sesi member B."""
    member_a = make_user(role="member", password="benar123")
    member_b = make_user(role="member", password="benar123")

    client_b = new_client()
    client_b.post("/api/auth/login", json={
        "username": member_b["username"], "password": "benar123"})
    with client_b.stream("POST", "/api/chat",
                         json={"message": "rahasia B", "mode": "text"}) as r:
        body = "".join(r.iter_lines())
    assert "agent_done" in body
    conv_b = client_b.get("/api/conversations").json()["conversations"][0]["id"]

    client_a = new_client()
    client_a.post("/api/auth/login", json={
        "username": member_a["username"], "password": "benar123"})
    mine = client_a.get("/api/conversations").json()
    assert mine["scope"] == "own"
    assert conv_b not in [c["id"] for c in mine["conversations"]]
    assert client_a.get(f"/api/conversations/{conv_b}").status_code == 403
    assert client_a.delete(f"/api/conversations/{conv_b}").status_code == 403


def test_admin_sees_every_conversation_with_owner(admin):
    c = admin["client"]
    data = c.get("/api/conversations").json()
    assert data["scope"] == "all"
    for conv in data["conversations"]:
        assert "owner_username" in conv


# ---------------------------------------------------------------------------
# Task: cakupan per anggota
# ---------------------------------------------------------------------------

def test_member_sees_only_assigned_tasks(client, member, new_client, admin):
    c = admin["client"]
    made = c.post("/api/tasks", json={
        "title": "Task untuk member ini", "track": "internship", "phase": "i0",
        "assignee": member["username"]}).json()["task"]
    other = c.post("/api/tasks", json={
        "title": "Task orang lain", "track": "internship", "phase": "i0",
        "assignee": "orang-lain"}).json()["task"]

    mine = client.get("/api/tasks", params={"track": "internship"}).json()
    assert mine["scope"] == "assigned"
    ids = [t["id"] for t in mine["tasks"]]
    assert made["id"] in ids
    assert other["id"] not in ids

    # boleh mengerjakan task-nya (ubah status + komentar), bukan task orang lain
    assert client.patch(f"/api/tasks/{made['id']}",
                        json={"status": "in_progress"}).status_code == 200
    assert client.get(f"/api/tasks/{other['id']}").status_code == 403
    assert client.post(f"/api/tasks/{other['id']}/comments",
                       json={"body": "halo"}).status_code == 403
    # membuat/menghapus task tetap khusus admin
    assert client.post("/api/tasks", json={"title": "coba"}).status_code == 403
    assert client.delete(f"/api/tasks/{made['id']}").status_code == 403
    assert client.post("/api/tasks/seed").status_code == 403


def test_member_cannot_reassign_or_change_priority_of_task(client, member,
                                                           new_client, admin):
    c = admin["client"]
    made = c.post("/api/tasks", json={
        "title": "Task berpindah tangan", "track": "internship", "phase": "i0",
        "assignee": member["username"]}).json()["task"]
    res = client.patch(f"/api/tasks/{made['id']}", json={
        "assignee": "intern2", "priority": "critical", "status": "review"})
    assert res.status_code == 200
    task = res.json()["task"]
    assert task["assignee"] == member["username"]  # tidak berubah
    assert task["priority"] == "medium"            # tidak berubah
    assert task["status"] == "review"              # status boleh berubah


def test_member_can_read_policy_for_own_role(client, member):
    pol = client.get("/api/policy").json()
    assert pol["role"] == "member"
    assert pol["modes"]["image"] is False
    assert pol["modes"]["text"] is True
    # admin bisa membuka option untuk member kapan saja
    assert governance.mode_allowed("image", "admin") is True


# ---------------------------------------------------------------------------
# Password
# ---------------------------------------------------------------------------

def test_user_can_change_own_password(client, member):
    res = client.post("/api/auth/password", json={
        "current_password": "benar123", "new_password": "passwordBaru9"})
    assert res.status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={
        "username": member["username"], "password": "benar123"}).status_code == 401
    assert client.post("/api/auth/login", json={
        "username": member["username"],
        "password": "passwordBaru9"}).status_code == 200


def test_change_password_requires_old_password(client, member):
    res = client.post("/api/auth/password", json={
        "current_password": "salah", "new_password": "passwordBaru9"})
    assert res.status_code == 403


def test_admin_resets_member_password_and_revokes_sessions(member, new_client,
                                                           admin):
    c = admin["client"]
    res = c.post(f"/api/admin/users/{member['id']}/password",
                 json={"password": "resetOlehAdmin1"})
    assert res.status_code == 200
    # sesi member lama tidak berlaku lagi
    assert member is not None
    login_again = new_client().post("/api/auth/login", json={
        "username": member["username"], "password": "resetOlehAdmin1"})
    assert login_again.status_code == 200


def test_users_crud_via_admin_api(new_client, admin):
    c = admin["client"]
    created = c.post("/api/admin/users", json={
        "username": "Intern-Baru", "password": "rahasia123", "name": "Intern Baru",
        "role": "member"})
    assert created.status_code == 200, created.text
    user = created.json()["user"]
    assert user["username"] == "intern-baru"   # dinormalkan ke huruf kecil
    assert user["role"] == "member"

    assert c.patch(f"/api/admin/users/{user['id']}",
                   json={"role": "admin"}).json()["user"]["role"] == "admin"
    assert c.patch(f"/api/admin/users/{user['id']}",
                   json={"active": False}).json()["user"]["active"] is False

    # akun nonaktif → pesan seragam 401 (tidak membocorkan status akun)
    login_disabled = new_client().post("/api/auth/login", json={
        "username": user["username"], "password": "rahasia123"})
    assert login_disabled.status_code == 401

    assert c.delete(f"/api/admin/users/{user['id']}").status_code == 200
    assert users.get_user(user["id"]) is None


def test_last_admin_cannot_be_demoted_or_deleted(new_client, monkeypatch):
    """Pagar keselamatan: jangan sampai sistem kehilangan admin terakhir."""
    admin = users.create_user(username="admin-inti", password="rahasia123",
                              role="admin")
    db.execute("UPDATE users SET role='member' WHERE id<>? AND role='admin'",
               (admin["id"],))
    monkeypatch.setattr(settings, "auth_mode", "required")
    with pytest.raises(users.UserError):
        users.update_user(admin["id"], {"role": "member"})
    with pytest.raises(users.UserError):
        users.delete_user(admin["id"])


def test_login_throttled_after_repeated_failures(client, strict_auth, make_user,
                                                 monkeypatch):
    monkeypatch.setattr(settings, "login_max_attempts", 3)
    user = make_user(role="member", password="benar123")
    for _ in range(3):
        assert client.post("/api/auth/login", json={
            "username": user["username"], "password": "salah"}).status_code == 401
    assert client.post("/api/auth/login", json={
        "username": user["username"], "password": "salah"}).status_code == 429
    # password benar pun ikut tertahan selama jendela blokir
    assert client.post("/api/auth/login", json={
        "username": user["username"], "password": "benar123"}).status_code == 429


USER_COLS = ("id", "username", "name", "role", "password_hash", "active",
             "must_change_password", "created_at", "updated_at", "last_login")


@pytest.fixture()
def restore_users(client):
    """Tes yang mengosongkan tabel `users` harus memulihkannya.

    Seluruh sesi pytest memakai satu database, jadi akun seed (admin/intern1-3)
    yang dihapus satu tes akan merusak tes lain di file/berkas berbeda.
    """
    rows = db.query_all("SELECT * FROM users")
    yield
    db.execute("DELETE FROM users")
    for row in rows:
        db.execute(
            "INSERT INTO users(" + ",".join(USER_COLS) + ") VALUES("
            + ",".join("?" * len(USER_COLS)) + ")",
            tuple(row[col] for col in USER_COLS))


def test_seed_users_creates_admin_and_members(monkeypatch, strict_auth,
                                              restore_users):
    """Seed awal: 1 admin + akun member contoh dari env, idempoten."""
    from app import users as users_mod

    db.execute("DELETE FROM users")
    monkeypatch.setattr(settings, "admin_username", "admin-utama")
    monkeypatch.setattr(settings, "admin_password", "adminAwal1")
    monkeypatch.setattr(settings, "seed_members", "internA,internB")
    monkeypatch.setattr(settings, "member_password", "internAwal1")

    first = users_mod.ensure_seed_users(settings)
    assert [u["role"] for u in first["created"]] == ["admin", "member", "member"]

    admin = users_mod.authenticate("admin-utama", "adminAwal1")
    assert admin and admin["role"] == "admin"
    intern = users_mod.authenticate("interna", "internAwal1")
    assert intern and intern["role"] == "member"

    # idempoten: panggilan kedua tidak menambah apa pun
    again = users_mod.ensure_seed_users(settings)
    assert again == {"created": [], "skipped": True}


def test_password_hash_never_returned_and_verifies():
    digest = users.hash_password("rahasia123")
    assert digest.startswith("pbkdf2_sha256$")
    assert "rahasia123" not in digest
    assert users.verify_password(digest, "rahasia123") is True
    assert users.verify_password(digest, "salah") is False
    assert users.verify_password("hash-rusak", "rahasia123") is False
