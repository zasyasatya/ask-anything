"""Backend harus hidup walau sub-sistem opsional gagal.

Konteks bug nyata: `torch` rusak (Windows `OSError WinError 1114` pada
`torch\\lib\\c10.dll`) atau `python-multipart` tidak ter-install membuat proses
uvicorn mati saat startup. Gejalanya di `run.py` cuma "backend did not become
healthy" — tanpa sebab. Test ini mengunci perilaku barunya:

  * autoload model berjalan di background & kegagalannya cuma dicatat,
  * folder model yang tidak bisa dibuat tidak mematikan server,
  * route upload multipart absen → 503 yang menjelaskan, bukan crash saat import,
  * `/api/health` selalu membalas dan memuat `warnings` + `autoload`.
"""
import time

import pytest
from fastapi import HTTPException

from app import startup
from app.api import routes


def test_health_reports_warnings_and_autoload(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert isinstance(data["warnings"], list)
    assert set(data["autoload"]) >= {"state", "detail"}


def test_startup_notes_are_recorded_and_clearable():
    startup.clear()
    note = startup.add("demo", "  ada   masalah\nbaris dua ", hint="lakukan X")
    assert note["message"] == "ada masalah baris dua"
    assert note["hint"] == "lakukan X"
    assert startup.notes()[-1]["component"] == "demo"
    startup.clear()
    assert startup.notes() == []


def test_models_dir_failure_is_a_note_not_a_crash(monkeypatch, tmp_path, client):
    """Folder model gagal dibuat (mis. path menunjuk ke sebuah berkas) → server
    tetap start, masalahnya tercatat & terlihat di /api/health."""
    from app import main

    blocker = tmp_path / "models-is-a-file"
    blocker.write_text("bukan folder", encoding="utf-8")
    monkeypatch.setattr(main.settings, "models_dir", str(blocker / "sub"))
    startup.clear()

    main._init_storage()          # tidak boleh melempar

    notes = startup.notes()
    assert any(n["component"] == "storage" for n in notes), notes


def test_db_failure_has_actionable_message(monkeypatch):
    from app import db, main

    def boom(_path):
        raise OSError("database is locked")

    monkeypatch.setattr(db, "init_db", boom)
    with pytest.raises(RuntimeError) as exc:
        main._init_storage()
    message = str(exc.value)
    assert "SQLite" in message and "ASK_DB_PATH" in message
    assert "locked" in message


def test_autoload_failure_only_records_a_note(monkeypatch):
    """Kegagalan tak terduga saat autoload tidak boleh mematikan startup."""
    from app import main

    startup.clear()

    def boom():
        raise OSError("[WinError 1114] c10.dll initialization failed")

    monkeypatch.setattr(main, "_autoload_local_model", boom)
    main._run_autoload_in_background()      # tidak melempar

    deadline = time.time() + 5
    while time.time() < deadline and not startup.notes():
        time.sleep(0.02)
    assert main.AUTOLOAD_STATE["state"] == "error"
    assert any(n["component"] == "autoloader" for n in startup.notes())


def test_autoload_skips_when_torch_missing(monkeypatch):
    from app import main

    startup.clear()
    monkeypatch.setattr(main.settings, "provider", "huggingface")
    monkeypatch.setattr(main.settings, "hf_mode", "local")
    monkeypatch.setattr(main, "_deps", lambda: {
        "available": False, "install_hint": "pasang torch dulu"})
    main._autoload_local_model()
    assert main.AUTOLOAD_STATE["state"] == "unavailable"
    assert startup.notes()[-1]["component"] == "autoloader"


def test_rag_upload_route_is_registered(client):
    """Dengan python-multipart terpasang: endpoint asli (validasi multipart)."""
    names = {r.path for r in routes.router.routes}
    assert any(p.endswith("/rag/upload") for p in names), names
    r = client.post("/api/rag/upload")
    assert r.status_code in (422, 503)      # 422 = tanpa berkas, 503 = fallback


async def test_rag_upload_fallback_message_is_actionable():
    """Versi 503 (dipakai saat python-multipart absen) menyebut cara memperbaiki."""
    with pytest.raises(HTTPException) as exc:
        await routes.rag_upload_unavailable()
    assert exc.value.status_code == 503
    assert "python-multipart" in exc.value.detail
    assert "run.py" in exc.value.detail
