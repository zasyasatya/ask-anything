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

#: Task Sprint 0 lama yang dibekukan (selesai, isi tidak boleh berubah).
FROZEN = ("INT-001", "INT-002", "INT-003", "INT-004")


def _mutable_tasks():
    """Task yang ditulis ulang mengikuti PRD terbaru (di luar yang dibekukan)."""
    return [t for t in internship_plan.TASKS if t["id"] not in FROZEN]


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
        assert internship_plan.acceptance_text(task), (
            f"{task['id']} tanpa kriteria selesai")
        assert task["evidence"], f"{task['id']} tanpa berkas bukti"
        assert task["assignee"] in internship_plan.INTERNS, task
        # Setiap task harus cukup detail untuk dikerjakan tanpa bertanya lagi.
        assert len(task["description"]) > 120, f"{task['id']} deskripsi terlalu tipis"
        assert task["workflow"], f"{task['id']} tanpa alur kerja"
        assert task["wireframe"], f"{task['id']} tanpa wireframe/sketsa"
        for step in task["workflow"]:
            assert step["action"].strip(), f"{task['id']} punya langkah kosong"


def test_intern_plan_covers_prd_epics_and_stack():
    """Rencana harus memuat lima epic LLM + semua kemampuan PRD terbaru."""
    blob = " ".join(f"{t['title']} {t['description']} {t['source']}"
                    for t in internship_plan.TASKS).lower()
    for keyword in (
        # Epic 0 - produk
        "prd", "persona", "user story", "non-goal",
        # Epic 1 - konteks & memori
        "sesi", "token", "sliding window", "ringkas", "memori",
        # Epic 2 - orkestrasi & tooling
        "function calling", "json schema", "chunk", "embedding", "retrieval",
        "sitasi", "router", "pgvector", "docx", "graphview", "bar chart",
        # Epic 3 - guardrail
        "prompt injection", "pii", "redaksi", "validator",
        # Epic 4 - observability
        "trace", "ttft", "biaya", "feedback", "evaluasi",
        # Epic 5 - performa & rilis
        "cache", "rate limit", "fallback", "docker", "volume", "demo",
        # stack terkunci PRD bagian C + design system
        "next.js", "fastapi", "postgresql", "clean architecture", "sse",
        "beui", "lucide",
    ):
        assert keyword in blob, keyword
    phases = {t["phase"] for t in internship_plan.TASKS}
    assert phases == set(internship_plan.PHASE_IDS)


def _stories_mentioned(blob: str) -> set[int]:
    """Nomor user story yang disebut, termasuk bentuk daftar 'US-01,02,03'."""
    import re

    found: set[int] = set()
    for match in re.finditer(r"US-(\d{2})((?:\s*,\s*\d{2})*)", blob):
        found.add(int(match.group(1)))
        found.update(int(x) for x in re.findall(r"\d{2}", match.group(2)))
    return found


def test_every_prd_user_story_is_planned():
    """US-01..US-10 tiap-tiapnya disebut oleh minimal satu task."""
    blob = " ".join(
        f"{t['title']} {t['description']} {t['wireframe']} "
        f"{' '.join(internship_plan.acceptance_text(t))}"
        for t in internship_plan.TASKS)
    missing = set(range(1, 11)) - _stories_mentioned(blob)
    assert not missing, f"user story belum direncanakan: {sorted(missing)}"


def test_plan_follows_prd_stack_not_the_old_prototype():
    """Arsitektur mengikuti PRD bagian C: tidak ada infra di luar ADR.

    Kata terlarang boleh muncul di deskripsi sebagai penjelasan apa yang TIDAK
    dipakai; yang diuji adalah pekerjaan nyatanya (judul, kriteria, bukti).
    INT-001..004 dibekukan (Sprint 0 lama) dan dikecualikan.
    """
    blob = " ".join(
        f"{t['title']} {' '.join(internship_plan.acceptance_text(t))} "
        f"{' '.join(t['evidence'])}" for t in _mutable_tasks()).lower()
    for banned in ("streamlit", "sqlite", "milvus", "qdrant", "kafka",
                   "rabbitmq", "kubernetes", "langsmith", "redis", "mongodb"):
        assert banned not in blob, f"{banned} di luar ADR PRD bagian C"
    plan_blob = " ".join(f"{t['description']} {t['wireframe']}"
                         for t in _mutable_tasks()).lower()
    for expected in ("next.js", "fastapi", "postgresql", "pgvector", "beui",
                     "lucide", "alembic"):
        assert expected in plan_blob, expected


