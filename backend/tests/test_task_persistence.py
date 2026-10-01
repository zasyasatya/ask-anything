"""Task bisa disunting, ditambah, dihapus — dan semuanya bertahan.

Yang diuji adalah jaminan persistensi papan:
  * menyunting isi task rencana menandainya `edited` (progres seperti pindah
    kolom / centang kriteria bukan suntingan isi),
  * pembaruan rencana (`refresh_plan_if_stale`) tidak menimpa task `edited` atau
    `done`, dan membawa progres task yang belum disentuh,
  * task rencana yang dihapus tidak muncul lagi (seed, boot, pembaruan rencana)
    sampai dipulihkan secara eksplisit; nomornya tidak dipakai ulang,
  * task buatan tangan tidak pernah disentuh pembaruan rencana,
  * INT-001..004 dibekukan; INT-005 (sudah di-merge) berstatus done.
"""
from __future__ import annotations

import pytest

from app import db, internship_plan, tasks

TRACK = "internship"


def _force_refresh() -> dict:
    db.execute("DELETE FROM admin_policy WHERE key=?",
               (f"plan_revision:{TRACK}",))
    return tasks.refresh_plan_if_stale(TRACK)


@pytest.fixture(autouse=True)
def _fresh_board(client):
    """Papan internship bersih dari rencana (tanpa nisan, tanpa task buatan)."""
    db.execute("DELETE FROM tasks WHERE track=? AND seeded=0", (TRACK,))
    tasks.seed_tasks(reset=True, track=TRACK)
    yield
    db.execute("DELETE FROM tasks WHERE track=? AND seeded=0", (TRACK,))
    tasks.seed_tasks(reset=True, track=TRACK)


# ---------------------------------------------------------------------------
# Penanda `edited`
# ---------------------------------------------------------------------------

def test_editing_content_marks_seeded_task_edited():
    assert tasks.get_task("INT-008")["edited"] is False
    updated = tasks.update_task("INT-008", {"title": "Sesi persisten (judul saya)"})
    assert updated["edited"] is True
    assert updated["title"] == "Sesi persisten (judul saya)"


def test_progress_changes_do_not_mark_edited():
    task = tasks.get_task("INT-009")
    tasks.update_task("INT-009", {"status": "in_progress",
                                  "assignee": "verisimb",
                                  "branch": "feat/INT-009-token",
                                  "mr_url": "https://git.example/mr/9"})
    tasks.update_task("INT-009", {"acceptance": [
        {"text": a["text"], "done": i == 0}
        for i, a in enumerate(task["acceptance"])]})
    assert tasks.get_task("INT-009")["edited"] is False


def test_saving_identical_content_is_not_an_edit():
    task = tasks.get_task("INT-010")
    tasks.update_task("INT-010", {"title": task["title"],
                                  "description": task["description"],
                                  "labels": task["labels"],
                                  "workflow": task["workflow"]})
    assert tasks.get_task("INT-010")["edited"] is False


@pytest.mark.parametrize("field,value", [
    ("description", "Deskripsi baru yang ditulis tangan."),
    ("priority", "low"),
    ("estimate", 9),
    ("labels", ["internship", "custom"]),
    ("depends_on", ["INT-005"]),
    ("evidence", ["ai-assistant-prototype/README.md"]),
    ("source", "catatan-rapat.md"),
    ("wireframe", "+----+\n| ok |\n+----+"),
    ("workflow", [{"actor": "Intern", "action": "Langkah baru", "result": ""}]),
])
def test_every_content_field_counts_as_edit(field, value):
    tasks.update_task("INT-011", {field: value})
    assert tasks.get_task("INT-011")["edited"] is True, field


def test_editing_acceptance_text_marks_edited_but_checking_does_not():
    task = tasks.get_task("INT-012")
    texts = [a["text"] for a in task["acceptance"]]
    tasks.set_acceptance("INT-012", 0, True)
    assert tasks.get_task("INT-012")["edited"] is False
    tasks.add_acceptance("INT-012", "Kriteria tambahan buatan saya")
    after = tasks.get_task("INT-012")
    assert after["edited"] is True
    assert [a["text"] for a in after["acceptance"]][:len(texts)] == texts


def test_system_updates_never_mark_edited():
    tasks.update_task("INT-013", {"title": "Dari rencana"}, system=True)
    assert tasks.get_task("INT-013")["edited"] is False


# ---------------------------------------------------------------------------
# Pembaruan rencana tidak menimpa pekerjaan tangan
# ---------------------------------------------------------------------------

def test_refresh_keeps_edited_tasks_and_updates_untouched_ones():
    tasks.update_task("INT-014", {"title": "Judul hasil suntingan saya",
                                  "wireframe": "sketsa saya"})
    # task lain dirusak 'seolah rencana lama' → harus ditulis ulang dari rencana
    db.execute("UPDATE tasks SET title='JUDUL LAMA', description='lama' "
               "WHERE id='INT-015'")

    report = _force_refresh()
    assert report["changed"] is True
    assert "INT-014" in report["kept"] and "INT-014" not in report["updated"]
    assert "INT-015" in report["updated"]

    mine = tasks.get_task("INT-014")
    assert mine["title"] == "Judul hasil suntingan saya"
    assert mine["wireframe"] == "sketsa saya"
    plan_title = next(t["title"] for t in internship_plan.TASKS
                      if t["id"] == "INT-015")
    assert tasks.get_task("INT-015")["title"] == plan_title


