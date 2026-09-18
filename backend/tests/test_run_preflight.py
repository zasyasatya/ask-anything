"""Preflight `run.py`: backend diperiksa **sebelum** dijalankan.

Sebelumnya run.py hanya memastikan `import fastapi, uvicorn, httpx, bs4` lalu
menjalankan uvicorn; kalau aplikasinya sendiri gagal di-import (paket opsional
hilang, route bentrok), hasilnya cuma "backend did not become healthy" tanpa
petunjuk. Test ini menjaga preflight + penerjemahan log yang baru.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.test_run_installer import _load_run_module


@pytest.fixture()
def run_mod():
    return _load_run_module()


def test_pip_module_map_covers_optional_packages(run_mod):
    for module in ("multipart", "pptx", "pypdf", "bs4", "pydantic_settings"):
        assert module in run_mod.PIP_FOR_MODULE


def test_probe_backend_app_reports_broken_app(run_mod, tmp_path, monkeypatch):
    """Backend tiruan yang impornya rusak harus terdeteksi preflight."""
    backend = tmp_path / "backend"
    (backend / "app").mkdir(parents=True)
    (backend / "app" / "__init__.py").write_text("", encoding="utf-8")
    (backend / "app" / "main.py").write_text(
        "import paket_yang_tidak_pernah_ada_xyz  # sengaja\n",
        encoding="utf-8")
    monkeypatch.setattr(run_mod, "BACKEND", backend)

    probe = run_mod.probe_backend_app(run_mod.venv_python())
    assert probe.returncode != 0
    assert "ModuleNotFoundError" in (probe.stderr or "")


def test_probe_backend_app_accepts_real_app(run_mod):
    probe = run_mod.probe_backend_app(run_mod.venv_python())
    assert probe.returncode == 0, probe.stderr


def test_core_module_probe_finds_missing_feature_package(run_mod, monkeypatch):
    """Paket fitur (mis. python-multipart) terdeteksi walau app tetap importable."""
    monkeypatch.setattr(run_mod, "CORE_MODULES",
                        ("fastapi", "paket_yang_tidak_pernah_ada_xyz"))
    missing = run_mod.missing_core_modules(run_mod.venv_python())
    assert missing == ["paket_yang_tidak_pernah_ada_xyz"]


def test_ensure_backend_features_reports_missing(run_mod, monkeypatch):
    """Modul hilang → dicoba dipasang, lalu dilaporkan bila tetap tidak ada."""
    calls: list[list[str]] = []

    monkeypatch.setattr(run_mod, "missing_core_modules",
                        lambda py: [] if calls else ["multipart"])
    monkeypatch.setattr(run_mod.subprocess, "run",
                        lambda cmd, *a, **kw: calls.append(list(cmd)))

    run_mod.ensure_backend_features(run_mod.venv_python())
    assert any("python-multipart" in " ".join(c) for c in calls)


def test_log_tail_reads_last_lines(run_mod, tmp_path, monkeypatch):
    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "backend.log").write_text(
        "\n".join(f"baris {i}" for i in range(50)), encoding="utf-8")
    tail = run_mod.log_tail("backend", lines=3)
    assert tail.splitlines() == ["baris 47", "baris 48", "baris 49"]
    assert "belum ada" in run_mod.log_tail("frontend")
    assert run_mod.show_failure("backend", "demo") is None


@pytest.mark.parametrize("snippet,expected", [
    ("ERROR: [Errno 10048] error while attempting to bind on address",
     "--backend-port"),
    ("Form data requires \"python-multipart\" to be installed", "install-only"),
    ("OSError: [WinError 1114] ... c10.dll", "--install-local"),
    ("ModuleNotFoundError: No module named 'pptx'", "install-only"),
    ("sqlite3.OperationalError: database is locked", "ASK_DB_PATH"),
])
def test_backend_start_failure_hint_translates_log(run_mod, tmp_path, monkeypatch,
                                                    snippet, expected):
    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "backend.log").write_text(snippet, encoding="utf-8")
    hint = run_mod.backend_start_failure_hint(8000)
    assert expected in hint


def test_health_warnings_formats_backend_notes(run_mod):
    payload = {"status": "ok", "warnings": [
        {"component": "autoloader", "message": "torch rusak", "hint": "install-local"},
        {"component": "x", "message": "", "hint": "diabaikan"},
    ]}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # senyap saat test
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        notes = run_mod.health_warnings(
            f"http://127.0.0.1:{server.server_port}/api/health")
    finally:
        server.shutdown()
    assert notes == ["torch rusak → install-local"]
    assert run_mod.health_warnings("http://127.0.0.1:1/api/health") == []