def test_plan_has_no_emoji_per_design_system():
    """Design system beUI: kebijakan nol emoji (ikon = lucide-react)."""
    import re

    emoji = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")
    for task in _mutable_tasks():
        text = " ".join([
            task["title"], task["description"], task["wireframe"],
            " ".join(internship_plan.acceptance_text(task)),
            " ".join(f"{w['actor']} {w['action']} {w['result']}"
                     for w in task["workflow"])])
        assert not emoji.search(text), f"{task['id']} memuat emoji"


def test_prd_numbers_are_carried_into_the_plan():
    """Angka kunci PRD bagian B/C muncul di task yang relevan."""
    by_id = {t["id"]: t for t in internship_plan.TASKS}

    def blob(task_id: str) -> str:
        t = by_id[task_id]
        return (f"{t['description']} {t['wireframe']} "
                f"{' '.join(internship_plan.acceptance_text(t))}")

    assert "8.192" in blob("INT-009") and "1.024" in blob("INT-009")
    assert "2.000" in blob("INT-019")                              # panjang input
    assert "0.7" in blob("INT-012") and "0.7" in blob("INT-021")   # ambang
    assert "Rp5,76" in blob("INT-024") and "Rp29,03" in blob("INT-024")
    assert "50 pesan" in blob("INT-028") and "100.000" in blob("INT-028")
    assert "20 soal" in blob("INT-026")


#: Task Sprint 2 yang sengaja ditarik lebih awal ke To do: pipeline RAG adalah
#: pekerjaan terdekat (INT-033 = payung, INT-011..013 = potongannya).
PULLED_FORWARD = ("INT-011", "INT-012", "INT-013", "INT-033")


def test_sprint_zero_is_done_and_later_sprints_wait_in_backlog():
    """Sprint 0 (PRD A-C + boilerplate) selesai; sprint lain menunggu di backlog,
    kecuali task pipeline RAG yang ditarik lebih awal ke To do."""
    for task in internship_plan.TASKS:
        if task["phase"] == "i0":
            assert task["status"] == "done", task["id"]
            assert all(a["done"] for a in task["acceptance"]), task["id"]
        elif task["id"] in PULLED_FORWARD:
            assert task["status"] == "todo", task["id"]
        else:
            assert task["status"] == "backlog", task["id"]
    sprint0 = internship_plan.by_phase("i0")
    assert [t["id"] for t in sprint0] == [
        "INT-001", "INT-002", "INT-003", "INT-004", "INT-005"]
    assert sum(1 for t in sprint0 if "prd" in t["title"].lower()) >= 3


def test_int_005_reflects_the_merged_boilerplate():
    task = next(t for t in internship_plan.TASKS if t["id"] == "INT-005")
    assert task["status"] == "done"
    assert task["branch"] == "feat/INT-005-repo-boilerplate"
    text = f"{task['title']} {task['description']}".lower()
    for keyword in ("clean architecture", "fastapi", "next.js", "beui",
                    "postgresql", "docker"):
        assert keyword in text, keyword


def test_every_task_carries_sprint_and_epic_label():
    epic_labels = {e["label"] for e in internship_plan.EPICS}
    for task in internship_plan.TASKS:
        sprint_label = internship_plan.SPRINT_LABELS[task["phase"]]
        assert sprint_label in task["labels"], task["id"]
        assert epic_labels & set(task["labels"]), f"{task['id']} tanpa label epic"


def test_acceptance_criteria_are_measurable():
    """Kriteria selesai harus berangka, bukan kata sifat."""
    for task in internship_plan.TASKS:
        items = internship_plan.acceptance_text(task)
        assert len(items) >= 4, task["id"]
        assert any(any(ch.isdigit() for ch in item) for item in items), (
            f"{task['id']} tidak punya kriteria berangka")


