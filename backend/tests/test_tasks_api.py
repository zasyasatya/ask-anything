"""Task management — papan rencana RAG (`/tasks`) di sisi backend.

Yang dijamin di sini:
  * rencana RAG benar-benar ter-seed & id-nya rapi (`ASK-NNN` unik, fase valid),
  * CRUD + drag & drop (`move`) + checklist + komentar bekerja lewat HTTP,
  * task id → nama branch GitLab konsisten (`feat/ASK-NNN-slug`),
  * `sync` menaikkan status dari bukti kode tapi tidak pernah menurunkannya.
"""
import pytest

from app import tasks
from app.tasks_plan import PHASE_IDS, STATUSES, TASKS as PLAN_TASKS


def _fresh(client):
    """Pastikan papan berisi rencana (seeder idempoten) untuk tiap test."""
    client.post("/api/tasks/seed")
    return client.get("/api/tasks").json()


# ---------------------------------------------------------------------------
# Rencana (data statis)
# ---------------------------------------------------------------------------

def test_plan_ids_are_unique_and_well_formed():
    ids = [t["id"] for t in PLAN_TASKS]
    assert len(ids) == len(set(ids)), "id task harus unik"
    for task in PLAN_TASKS:
        assert task["id"].startswith("ASK-")
        assert task["id"][4:].isdigit() and len(task["id"][4:]) >= 3
        assert task["phase"] in PHASE_IDS, task
        assert task["status"] in STATUSES, task
        assert task["title"].strip()
        assert task["acceptance"], f"{task['id']} tanpa kriteria selesai"


def test_plan_covers_every_phase_and_core_rag_work():
    phases = {t["phase"] for t in PLAN_TASKS}
    assert phases == set(PHASE_IDS)
    blob = " ".join(f"{t['title']} {t['description']}" for t in PLAN_TASKS).lower()
    for keyword in ("retrieve_knowledge", "create_chart", "chunking",
                    "vector", "admin_token", "task management"):
        assert keyword.lower() in blob, keyword


def test_branch_name_uses_task_id_and_is_git_safe():
    name = tasks.branch_name({"id": "ASK-007", "labels": [],
                              "title": "Tab Feedback: 👍/👎 + 'Jadikan pedoman'"})
    assert name == "feat/ASK-007-tab-feedback-jadikan-pedoman"
    assert " " not in name and ":" not in name
    bug = tasks.branch_name({"id": "ASK-050", "labels": ["bugfix"],
                             "title": "Perbaiki prompt"})
    assert bug.startswith("fix/ASK-050-")


# ---------------------------------------------------------------------------
# Seed & koleksi
# ---------------------------------------------------------------------------

def test_seed_is_idempotent_and_keeps_edits(client):
    data = _fresh(client)
    assert len(data["tasks"]) == len(PLAN_TASKS)

    client.patch("/api/tasks/ASK-001", json={"title": "Judul diubah developer"})
    again = client.post("/api/tasks/seed").json()
    assert again["created"] == []          # tidak ada yang dibuat ulang
    detail = client.get("/api/tasks/ASK-001").json()["task"]
    assert detail["title"] == "Judul diubah developer"   # tidak ditimpa


def test_list_filters_and_stats(client):
    _fresh(client)
    data = client.get("/api/tasks", params={"phase": "f0"}).json()
    assert data["tasks"] and all(t["phase"] == "f0" for t in data["tasks"])

    search = client.get("/api/tasks", params={"q": "retrieve_knowledge"}).json()
    assert any(t["id"] == "ASK-030" for t in search["tasks"])

    stats = data["stats"]
    assert stats["total"] == len(PLAN_TASKS)
    assert set(stats["per_status"]) == set(STATUSES)
    assert stats["per_phase"]["f0"]["total"] > 0
    assert stats["estimate_total"] > 0


# ---------------------------------------------------------------------------
# CRUD + kolom + checklist + komentar
# ---------------------------------------------------------------------------

