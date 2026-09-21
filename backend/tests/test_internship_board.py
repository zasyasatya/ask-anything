"""Papan proyek internship (`INT-NNN`) — rencana, seeder, track, dan halaman.

Papan ini **terpisah** dari papan platform (`ASK-NNN`): id berbeda prefix,
fase berbeda (i0–i5), dan statistiknya tidak boleh tercampur. Yang diuji:
  * rencana dari slide ter-seed lengkap & idempoten,
  * `track` menyaring board, stats, dan plan,
  * halaman /internship: ringkasan + materi + task milik sendiri (member),
  * pembagian kerja per intern & nama branch `feat/INT-NNN-…`.
"""
from __future__ import annotations

import pytest

from app import db, internship_plan, tasks
from app.tasks_plan import STATUSES


@pytest.fixture(autouse=True)
def _clean_intern_board(client):
    """Buang task buatan tes lain dari papan internship.

    Seluruh sesi pytest memakai satu database, jadi task yang dibuat tes
    berikutnya (mis. INT-034) akan terlihat di sini — bersihkan dulu supaya
    hitungan task = rencana dari `internship_plan`.
    """
    db.execute("DELETE FROM tasks WHERE track='internship' AND seeded=0")
    yield
    db.execute("DELETE FROM tasks WHERE track='internship' AND seeded=0")


def _intern_board(client):
    client.post("/api/tasks/seed", params={"track": "internship"})
    return client.get("/api/tasks", params={"track": "internship"}).json()


# ---------------------------------------------------------------------------
# Rencana (data statis)
# ---------------------------------------------------------------------------

def test_intern_plan_is_well_formed():
    ids = [t["id"] for t in internship_plan.TASKS]
    assert len(ids) == len(set(ids))
    phase_ids = set(internship_plan.PHASE_IDS)
    for task in internship_plan.TASKS:
        assert task["id"].startswith("INT-")
        assert task["id"][4:].isdigit()
        assert task["phase"] in phase_ids, task
        assert task["status"] in STATUSES, task
        assert task["title"].strip()
        assert task["acceptance"], f"{task['id']} tanpa kriteria selesai"
        assert task["evidence"], f"{task['id']} tanpa berkas bukti"
        assert task["assignee"] in internship_plan.INTERNS, task
        # Setiap task harus cukup detail untuk dikerjakan tanpa bertanya lagi.
        assert len(task["description"]) > 120, f"{task['id']} deskripsi terlalu tipis"
        assert task["workflow"], f"{task['id']} tanpa alur kerja"
        assert task["wireframe"], f"{task['id']} tanpa wireframe/sketsa"
        for step in task["workflow"]:
            assert step["action"].strip(), f"{task['id']} punya langkah kosong"


def test_intern_plan_covers_production_chatbot_end_to_end():
    """Rencana harus mencakup seluruh rantai produk, bukan prototipe saja."""
    blob = " ".join(f"{t['title']} {t['description']} {t['source']}"
                    for t in internship_plan.TASKS).lower()
    for keyword in (
        # fondasi & chat
        "kontrak api", "autentikasi", "streaming", "sse",
        # agent & pengetahuan
        "agent", "tool", "chunking", "embedding", "retrieval", "sitasi",
        "guardrail",
        # memori
        "memori", "ringkasan", "jendela konteks",
        # token, kuota, feedback
        "token", "kuota", "rate limit", "feedback", "analitik",
        # rilis
        "observability", "keamanan", "uji beban", "deploy", "runbook", "demo",
    ):
        assert keyword in blob, keyword
    phases = {t["phase"] for t in internship_plan.TASKS}
    assert phases == set(internship_plan.PHASE_IDS)


def test_intern_plan_details_feedback_memory_and_quota_tasks():
    """Tiga pilar yang diminta harus punya task tersendiri yang detail."""
    by_title = {t["id"]: f"{t['title']} {t['description']}".lower()
                for t in internship_plan.TASKS}
    joined = " ".join(by_title.values())
    # feedback 👍/👎 dengan alasan terstruktur
    assert "👍" in joined and "👎" in joined
    assert "alasan" in joined
    # manajemen memori: jangka menengah (ringkasan) & panjang (fakta pengguna)
    assert "jangka panjang" in joined
    # limit token per pengguna
    assert "kuota" in joined and "429" in joined


def test_every_phase_has_at_least_three_tasks():
    per_phase = internship_plan.summary()["per_phase"]
    assert set(per_phase) == set(internship_plan.PHASE_IDS)
    for phase_id, count in per_phase.items():
        assert count >= 3, f"fase {phase_id} hanya punya {count} task"


def test_dependencies_point_to_existing_earlier_tasks():
    ids = [t["id"] for t in internship_plan.TASKS]
    order = {task_id: i for i, task_id in enumerate(ids)}
    for task in internship_plan.TASKS:
        for dep in task["depends_on"]:
            assert dep in order, f"{task['id']} bergantung pada {dep} yang tidak ada"
            assert order[dep] < order[task["id"]], (
                f"{task['id']} bergantung pada task yang datang belakangan ({dep})")


def test_intern_plan_summary_counts_every_task():
    summary = internship_plan.summary()
    assert summary["total"] == len(internship_plan.TASKS)
    assert summary["track"] == "internship"
    assert sum(summary["per_phase"].values()) == len(internship_plan.TASKS)
    assert summary["per_assignee"] == {
        name: len(internship_plan.for_assignee(name))
        for name in internship_plan.INTERNS}


