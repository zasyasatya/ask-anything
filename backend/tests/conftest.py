import os
import sys
import tempfile

os.environ["ASK_PROVIDER"] = "mock"
# Test lama mengakses API tanpa login → mode terbuka (tiap request = admin).
# Tes yang memang menguji login/role memakai fixture `strict_auth` di bawah,
# yang menyalakan kembali mode "required".
os.environ["ASK_AUTH_MODE"] = "open"
os.environ["ASK_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="askanything_test_"), "test.db"
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _forget_payload_memory():
    """Providers remember which payload rung a server accepted; tests must not."""
    from app.providers import OpenAIProtocolProvider

    OpenAIProtocolProvider.reset_payload_memory()
    yield
    OpenAIProtocolProvider.reset_payload_memory()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Login & role (dipakai tests/test_auth.py + test_internship_board.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def strict_auth(monkeypatch):
    """Nyalakan mode login wajib (`ASK_AUTH_MODE=required`) untuk tes ini."""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_mode", "required")
    monkeypatch.setattr(settings, "admin_token", "")
    yield settings


@pytest.fixture()
def make_user():
    """Buat akun unik per tes (username berbasis uuid agar tidak bentrok)."""
    from app import users

    def _make(role: str = "member", password: str = "rahasia123",
              name: str = "") -> dict:
        suffix = uuid.uuid4().hex[:6]
        return users.create_user(
            username=f"{role}-{suffix}", password=password,
            name=name or f"{role} {suffix}", role=role)

    return _make


@pytest.fixture()
def login(client):
    """Login pada client utama → sesi (cookie) aktif untuk request berikutnya."""
    def _login(username: str, password: str = "rahasia123"):
        res = client.post("/api/auth/login",
                          json={"username": username, "password": password})
        assert res.status_code == 200, res.text
        return res.json()

    return _login


@pytest.fixture()
def new_client():
    """Client tambahan (mis. admin & member login bersamaan)."""
    from fastapi.testclient import TestClient

    from app.main import app

    opened: list = []

    def _new():
        c = TestClient(app)
        c.__enter__()
        opened.append(c)
        return c

    yield _new
    for c in opened:
        c.__exit__(None, None, None)
