"""Sesi login + dependency FastAPI untuk peran (admin / member).

Alur: `POST /api/auth/login` memverifikasi kredensial (`users.authenticate`),
membuat baris di tabel `sessions`, lalu menaruh token di cookie **HttpOnly**
(`ask_session`, SameSite=Lax). Semua endpoint aplikasi membaca cookie itu —
tidak ada token di localStorage, jadi XSS di frontend tidak bisa mencuri sesi.

Dua mode (`ASK_AUTH_MODE`):
  * `required` (default) — request tanpa sesi ditolak 401; UI mengarahkan ke
    halaman `/login`.
  * `open` — tanpa login (dipakai test otomatis & demo cepat); setiap request
    diperlakukan sebagai admin anonim sehingga perilaku lama tidak berubah.

Role yang tersedia: `admin` (semua endpoint, semua mode/tool) dan `member`
(playground + task yang ditugaskan; tanpa model offline & tanpa setelan
provider — lihat `governance.py`).
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status

from . import db, users
from .config import settings

#: Principal pengganti saat `ASK_AUTH_MODE=open` (tanpa login).
ANONYMOUS_ADMIN: dict[str, Any] = {
    "id": "", "username": "anon", "name": "Mode terbuka", "role": "admin",
    "active": True, "anonymous": True,
}

_lock = threading.Lock()
#: username → daftar timestamp percobaan login gagal (throttle in-memory).
_ATTEMPTS: dict[str, list[float]] = {}
_ATTEMPT_WINDOW = 300.0


# ---------------------------------------------------------------------------
# Sesi (tabel `sessions`)
# ---------------------------------------------------------------------------

def cookie_name() -> str:
    return (settings.session_cookie or "ask_session").strip() or "ask_session"


def create_session(user_id: str, *, user_agent: str = "") -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    now = db.now()
    ttl = max(1, int(settings.session_hours or 168)) * 3600
    with _lock:
        db.execute(
            "INSERT INTO sessions(token,user_id,created_at,expires_at,last_seen,"
            "user_agent) VALUES(?,?,?,?,?,?)",
            (token, user_id, now, now + ttl, now, (user_agent or "")[:200]),
        )
        # Pangkas sesi kedaluwarsa sekalian (tabel tetap kecil tanpa cron).
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return {"token": token, "expires_at": now + ttl, "user_id": user_id}


def resolve_session(token: str | None) -> dict[str, Any] | None:
    """Token → user aktif. Sesi kedaluwarsa/nonaktif dihapus & dianggap gagal."""
    token = (token or "").strip()
    if not token:
        return None
    row = db.query_one("SELECT * FROM sessions WHERE token=?", (token,))
    if not row:
        return None
    if float(row["expires_at"]) < db.now():
        destroy_session(token)
        return None
    user = users.get_user(row["user_id"])
    if not user or not user["active"]:
        destroy_session(token)
        return None
    db.execute("UPDATE sessions SET last_seen=? WHERE token=?", (db.now(), token))
    return user


def destroy_session(token: str | None) -> bool:
    token = (token or "").strip()
    if not token:
        return False
    row = db.query_one("SELECT token FROM sessions WHERE token=?", (token,))
    if not row:
        return False
    db.execute("DELETE FROM sessions WHERE token=?", (token,))
    return True


def destroy_user_sessions(user_id: str) -> int:
    rows = db.query_all("SELECT token FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return len(rows)


def active_sessions(user_id: str) -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM sessions WHERE user_id=? AND expires_at > ?",
        (user_id, db.now()))
    return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Throttle login (anti brute-force sederhana, tanpa Redis)
# ---------------------------------------------------------------------------

def attempts_blocked(key: str) -> float:
    """Sisa detik blokir untuk `key` (0 = boleh mencoba)."""
    limit = int(settings.login_max_attempts or 0)
    if limit <= 0:
        return 0.0
    now = time.time()
    with _lock:
        hits = [t for t in _ATTEMPTS.get(key, []) if now - t < _ATTEMPT_WINDOW]
        _ATTEMPTS[key] = hits
        if len(hits) < limit:
            return 0.0
        return max(0.0, _ATTEMPT_WINDOW - (now - min(hits)))


def note_login_failure(key: str) -> None:
    with _lock:
        _ATTEMPTS.setdefault(key, []).append(time.time())


def clear_login_failures(key: str) -> None:
    with _lock:
        _ATTEMPTS.pop(key, None)


# ---------------------------------------------------------------------------
# Dependency FastAPI
# ---------------------------------------------------------------------------

def _token_from(request: Request) -> str:
    """Cookie sesi, atau `Authorization: Bearer <token>` untuk skrip/CLI."""
    token = request.cookies.get(cookie_name()) if request.cookies else None
    if token:
        return token
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def optional_user(request: Request) -> dict[str, Any] | None:
    """User dari sesi bila ada; `None` bila tidak login (tanpa melempar)."""
    return resolve_session(_token_from(request))


def current_principal(request: Request) -> dict[str, Any]:
    """Dependency utama seluruh endpoint aplikasi.

    Mode `required`: 401 bila tidak ada sesi valid (UI → halaman /login).
    Mode `open`: request tanpa sesi diperlakukan sebagai admin anonim.
    """
    user = optional_user(request)
    if user is not None:
        return user
    if not settings.auth_required():
        return dict(ANONYMOUS_ADMIN)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Login diperlukan. Buka /login untuk masuk.",
    )


def require_admin_principal(
    principal: dict[str, Any] = Depends(current_principal),
) -> dict[str, Any]:
    """Endpoint khusus admin (konsol admin, setelan provider, model offline)."""
    if users.is_admin(principal):
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Halaman/aksi ini hanya untuk role admin.",
    )


def admin_header_token_ok(x_admin_token: str | None) -> bool:
    """Header `X-Admin-Token` legacy (skrip/CLI) — masih didukung."""
    expected = (getattr(settings, "admin_token", "") or "").strip()
    return bool(expected) and (x_admin_token or "") == expected


def require_admin(
    x_admin_token: str | None = Header(default=None),
    principal: dict[str, Any] | None = Depends(optional_user),
) -> dict[str, Any]:
    """Guard konsol admin — menerima **sesi admin** atau `X-Admin-Token`.

    Urutan (penting untuk kompatibilitas):
      1. `X-Admin-Token` cocok dengan `ASK_ADMIN_TOKEN` → boleh (skrip lama),
      2. sesi login dengan role admin → boleh,
      3. `ASK_AUTH_MODE=open` → boleh sebagai admin anonim (demo/test),
      4. selebihnya: 401 bila belum login, 403 bila login tapi bukan admin.
    """
    expected = (getattr(settings, "admin_token", "") or "").strip()
    if expected:
        # Konsol dilindungi token (perilaku lama dipertahankan): header benar
        # → boleh; sesi admin juga diterima supaya UI tidak perlu token lagi.
        if admin_header_token_ok(x_admin_token):
            return dict(ANONYMOUS_ADMIN, username="admin-token",
                        name="Token admin")
        if principal is not None and users.is_admin(principal):
            return principal
        raise HTTPException(
            status_code=401,
            detail="Token admin salah/absen — isi X-Admin-Token atau login sebagai admin.",
        )
    if principal is not None:
        if users.is_admin(principal):
            return principal
        raise HTTPException(status_code=403,
                            detail="Halaman/aksi ini hanya untuk role admin.")
    if not settings.auth_required():
        return dict(ANONYMOUS_ADMIN)
    raise HTTPException(status_code=401,
                        detail="Login admin diperlukan. Buka /login untuk masuk.")


def admin_console_state(x_admin_token: str | None = None) -> dict[str, Any]:
    """Info untuk UI: konsol terlindungi token? token yang dikirim valid?"""
    expected = (getattr(settings, "admin_token", "") or "").strip()
    return {
        "token_required": bool(expected),
        "token_ok": admin_header_token_ok(x_admin_token) if expected else True,
        "auth_mode": settings.auth_mode,
    }


def capabilities(user: dict[str, Any] | None) -> dict[str, Any]:
    """Ringkasan izin peran — dipakai UI untuk menampilkan/menyembunyikan."""
    role = (user or {}).get("role") or "member"
    from . import governance  # impor lokal: hindari siklus impor modul

    pol = governance.role_policy(role)
    return {
        "role": role,
        "is_admin": role == "admin",
        "dashboard": "/admin" if role == "admin" else "/",
        "modes": pol.get("modes", {}),
        "tools": pol.get("tools", {}),
        "allow_offline_models": bool(pol.get("allow_offline_models")),
        "allow_provider_settings": bool(pol.get("allow_provider_settings")),
        "allow_admin_console": bool(pol.get("allow_admin_console")),
        "allow_rag_upload": bool(pol.get("allow_rag_upload")),
        "allow_task_write": bool(pol.get("allow_task_write")),
        "tasks_scope": pol.get("tasks_scope", "assigned"),
        "chat_provider": pol.get("chat_provider", "openai"),
    }


def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    """User untuk dikirim ke browser (tanpa hash password, plus izin)."""
    if user is None:
        return None
    out = {k: v for k, v in user.items() if k != "password_hash"}
    out["capabilities"] = capabilities(user)
    return out