def test_create_update_delete_task(client):
    _fresh(client)
    created = client.post("/api/tasks", json={
        "title": "Riset vector DB alternatif",
        "description": "Bandingkan Chroma vs Qdrant",
        "phase": "f2", "priority": "low", "estimate": 1.5,
        "labels": ["research"], "acceptance": ["Tabel perbandingan jadi"],
    }).json()["task"]
    assert created["id"].startswith("ASK-")
    assert created["branch_name"].endswith("riset-vector-db-alternatif")
    assert created["acceptance_total"] == 1

    patched = client.patch(f"/api/tasks/{created['id']}",
                           json={"status": "in_progress",
                                 "assignee": "zasya"}).json()["task"]
    assert patched["status"] == "in_progress"
    assert patched["assignee"] == "zasya"
    # pindah status otomatis tercatat sebagai aktivitas
    assert any(c["kind"] == "activity"
               for c in client.get(f"/api/tasks/{created['id']}").json()
               ["task"]["comments"])

    assert client.delete(f"/api/tasks/{created['id']}").json()["ok"] is True
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_create_rejects_bad_payload(client):
    _fresh(client)
    assert client.post("/api/tasks", json={"title": "  "}).status_code == 400
    r = client.post("/api/tasks", json={"title": "x", "phase": "f9"})
    assert r.status_code == 400
    assert client.post("/api/tasks", json={"title": "x", "status": "ngawur"}
                       ).status_code == 400


def test_move_task_reorders_column(client):
    _fresh(client)
    first = client.get("/api/tasks", params={"status": "review"}).json()["tasks"][0]
    target = client.post(f"/api/tasks/{first['id']}/move",
                         json={"status": "in_progress"}).json()
    assert target["task"]["status"] == "in_progress"
    column = [t["id"] for t in target["tasks"] if t["status"] == "in_progress"]
    assert first["id"] in column
    positions = [t["position"] for t in target["tasks"]
                 if t["status"] == "in_progress"]
    assert positions == sorted(positions)


def test_acceptance_and_comments(client):
    _fresh(client)
    add = client.post("/api/tasks/ASK-010/acceptance",
                      json={"text": "Uji threshold 0.35"}).json()["task"]
    idx = add["acceptance_total"] - 1
    assert add["acceptance"][idx]["text"] == "Uji threshold 0.35"

    done = client.post("/api/tasks/ASK-010/acceptance",
                       json={"index": idx, "done": True}).json()["task"]
    assert done["acceptance"][idx]["done"] is True
    assert done["progress"] > 0

    removed = client.post("/api/tasks/ASK-010/acceptance",
                          json={"index": idx, "remove": True}).json()["task"]
    assert removed["acceptance_total"] == add["acceptance_total"] - 1

    comment = client.post("/api/tasks/ASK-010/comments",
                          json={"body": "skor cosine sudah masuk akal",
                                "author": "dev"}).json()
    assert comment["comments"][-1]["body"].startswith("skor cosine")
    assert client.post("/api/tasks/ASK-010/comments",
                       json={"body": "   "}).status_code == 400
    cid = comment["comments"][-1]["id"]
    assert client.delete(f"/api/tasks/comments/{cid}").json()["ok"] is True


def test_task_detail_has_dependencies_and_branch(client):
    _fresh(client)
    task = client.get("/api/tasks/ASK-030").json()["task"]
    assert [d["id"] for d in task["depends_on_tasks"]] == ["ASK-024", "ASK-019"]
    assert task["git_command"].startswith("git checkout -b feat/ASK-030-")
    assert task["blocked_by"]            # prasyarat belum selesai
    # detail task lain menampilkan siapa saja yang menunggu dia
    upstream = client.get("/api/tasks/ASK-024").json()["task"]
    assert "ASK-030" in {d["id"] for d in upstream["dependents"]}
    assert upstream["ready"] in (True, False)


# ---------------------------------------------------------------------------
# Sinkronisasi kode & git
# ---------------------------------------------------------------------------

def test_sync_marks_review_when_evidence_exists(client, monkeypatch):
    _fresh(client)
    task = client.get("/api/tasks/ASK-001").json()["task"]
    # ASK-001 punya bukti implementasi di repo ini
    assert tasks._touched(task["evidence"]) is True

    report = client.post("/api/tasks/sync").json()
    assert report["is_repo"] in (True, False)
    after = client.get("/api/tasks/ASK-001").json()["task"]
    assert after["status"] in ("review", "done")