def test_plan_details_feedback_memory_and_quota_tasks():
    """Tiga pilar yang diminta harus punya task tersendiri yang detail."""
    joined = " ".join(f"{t['title']} {t['description']}".lower()
                      for t in internship_plan.TASKS)
    # feedback suka / tidak suka dengan alasan terstruktur (ikon lucide, bukan emoji)
    assert "tidak suka" in joined and "alasan" in joined
    assert "thumbsup" in joined and "thumbsdown" in joined
    # manajemen memori: ringkasan sesi + multi-turn
    assert "multi-turn" in joined and "ringkasan" in joined
    # kuota token per pengguna
    assert "kuota" in joined and "100.000 token" in joined


def test_every_sprint_has_at_least_three_tasks():
    per_phase = internship_plan.summary()["per_phase"]
    assert set(per_phase) == set(internship_plan.PHASE_IDS)
    for phase_id, count in per_phase.items():
        assert count >= 3, f"sprint {phase_id} hanya punya {count} task"


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
    from app import users

    _intern_board(client)
    intern = internship_plan.INTERNS[0]
    account = users.get_user_by_username(intern)
    assert account, "akun intern harus dibuat otomatis saat startup"
    # Password awalnya acak (hanya dicetak sekali) — set ulang untuk tes ini.
    users.set_password(account["id"], "rahasia123")
    res = client.post("/api/auth/login", json={
        "username": intern, "password": "rahasia123"})
    assert res.status_code == 200, res.text

    data = client.get("/api/internship/overview").json()
    assert data["scope"] == "assigned"
    assert data["tasks"], "task member harus terlihat"
    for task in data["tasks"]:
        assert task["assignee"].lower() == intern.lower()
    assert data["stats"]["total"] == len(data["tasks"])
    # Satu intern memegang seluruh papan; admin tetap bisa menugaskan ulang.
    assert data["stats"]["total"] == len(
        internship_plan.for_assignee(intern))


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


# ---------------------------------------------------------------------------
# Pembaruan rencana (revisi) — papan lama ikut naik versi tanpa kehilangan progres
# ---------------------------------------------------------------------------

def test_refresh_plan_keeps_progress_when_revision_changes(client):
    """Rencana ditulis ulang → papan diperbarui, status & centang bertahan."""
    client.post("/api/tasks/seed", params={"track": "internship"})
    db.execute("DELETE FROM admin_policy WHERE key=?",
               ("plan_revision:internship",))

    tasks.update_task("INT-007", {"status": "in_progress",
                                  "assignee": "verisimb",
                                  "branch": "feat/INT-007-autentikasi"})
    before = tasks.get_task("INT-007")
    first_criterion = before["acceptance"][0]["text"]
    tasks.update_task("INT-007", {"acceptance": [
        {"text": a["text"], "done": a["text"] == first_criterion}
        for a in before["acceptance"]]})

    report = tasks.refresh_plan_if_stale("internship")
    assert report["changed"] is True
    assert report["restored"] >= 1

    after = tasks.get_task("INT-007")
    assert after["status"] == "in_progress"
    assert after["branch"] == "feat/INT-007-autentikasi"
    assert {a["text"] for a in after["acceptance"] if a["done"]} == {
        first_criterion}
    assert len(tasks.list_tasks(track="internship", seeded=True)) == len(
        internship_plan.TASKS)

    # kedua kali: revisi sudah tersimpan → tidak ada pekerjaan ulang
    assert tasks.refresh_plan_if_stale("internship")["changed"] is False


def test_refresh_plan_leaves_handmade_tasks_alone(client):
    client.post("/api/tasks/seed", params={"track": "internship"})
    mine = tasks.create_task(title="Catatan saya sendiri", track="internship",
                             phase="i0")
    db.execute("DELETE FROM admin_policy WHERE key=?",
               ("plan_revision:internship",))
    tasks.refresh_plan_if_stale("internship")
    assert tasks.get_task(mine["id"]) is not None