def test_refresh_does_not_rewrite_done_tasks():
    db.execute("UPDATE tasks SET title='Selesai, jangan disentuh' WHERE id='INT-002'")
    report = _force_refresh()
    assert "INT-002" in report["kept"]
    assert tasks.get_task("INT-002")["title"] == "Selesai, jangan disentuh"


def test_refresh_never_lowers_status_but_plan_can_promote():
    tasks.update_task("INT-016", {"status": "review"})
    db.execute("UPDATE tasks SET status='todo' WHERE id='INT-005'")
    _force_refresh()
    assert tasks.get_task("INT-016")["status"] == "review"      # tidak turun
    assert tasks.get_task("INT-005")["status"] == "done"        # rencana menaikkan


def test_refresh_carries_assignee_branch_and_checked_criteria():
    task = tasks.get_task("INT-017")
    first = task["acceptance"][0]["text"]
    tasks.update_task("INT-017", {
        "status": "in_progress", "assignee": "intern-lain",
        "branch": "feat/INT-017-graphview",
        "acceptance": [{"text": a["text"], "done": a["text"] == first}
                       for a in task["acceptance"]]})
    db.execute("UPDATE tasks SET description='lama' WHERE id='INT-017'")
    _force_refresh()
    after = tasks.get_task("INT-017")
    assert after["description"] != "lama"
    assert after["status"] == "in_progress"
    assert after["assignee"] == "intern-lain"
    assert after["branch"] == "feat/INT-017-graphview"
    assert {a["text"] for a in after["acceptance"] if a["done"]} == {first}


def test_refresh_leaves_handmade_tasks_and_reports_id_conflicts():
    mine = tasks.create_task(title="Catatan saya", track=TRACK, phase="i0")
    tasks.delete_task("INT-032")
    tasks.create_task(title="Task saya memakai nomor rencana", track=TRACK,
                      phase="i5", task_id="INT-032")
    report = _force_refresh()
    assert "INT-032" in report["conflicts"]
    assert tasks.get_task("INT-032")["title"] == "Task saya memakai nomor rencana"
    assert tasks.get_task(mine["id"])["title"] == "Catatan saya"


def test_refresh_adds_new_plan_tasks_and_drops_obsolete_untouched_ones():
    db.execute("DELETE FROM tasks WHERE id='INT-031'")        # 'belum ada' di papan lama
    db.execute(
        "INSERT INTO tasks(id,title,phase,status,priority,track,seeded,created_at,updated_at)"
        " VALUES('INT-099','Usang dari rencana lama','i3','backlog','low','internship',1,1,1)")
    db.execute(
        "INSERT INTO tasks(id,title,phase,status,priority,track,seeded,edited,created_at,updated_at)"
        " VALUES('INT-098','Usang tapi saya sunting','i3','backlog','low','internship',1,1,1,1)")
    report = _force_refresh()
    assert "INT-031" in report["created"]
    assert "INT-099" in report["removed"] and tasks.get_task("INT-099") is None
    assert tasks.get_task("INT-098") is not None              # edited → dibiarkan


def test_refresh_is_a_noop_the_second_time():
    assert _force_refresh()["changed"] is True
    assert tasks.refresh_plan_if_stale(TRACK)["changed"] is False


def test_sprint_zero_is_frozen_and_int_005_is_done():
    before = {tid: tasks.get_task(tid) for tid in
              ("INT-001", "INT-002", "INT-003", "INT-004")}
    _force_refresh()
    for tid, old in before.items():
        new = tasks.get_task(tid)
        assert new["status"] == "done"
        for key in ("title", "description", "workflow", "wireframe", "evidence",
                    "acceptance", "labels", "estimate", "priority"):
            assert new[key] == old[key], (tid, key)
    five = tasks.get_task("INT-005")
    assert five["status"] == "done"
    assert five["progress"] == 100
    assert five["branch"] == "feat/INT-005-repo-boilerplate"


# ---------------------------------------------------------------------------
# Hapus & tambah
# ---------------------------------------------------------------------------

def test_deleted_plan_task_stays_deleted_across_seed_and_refresh():
    assert tasks.delete_task("INT-020") is True
    assert tasks.get_task("INT-020") is None
    assert "INT-020" in tasks.tombstoned_ids(TRACK)

    again = tasks.seed_tasks(track=TRACK)
    assert "INT-020" not in again["created"]
    assert "INT-020" in again["deleted_kept"]
    assert tasks.get_task("INT-020") is None

    _force_refresh()
    assert tasks.get_task("INT-020") is None
    # task lain tetap utuh
    assert tasks.get_task("INT-021") is not None