def test_sync_never_downgrades_a_done_task(client):
    _fresh(client)
    client.patch("/api/tasks/ASK-005", json={"status": "done"})
    client.post("/api/tasks/sync")
    assert client.get("/api/tasks/ASK-005").json()["task"]["status"] == "done"


def test_sync_picks_up_branch_and_commit(monkeypatch, client):
    """Branch/commit yang menyebut ASK-NNN menaikkan status + menyimpan sha."""
    _fresh(client)
    monkeypatch.setattr(tasks, "git_snapshot", lambda limit=600: {
        "branches": ["feat/ASK-021-ui-documentuploader"], "commits": [
            {"sha": "abc123456789", "subject": "feat(ASK-021): uploader drag & drop"},
            {"sha": "def456789012", "subject": "chore: selesai ASK-021"},
        ], "repo": "/tmp/repo", "is_repo": True})
    report = client.post("/api/tasks/sync").json()
    task = client.get("/api/tasks/ASK-021").json()["task"]
    assert task["branch"] == "feat/ASK-021-ui-documentuploader"
    assert [c["sha"] for c in task["commits"]] == ["abc123456789", "def456789012"]
    assert task["status"] == "done"          # commit "selesai" menutup task
    assert any(c["id"] == "ASK-021" for c in report["changed"])


def test_reset_seed_only_touches_plan_tasks(client):
    _fresh(client)
    manual = client.post("/api/tasks", json={"title": "Catatan pribadi"}).json()["task"]
    client.patch("/api/tasks/ASK-003", json={"status": "done"})
    client.post("/api/tasks/seed", params={"reset": True})
    assert client.get(f"/api/tasks/{manual['id']}").status_code == 200
    assert client.get("/api/tasks/ASK-003").json()["task"]["status"] == "todo"


# ---------------------------------------------------------------------------
# Detail task: workflow (aktor → aksi → hasil) & wireframe
# ---------------------------------------------------------------------------

def test_workflow_and_wireframe_roundtrip(client):
    """Task bisa menyimpan alur kerja bernomor + sketsa layout."""
    _fresh(client)
    created = client.post("/api/tasks", json={
        "title": "Tombol feedback",
        "workflow": [
            {"actor": "Pengguna", "action": "Klik 👎", "result": "Dialog terbuka"},
            {"actor": "Backend", "action": "UPSERT unik", "result": "Tidak ganda"},
        ],
        "wireframe": "+--- dialog ---+",
    }).json()["task"]

    assert [s["step"] for s in created["workflow"]] == [1, 2]
    assert created["workflow"][0]["actor"] == "Pengguna"
    assert created["workflow"][1]["result"] == "Tidak ganda"
    assert created["wireframe"] == "+--- dialog ---+"

    patched = client.patch(f"/api/tasks/{created['id']}", json={
        "workflow": [{"actor": "QA", "action": "Uji ulang"}],
        "wireframe": "baru",
    }).json()["task"]
    assert len(patched["workflow"]) == 1
    assert patched["workflow"][0] == {"step": 1, "actor": "QA",
                                      "action": "Uji ulang", "result": ""}
    assert patched["wireframe"] == "baru"


def test_workflow_accepts_plain_strings_and_drops_empty_steps(client):
    """Rencana lama (list string) tetap valid; langkah kosong dibuang."""
    _fresh(client)
    task = client.post("/api/tasks", json={
        "title": "Kompatibilitas",
        "workflow": ["langkah pertama", {"actor": "", "action": "", "result": ""}],
    }).json()["task"]
    assert task["workflow"] == [
        {"step": 1, "actor": "", "action": "langkah pertama", "result": ""}]


def test_seeded_internship_tasks_expose_workflow_and_wireframe(client):
    """Papan internship ter-seed lengkap dengan detail alur & sketsa."""
    client.post("/api/tasks/seed", params={"track": "internship"})
    task = client.get("/api/tasks/INT-026").json()["task"]
    assert task["workflow"], "task feedback harus punya alur kerja"
    assert task["wireframe"], "task feedback harus punya wireframe"
    assert all(s["step"] == i + 1 for i, s in enumerate(task["workflow"]))


