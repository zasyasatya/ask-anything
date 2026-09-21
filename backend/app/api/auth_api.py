"""API login (`/api/auth/*`) — halaman /login, sesi cookie, ganti password.

Endpoint di sini adalah satu-satunya bagian `/api` yang **tidak** memerlukan
sesi (kecuali `/me` & `/password`) — kalau tidak, tidak akan ada cara untuk
masuk. Cookie sesi bersifat HttpOnly + SameSite=Lax sehingga token tidak
pernah bisa dibaca JavaScript (aman dari XSS), dan frontend cukup mengirim
`credentials: same-origin` (default untuk fetch same-origin).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import auth, users
from ..config import settings

router = APIRouter(prefix="/api/auth")


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    #: Wajib untuk ganti password sendiri; admin boleh melewatkannya saat reset.
    current_password: str = ""
    new_password: str = Field(min_length=1)


class ProfileIn(BaseModel):
    name: str | None = None


def _client_key(request: Request, username: str) -> str:
    host = (request.client.host if request.client else "") or "-"
    return f"{users.normalise_username(username)}|{host}"


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        key=auth.cookie_name(),
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=bool(settings.cookie_secure),
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=auth.cookie_name(), path="/")


# ---------------------------------------------------------------------------
# Info akun awal (dipakai halaman login untuk menampilkan petunjuk)
# ---------------------------------------------------------------------------

@router.get("/bootstrap")
async def bootstrap() -> dict[str, Any]:
    """Apakah sudah ada akun? Kredensial awal hanya dikirim di mode demo."""
    return users.bootstrap_state(settings)


@router.get("/me")
async def me(request: Request) -> dict[str, Any]:
    user = auth.optional_user(request)
    if user is None:
        if settings.auth_required():
            raise HTTPException(401, "Belum login")
        return {"user": None, "auth_mode": settings.auth_mode,
                "anonymous": True,
                "capabilities": auth.capabilities(auth.ANONYMOUS_ADMIN)}
    return {"user": auth.public_user(user), "auth_mode": settings.auth_mode,
            "anonymous": False}


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(item: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    username = (item.username or "").strip()
    if not username or not item.password:
        raise HTTPException(400, "Username dan password wajib diisi")

    key = _client_key(request, username)
    blocked = auth.attempts_blocked(key)
    if blocked > 0:
        raise HTTPException(
            429,
            f"Terlalu banyak percobaan login. Coba lagi dalam {int(blocked // 60) + 1} menit.",
        )

    user = users.authenticate(username, item.password)
    if user is None:
        auth.note_login_failure(key)
        # Pesan seragam: tidak membocorkan apakah username-nya ada.
        raise HTTPException(401, "Username atau password salah")
    if not user["active"]:
        raise HTTPException(403, "Akun ini dinonaktifkan. Hubungi admin.")

    auth.clear_login_failures(key)
    session = auth.create_session(
        user["id"], user_agent=request.headers.get("user-agent") or "")
    ttl = max(1, int(settings.session_hours or 168)) * 3600
    _set_session_cookie(response, session["token"], ttl)
    return {
        "user": auth.public_user(user),
        "expires_at": session["expires_at"],
        "auth_mode": settings.auth_mode,
    }


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, Any]:
    token = request.cookies.get(auth.cookie_name()) if request.cookies else ""
    auth.destroy_session(token)
    _clear_session_cookie(response)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Profil & password (user sendiri)
# ---------------------------------------------------------------------------

@router.post("/password")
async def change_password(
    item: PasswordIn, request: Request, response: Response
) -> dict[str, Any]:
    user = auth.optional_user(request)
    if user is None:
        raise HTTPException(401, "Login diperlukan")
    if not item.current_password:
        raise HTTPException(400, "Password lama wajib diisi")
    if not users.verify_user_password(user["id"], item.current_password):
        raise HTTPException(403, "Password lama salah")
    try:
        users.set_password(user["id"], item.new_password)
    except users.UserError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Password berubah → semua sesi lain diputus, lalu sesi ini dibuat ulang.
    auth.destroy_user_sessions(user["id"])
    session = auth.create_session(
        user["id"], user_agent=request.headers.get("user-agent") or "")
    _set_session_cookie(response, session["token"],
                        max(1, int(settings.session_hours or 168)) * 3600)
    return {"ok": True, "user": auth.public_user(users.get_user(user["id"]))}


@router.patch("/profile")
async def update_profile(item: ProfileIn, request: Request) -> dict[str, Any]:
    user = auth.optional_user(request)
    if user is None:
        raise HTTPException(401, "Login diperlukan")
    patch = {k: v for k, v in item.model_dump().items() if v is not None}
    if not patch:
        return {"ok": True, "user": auth.public_user(user)}
    updated = users.update_user(user["id"], patch)
    return {"ok": True, "user": auth.public_user(updated)}