def test_deleting_every_task_does_not_resurrect_the_board_on_boot():
    for t in tasks.list_tasks(track=TRACK):
        tasks.delete_task(t["id"])
    assert tasks.list_tasks(track=TRACK) == []
    assert tasks.seed_track_if_empty(TRACK) == []
    assert tasks.list_tasks(track=TRACK) == []


def test_restore_deleted_brings_plan_tasks_back_but_keeps_edits():
    tasks.update_task("INT-022", {"title": "Edit saya"})
    tasks.delete_task("INT-023")
    report = tasks.seed_tasks(track=TRACK, restore_deleted=True)
    assert report["created"] == ["INT-023"]
    assert tasks.get_task("INT-023") is not None
    assert tasks.tombstoned_ids(TRACK) == set()
    assert tasks.get_task("INT-022")["title"] == "Edit saya"


def test_reset_restores_everything_to_the_plan():
    tasks.update_task("INT-024", {"title": "Edit saya"})
    tasks.delete_task("INT-025")
    tasks.seed_tasks(reset=True, track=TRACK)
    assert tasks.get_task("INT-025") is not None
    assert tasks.get_task("INT-024")["title"] != "Edit saya"
    assert tasks.get_task("INT-024")["edited"] is False


def test_deleted_numbers_are_not_reused():
    top = internship_plan.TASKS[-1]["id"]
    tasks.delete_task(top)
    created = tasks.create_task(title="Task baru", track=TRACK, phase="i5")
    assert created["id"] != top
    assert int(created["id"][4:]) > int(top[4:])


def test_handmade_task_delete_leaves_no_tombstone():
    mine = tasks.create_task(title="Sementara", track=TRACK, phase="i0")
    assert tasks.delete_task(mine["id"]) is True
    assert mine["id"] not in tasks.tombstoned_ids(TRACK)


def test_recreating_a_deleted_id_clears_its_tombstone():
    tasks.delete_task("INT-026")
    tasks.create_task(title="Buat ulang", track=TRACK, phase="i4",
                      task_id="INT-026")
    assert "INT-026" not in tasks.tombstoned_ids(TRACK)


# ---------------------------------------------------------------------------
# Lewat API (yang dipakai UI)
# ---------------------------------------------------------------------------

def test_api_edit_add_delete_roundtrip(client):
    # tambah
    created = client.post("/api/tasks", json={
        "title": "Tambahan dari UI", "track": TRACK, "phase": "i1",
        "workflow": [{"actor": "Intern", "action": "Kerjakan", "result": "Selesai"}],
        "wireframe": "kotak", "evidence": ["ai-assistant-prototype/x.py"],
    }).json()["task"]
    assert created["workflow"][0]["action"] == "Kerjakan"
    assert created["wireframe"] == "kotak"

    # sunting task rencana: labels, workflow, wireframe, evidence, prasyarat
    patched = client.patch("/api/tasks/INT-018", json={
        "labels": ["internship", "ui"], "depends_on": ["INT-011"],
        "evidence": ["ai-assistant-prototype/a.tsx"], "wireframe": "baru",
        "workflow": [{"actor": "Intern", "action": "Langkah satu", "result": "ok"},
                     {"actor": "", "action": "Langkah dua", "result": ""}],
    }).json()["task"]
    assert patched["edited"] is True
    assert [w["action"] for w in patched["workflow"]] == ["Langkah satu", "Langkah dua"]
    assert patched["labels"] == ["internship", "ui"]
    assert patched["depends_on"] == ["INT-011"]

    # hapus + pastikan tak kembali setelah seed/refresh
    assert client.delete("/api/tasks/INT-019").status_code == 200
    client.post("/api/tasks/seed", params={"track": TRACK})
    _force_refresh()
    ids = {t["id"] for t in client.get("/api/tasks", params={"track": TRACK}
                                       ).json()["tasks"]}
    assert "INT-019" not in ids
    assert created["id"] in ids
    assert client.get("/api/tasks/INT-018").json()["task"]["wireframe"] == "baru"

    # pulihkan yang dihapus lewat API
    restored = client.post("/api/tasks/seed", params={
        "track": TRACK, "restore_deleted": True}).json()
    assert "INT-019" in restored["created"]


def test_seed_endpoint_targets_the_requested_board(client):
    """Reset di papan internship tidak boleh menyentuh papan platform."""
    platform_before = {t["id"] for t in client.get(
        "/api/tasks", params={"track": "platform"}).json()["tasks"]}
    client.post("/api/tasks/seed", params={"track": TRACK, "reset": True})
    platform_after = {t["id"] for t in client.get(
        "/api/tasks", params={"track": "platform"}).json()["tasks"]}
    assert platform_before == platform_after


def test_legacy_database_gets_edited_column_and_tombstone_table():
    assert ("tasks", "edited", "INTEGER NOT NULL DEFAULT 0") in db._MIGRATIONS
    assert db.query_one(
        "SELECT name FROM sqlite_master WHERE name='task_tombstones'")