def test_member_cannot_edit_workflow_or_wireframe(client, strict_auth):
    """Member hanya menggerakkan status — rancangan task milik admin."""
    from app import internship_plan, users

    client.post("/api/tasks/seed", params={"track": "internship"})
    intern = internship_plan.INTERNS[0]
    account = users.get_user_by_username(intern)
    assert account, "akun intern dibuat otomatis saat startup"
    users.set_password(account["id"], "rahasia123")
    assert client.post("/api/auth/login", json={
        "username": intern, "password": "rahasia123"}).status_code == 200
    before = client.get("/api/tasks/INT-001").json()["task"]
    assert before["assignee"] == intern
    client.patch("/api/tasks/INT-001", json={"wireframe": "diubah member",
                                             "workflow": []})
    after = client.get("/api/tasks/INT-001").json()["task"]
    assert after["wireframe"] == before["wireframe"]
    assert after["workflow"] == before["workflow"]


# ---------------------------------------------------------------------------
# ID otomatis (ASK-NNN / INT-NNN tergenerate saat menyimpan)
# ---------------------------------------------------------------------------

def test_next_id_previews_per_track(client):
    """Pratinjau nomor berikutnya mengikuti papan yang diminta."""
    client.post("/api/tasks/seed")
    client.post("/api/tasks/seed", params={"track": "internship"})
    plat = client.get("/api/tasks/next-id", params={"track": "platform"}).json()
    assert plat["track"] == "platform"
    assert plat["next_id"].startswith("ASK-")
    inter = client.get("/api/tasks/next-id",
                       params={"track": "internship"}).json()
    assert inter["track"] == "internship"
    assert inter["next_id"].startswith("INT-")
    assert client.get("/api/tasks/next-id").json()["track"] == "platform"


def test_create_auto_id_matches_preview_and_increments(client):
    """Task tanpa task_id memakai nomor pratinjau, lalu berlanjut naik."""
    _fresh(client)
    preview = client.get("/api/tasks/next-id").json()["next_id"]
    first = client.post("/api/tasks", json={"title": "auto satu"}).json()["task"]
    assert first["id"] == preview, "ID pertama harus sama dengan pratinjau"
    second = client.post("/api/tasks", json={"title": "auto dua"}).json()["task"]
    assert int(second["id"][4:]) == int(first["id"][4:]) + 1
    assert second["branch_name"].startswith(f"feat/{second['id']}-")


def test_create_on_internship_track_gets_int_id(client):
    """Membuat task dari papan internship → ID INT-NNN, bukan ASK-NNN."""
    client.post("/api/tasks/seed", params={"track": "internship"})
    task = client.post("/api/tasks", json={
        "title": "Tugas magang baru", "track": "internship", "phase": "i1",
    }).json()["task"]
    assert task["id"].startswith("INT-")
    assert task["track"] == "internship"


def test_create_explicit_duplicate_still_rejected(client):
    """ID eksplisit yang sudah ada tetap ditolak (tidak ditimpa diam-diam)."""
    _fresh(client)
    res = client.post("/api/tasks", json={"title": "x", "task_id": "ASK-001"})
    assert res.status_code == 400
    assert "sudah ada" in res.text


def test_create_auto_id_retries_on_collision(client):
    """Bentrok nomor saat generate → hitung ulang, bukan gagal.

    Mensimulasikan dua admin yang membuat task bersamaan: generator
    dipaksa mengembalikan nomor yang sudah dipakai dulu.
    """
    from app import tasks

    _fresh(client)
    real_next = tasks.next_task_id
    calls = {"n": 0}

    def flaky(track="platform"):
        calls["n"] += 1
        if calls["n"] == 1:
            return "ASK-001"  # sudah dipakai rencana → harus dilewati
        return real_next(track)

    tasks.next_task_id = flaky  # type: ignore[method-assign]
    try:
        task = client.post("/api/tasks",
                           json={"title": "lolos walau bentrok"}).json()["task"]
    finally:
        tasks.next_task_id = real_next  # type: ignore[method-assign]
    assert task["id"] != "ASK-001"
    assert task["id"].startswith("ASK-")
