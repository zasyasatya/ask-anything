"""Akun pengguna & peran (login page: role **admin** dan **member**).

Modul ini hanya menangani *identitas*: siapa boleh masuk, dengan peran apa,
dan bagaimana password disimpan. Aturan tentang apa yang boleh dilakukan tiap
peran ada di `governance.py` (policy per-role) dan ditegakkan di route/agent —
bukan di sini.

Penyimpanan password
--------------------
`hashlib.pbkdf2_hmac("sha256", …, iterations=210_000)` + salt acak per user,
format `pbkdf2_sha256$<iterasi>$<salt-b64>$<hash-b64>`. Tidak ada dependensi
baru (bcrypt/argon2) karena hashing stdlib sudah cukup untuk prototipe internal
dan tetap aman bila parameternya naik (iterasi dibaca dari hash tersimpan,
jadi password lama tetap bisa diverifikasi setelah parameter dinaikkan).

Akun awal
---------
Tabel `users` kosong → `ensure_seed_users()` membuat satu admin
(`ASK_ADMIN_PASSWORD`, default `admin123`) dan akun member contoh dari
`ASK_SEED_MEMBERS` (default `intern1,intern2,intern3`, password
`ASK_MEMBER_PASSWORD`, default `intern123`). Semua password awal **wajib**
diganti di deployment nyata — halaman Profil & konsol Admin → Users.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from typing import Any

from . import db

#: Peran yang dikenal. `admin` = konsol admin + semua mode/tool; `member` =
#: playground dengan batasan dari policy per-role (tanpa model offline).
ROLES: tuple[str, ...] = ("admin", "member")
ROLE_LABELS: dict[str, str] = {"admin": "Admin", "member": "Member"}

#: Panjang minimum password (dicek di API & UI).
MIN_PASSWORD = 6
#: Parameter PBKDF2 (iterasi dibaca dari hash tersimpan saat verifikasi).
_PBKDF2_ITERATIONS = 210_000
_ALGO = "pbkdf2_sha256"


class UserError(ValueError):
    """Kesalahan yang aman ditampilkan ke pengguna (→ HTTP 400)."""


# ---------------------------------------------------------------------------
# Password hashing (stdlib)
# ---------------------------------------------------------------------------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def hash_password(password: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    if not password:
        raise UserError("password tidak boleh kosong")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGO}${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(stored: str, password: str) -> bool:
    """Perbandingan waktu-tetap; hash rusak/format lama → False (bukan crash)."""
    try:
        algo, iters, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", (password or "").encode(), _unb64(salt_b64), int(iters)
        )
        return hmac.compare_digest(digest, _unb64(hash_b64))
    except (ValueError, TypeError, base64.binascii.Error):
        return False


def normalise_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_username(username: str) -> str:
    name = normalise_username(username)
    if len(name) < 3:
        raise UserError("username minimal 3 karakter")
    if len(name) > 32:
        raise UserError("username maksimal 32 karakter")
    if not all(c.isalnum() or c in "._-" for c in name):
        raise UserError("username hanya boleh huruf, angka, titik, strip, underscore")
    return name


def validate_password(password: str) -> str:
    if not password or len(password) < MIN_PASSWORD:
        raise UserError(f"password minimal {MIN_PASSWORD} karakter")
    if len(password) > 200:
        raise UserError("password terlalu panjang")
    return password


# ---------------------------------------------------------------------------
# Baris DB → dict publik (hash password TIDAK pernah keluar dari modul ini)
# ---------------------------------------------------------------------------

def _row(row: dict[str, Any]) -> dict[str, Any]:
    user = dict(row)
    user.pop("password_hash", None)
    user["role"] = user.get("role") if user.get("role") in ROLES else "member"
    user["active"] = bool(user.get("active"))
    user["must_change_password"] = bool(user.get("must_change_password"))
    user["role_label"] = ROLE_LABELS.get(user["role"], user["role"])
    return user


def is_admin(user: dict[str, Any] | None) -> bool:
    return bool(user and user.get("role") == "admin" and user.get("active"))


# ---------------------------------------------------------------------------
# Baca
# ---------------------------------------------------------------------------

def list_users() -> list[dict]:
    rows = db.query_all("SELECT * FROM users ORDER BY role, username")
    return [_row(r) for r in rows]


def get_user(user_id: str) -> dict | None:
    row = db.query_one("SELECT * FROM users WHERE id=?", (user_id or "",))
    return _row(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    row = db.query_one(
        "SELECT * FROM users WHERE username=? COLLATE NOCASE",
        (normalise_username(username),),
    )
    return _row(row) if row else None


def count_admins(*, exclude_id: str = "") -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM users WHERE role='admin' AND active=1 AND id<>?",
        (exclude_id or "",),
    )
    return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Tulis
# ---------------------------------------------------------------------------

def create_user(
    *,
    username: str,
    password: str,
    name: str = "",
    role: str = "member",
    active: bool = True,
    must_change_password: bool = False,
) -> dict:
    uname = validate_username(username)
    validate_password(password)
    if role not in ROLES:
        raise UserError(f"role harus salah satu dari: {', '.join(ROLES)}")
    if get_user_by_username(uname):
        raise UserError(f"username '{uname}' sudah dipakai")
    uid = f"u-{uuid.uuid4().hex[:10]}"
    ts = db.now()
    db.execute(
        "INSERT INTO users(id,username,name,role,password_hash,active,"
        "must_change_password,created_at,updated_at,last_login) "
        "VALUES(?,?,?,?,?,?,?,?,?,0)",
        (uid, uname, (name or "").strip()[:80] or uname, role,
         hash_password(password), 1 if active else 0,
         1 if must_change_password else 0, ts, ts),
    )
    return get_user(uid) or {}


def update_user(user_id: str, patch: dict[str, Any]) -> dict | None:
    """Ubah nama/peran/status aktif. Password **tidak** diubah di sini."""
    user = get_user(user_id)
    if not user:
        return None
    fields: list[str] = []
    params: list[Any] = []

    if patch.get("name") is not None:
        fields.append("name=?")
        params.append(str(patch["name"]).strip()[:80] or user["username"])
    if patch.get("role") is not None:
        role = str(patch["role"]).strip().lower()
        if role not in ROLES:
            raise UserError(f"role harus salah satu dari: {', '.join(ROLES)}")
        if user["role"] == "admin" and role != "admin" and count_admins(exclude_id=user_id) == 0:
            raise UserError("tidak bisa menurunkan admin terakhir — buat admin lain dulu")
        fields.append("role=?")
        params.append(role)
    if patch.get("active") is not None:
        active = bool(patch["active"])
        if not active and user["role"] == "admin" and count_admins(exclude_id=user_id) == 0:
            raise UserError("tidak bisa menonaktifkan admin terakhir")
        fields.append("active=?")
        params.append(1 if active else 0)
    if patch.get("must_change_password") is not None:
        fields.append("must_change_password=?")
        params.append(1 if patch["must_change_password"] else 0)

    if not fields:
        return user
    fields.append("updated_at=?")
    params.append(db.now())
    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", tuple(params))
    return get_user(user_id)


def set_password(user_id: str, password: str, *,
                 must_change: bool = False) -> dict | None:
    validate_password(password)
    if not get_user(user_id):
        return None
    db.execute(
        "UPDATE users SET password_hash=?, must_change_password=?, updated_at=? "
        "WHERE id=?",
        (hash_password(password), 1 if must_change else 0, db.now(), user_id),
    )
    return get_user(user_id)


def delete_user(user_id: str) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    if user["role"] == "admin" and count_admins(exclude_id=user_id) == 0:
        raise UserError("tidak bisa menghapus admin terakhir")
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    return True


def verify_user_password(user_id: str, password: str) -> bool:
    """Cek password user tanpa pernah mengeluarkan hash dari modul ini.

    `get_user()` sengaja membuang `password_hash`; fungsi inilah jalur resmi
    untuk memverifikasi password user yang sudah login (Profil → ganti password).
    """
    row = db.query_one("SELECT password_hash FROM users WHERE id=?", (user_id or "",))
    return bool(row) and verify_password(row["password_hash"], password or "")


def authenticate(username: str, password: str) -> dict | None:
    """Verifikasi kredensial. `None` bila salah/nonaktif (pesan seragam)."""
    uname = normalise_username(username)
    row = db.query_one(
        "SELECT * FROM users WHERE username=? COLLATE NOCASE", (uname,))
    if not row:
        # Tetap lakukan satu hash agar waktu respons tidak membocorkan
        # apakah username-nya ada (timing side channel sederhana).
        verify_password(
            "pbkdf2_sha256$1000$AAAA$AAAA", password or "")
        return None
    if not verify_password(row["password_hash"], password or ""):
        return None
    if not bool(row["active"]):
        return None
    db.execute("UPDATE users SET last_login=?, updated_at=? WHERE id=?",
               (db.now(), db.now(), row["id"]))
    return get_user(row["id"])


def ensure_seed_users(settings) -> dict[str, Any]:
    """Buat akun awal saat tabel `users` kosong (idempoten)."""
    existing = db.query_one("SELECT COUNT(*) AS n FROM users")
    if existing and int(existing["n"]) > 0:
        return {"created": [], "skipped": True}

    created: list[dict] = []
    admin = create_user(
        username=settings.admin_username or "admin",
        password=settings.admin_password or "admin123",
        name=settings.admin_name or "Administrator",
        role="admin",
        must_change_password=False,
    )
    created.append({"username": admin["username"], "role": "admin"})

    for username in settings.seed_member_usernames():
        try:
            member = create_user(
                username=username,
                password=settings.member_password or "intern123",
                name=username,
                role="member",
            )
        except UserError:
            continue
        created.append({"username": member["username"], "role": "member"})
    return {"created": created, "skipped": False}


def default_credentials(settings) -> list[dict[str, str]]:
    """Kredensial awal untuk ditampilkan di halaman login (mode demo saja)."""
    out = [{"username": settings.admin_username or "admin",
            "role": "admin",
            "password": settings.admin_password or "admin123"}]
    for username in settings.seed_member_usernames():
        out.append({"username": username, "role": "member",
                    "password": settings.member_password or "intern123"})
    return out


def bootstrap_state(settings) -> dict[str, Any]:
    """Info akun awal yang aman ditampilkan di halaman login.

    Hanya di mode `open`/demo (tanpa login) kredensial awal ikut dikirim;
    di mode `required` halaman login hanya mengatakan siapa yang membuat akun.
    """
    row = db.query_one("SELECT COUNT(*) AS n FROM users")
    count = int(row["n"]) if row else 0
    out: dict[str, Any] = {
        "users": count,
        "seeded": count == 0,
        "auth_mode": (settings.auth_mode or "required"),
        "demo": not settings.auth_required(),
        "min_password": MIN_PASSWORD,
    }
    if out["demo"]:
        out["credentials"] = default_credentials(settings)
    return out