# ---------------------------------------------------------------------------
# Seeder & pemisahan papan
# ---------------------------------------------------------------------------

def test_seed_internship_is_idempotent(client):
    # startup aplikasi sudah meng-seed papan ini; seeder kedua tidak menambah
    client.post("/api/tasks/seed", params={"track": "internship"})
    again = client.post("/api/tasks/seed", params={"track": "internship"}).json()
    assert again["created"] == []
    assert again["total"] == len(internship_plan.TASKS)

    board = _intern_board(client)
    assert board["track"] == "internship"
    assert len(board["tasks"]) == len(internship_plan.TASKS)
    assert all(t["track"] == "internship" for t in board["tasks"])
    assert {t["id"] for t in board["tasks"]} == {
        t["id"] for t in internship_plan.TASKS}


def test_boards_are_isolated(client):
    platform = client.get("/api/tasks", params={"track": "platform"}).json()
    intern = _intern_board(client)
    assert all(t["id"].startswith("ASK-") for t in platform["tasks"])
    assert all(t["id"].startswith("INT-") for t in intern["tasks"])
    assert platform["stats"]["total"] != intern["stats"]["total"]
    assert {p["id"] for p in intern["plan"]["phases"]} == set(
        internship_plan.PHASE_IDS)
    assert {p["id"] for p in platform["plan"]["phases"]} == {"f0", "f1", "f2",
                                                             "f3", "f4", "f5"}


def test_next_intern_id_and_branch_name(client):
    _intern_board(client)
    created = client.post("/api/tasks", json={
        "title": "Task tambahan intern", "track": "internship", "phase": "i0",
        "assignee": "intern2"}).json()["task"]
    assert created["id"] == f"INT-{len(internship_plan.TASKS) + 1:03d}"
    assert created["branch_name"].startswith(f"feat/{created['id']}-")
    assert created["git_command"].startswith("git checkout -b feat/")


def test_intern_phase_validated_per_board(client):
    bad = client.post("/api/tasks", json={
        "title": "Fase salah", "track": "internship", "phase": "f3"})
    assert bad.status_code == 400
    assert "fase" in bad.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Halaman /internship (member melihat miliknya sendiri)
# ---------------------------------------------------------------------------

def test_overview_for_admin_lists_everything(client):
    _intern_board(client)
    data = client.get("/api/internship/overview").json()
    assert data["track"] == "internship"
    assert data["scope"] == "all"
    assert data["stats"]["total"] == len(internship_plan.TASKS)
    assert set(data["per_assignee"]) == set(internship_plan.INTERNS)
    assert data["project_dir"] == internship_plan.PROJECT_DIR
    assert isinstance(data["docs"], list)
    assert data["slides"], "slide rujukan harus tertaut"


def test_overview_for_member_only_own_tasks(client, strict_auth):
    """Member melihat task miliknya saja; akun intern di-seed otomatis startup."""
    from app.config import settings

    _intern_board(client)
    intern = internship_plan.INTERNS[0]
    res = client.post("/api/auth/login", json={
        "username": intern, "password": settings.member_password})
    assert res.status_code == 200, res.text

    data = client.get("/api/internship/overview").json()
    assert data["scope"] == "assigned"
    assert data["tasks"], "task member harus terlihat"
    for task in data["tasks"]:
        assert task["assignee"].lower() == intern.lower()
    assert data["stats"]["total"] == len(data["tasks"])
    assert data["stats"]["total"] < len(internship_plan.TASKS)


def test_overview_shows_progress_counts(client):
    _intern_board(client)
    board = client.get("/api/tasks", params={"track": "internship"}).json()
    first = board["tasks"][0]
    client.post(f"/api/tasks/{first['id']}/move", json={"status": "in_progress"})
    data = client.get("/api/internship/overview").json()
    who = first["assignee"]
    assert data["per_assignee"][who]["in_progress"] >= 1


def test_docs_endpoint_is_path_safe(client):
    # dokumen materi boleh belum ada, tapi endpoint tidak boleh membocorkan file lain
    idx = client.get("/api/internship/docs")
    assert idx.status_code == 200
    assert isinstance(idx.json()["docs"], list)
    assert client.get("/api/internship/docs/..%2F..%2FREADME.md").status_code in (400, 404)
    assert client.get("/api/internship/docs/tidak-ada").status_code == 404


def test_member_cannot_delete_or_create_intern_tasks(client, strict_auth,
                                                     make_user, login):
    _intern_board(client)
    member = make_user(role="member", password="benar123")
    login(member["username"], "benar123")
    assert client.post("/api/tasks", json={
        "title": "coba", "track": "internship", "phase": "i0"}).status_code == 403
    assert client.post("/api/tasks/seed",
                       params={"track": "internship"}).status_code == 403
    assert client.post("/api/tasks/sync",
                       params={"track": "internship"}).status_code == 403
    assert db.query_one("SELECT COUNT(*) AS n FROM tasks WHERE track='internship'")[
        "n"] == len(internship_plan.TASKS)


def test_track_helper_and_labels():
    assert tasks.track_of("INT-004") == "internship"
    assert tasks.track_of("ASK-004") == "platform"
    assert tasks.TRACK_LABELS["internship"].startswith("Proyek Internship")
