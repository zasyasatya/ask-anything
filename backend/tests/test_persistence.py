"""Persistensi storage: satu direktori data, penanda boot, gerbang peringatan.

Gejala yang dicegah: redeploy mengganti container, direktori data ternyata
bukan mount, dan seluruh database (termasuk password hasil reset) hilang
tanpa pesan apa pun.
"""
from __future__ import annotations

import json

from app import persistence, startup
from app.config import Settings, settings


# ---------------------------------------------------------------------------
# Satu variabel (ASK_DATA_DIR) menentukan letak SEMUA state
# ---------------------------------------------------------------------------

def test_data_dir_drives_every_storage_path(tmp_path):
    # `_env_file=None` + field kosong: hasilnya murni dari data_dir, tidak
    # tercampur .env milik mesin dev yang menjalankan test.
    s = Settings(_env_file=None, data_dir=str(tmp_path / "srv"),
                 db_path="", artifacts_dir="", rag_dir="")
    assert s.resolved_data_dir() == tmp_path / "srv"
    assert s.resolved_db_path() == tmp_path / "srv" / "ask_anything.db"
    assert s.resolved_artifacts_dir() == tmp_path / "srv" / "artifacts"
    assert s.resolved_rag_dir() == tmp_path / "srv" / "rag"
    assert s.resolved_backups_dir() == tmp_path / "srv" / "backups"


def test_explicit_paths_still_win(tmp_path):
    """Deployment lama yang menyetel ASK_DB_PATH dkk. tidak boleh berubah."""
    s = Settings(_env_file=None, data_dir=str(tmp_path / "srv"),
                 db_path=str(tmp_path / "lain" / "x.db"),
                 rag_dir=str(tmp_path / "arsip"), artifacts_dir="")
    assert s.resolved_db_path() == tmp_path / "lain" / "x.db"
    assert s.resolved_rag_dir() == tmp_path / "arsip"
    # yang dibiarkan kosong tetap ikut data_dir
    assert s.resolved_artifacts_dir() == tmp_path / "srv" / "artifacts"


# ---------------------------------------------------------------------------
# Penanda boot = bukti data selamat lintas redeploy
# ---------------------------------------------------------------------------

def test_marker_counts_boots_in_the_same_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "db_path", "")   # kosong = ikut data_dir

    assert persistence.touch_marker()["boots"] == 1
    assert persistence.touch_marker()["boots"] == 2

    saved = json.loads((tmp_path / "data" / persistence.MARKER_NAME)
                       .read_text(encoding="utf-8"))
    assert saved["boots"] == 2
    assert saved["db_path"].endswith("ask_anything.db")


def test_report_flags_ephemeral_container_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "in_container", lambda: True)
    monkeypatch.setattr(persistence, "is_mounted", lambda _p: False)

    rep = persistence.report()
    assert rep["persistent"] is False
    assert "HILANG setiap redeploy" in rep["warning"]


def test_report_is_quiet_when_data_dir_is_mounted(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "in_container", lambda: True)
    monkeypatch.setattr(persistence, "is_mounted", lambda _p: True)

    rep = persistence.report()
    assert rep["persistent"] is True
    assert rep["warning"] == ""
    assert rep["writable"] is True


def test_unwritable_data_dir_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "_writable", lambda _p: False)

    assert "tidak bisa ditulis" in persistence.report()["warning"]


def test_check_at_startup_records_a_note_for_ephemeral_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "in_container", lambda: True)
    monkeypatch.setattr(persistence, "is_mounted", lambda _p: False)
    monkeypatch.delenv("ASK_ALLOW_EPHEMERAL_DATA", raising=False)
    startup.clear()

    persistence.check_at_startup()

    notes = [n for n in startup.notes() if n["component"] == "storage"]
    assert notes and "redeploy" in notes[0]["message"]
    startup.clear()


def test_ephemeral_opt_in_silences_the_note(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "in_container", lambda: True)
    monkeypatch.setattr(persistence, "is_mounted", lambda _p: False)
    monkeypatch.setenv("ASK_ALLOW_EPHEMERAL_DATA", "1")
    startup.clear()

    persistence.check_at_startup()

    assert [n for n in startup.notes() if n["component"] == "storage"] == []
    startup.clear()


# ---------------------------------------------------------------------------
# Backup: salinan konsisten + pemangkasan
# ---------------------------------------------------------------------------

def test_backup_now_copies_live_database_and_prunes(monkeypatch, tmp_path):
    import sqlite3

    data = tmp_path / "data"
    data.mkdir()
    db_file = data / "ask_anything.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE t(x TEXT)")
    conn.execute("INSERT INTO t VALUES ('password-baru')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "data_dir", str(data))
    monkeypatch.setattr(settings, "db_path", "")

    first = persistence.backup_now()
    assert first.exists()
    restored = sqlite3.connect(first).execute("SELECT x FROM t").fetchone()
    assert restored[0] == "password-baru"

    for i in range(4):
        (data / "backups" / f"ask_anything-2020010{i}-000000.db").write_bytes(b"x")
    persistence.backup_now(keep=2)
    assert len(persistence.list_backups(limit=50)) == 2


# ---------------------------------------------------------------------------
# API: status ikut /api/health dan konsol admin
# ---------------------------------------------------------------------------

def test_health_reports_storage(client):
    body = client.get("/api/health").json()
    assert body["storage"]["data_dir"]
    assert "persistent" in body["storage"]
    assert "boots" in body["storage"]


def test_admin_storage_endpoint(client):
    body = client.get("/api/admin/storage").json()
    assert body["storage"]["db_path"].endswith(".db")
    assert isinstance(body["backups"], list)


def test_admin_backup_endpoint_creates_a_copy(client):
    body = client.post("/api/admin/storage/backup").json()
    assert body["ok"] is True
    assert body["backup"].endswith(".db")
    assert any(b["path"] == body["backup"] for b in body["backups"])
