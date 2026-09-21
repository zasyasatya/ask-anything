"""Admin API — mengatur pipeline (policy), memori, artifact, feedback, **user**.

Auth (dua jalur, lihat `app/auth.py`):
  1. **sesi login** dengan role `admin` (halaman /login) — jalur normal, dan
  2. header `X-Admin-Token` bila `ASK_ADMIN_TOKEN` diset (skrip/CLI).
Bila `ASK_ADMIN_TOKEN` **diset**, header itu wajib (perilaku lama dipertahankan);
sesi admin tetap diterima. Bila tidak diset dan `ASK_AUTH_MODE=open` (demo/test),
konsol terbuka. Governance untuk end-user tetap ditegakkan di server.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator

from .. import artifacts, auth, db, feedback, governance, memory, users
from ..config import settings

#: Guard konsol admin (sesi admin ATAU header X-Admin-Token) — satu sumber di
#: `auth.require_admin`, dipakai juga oleh /api/tasks/*.
require_admin = auth.require_admin

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

@router.get("/policy")
async def get_policy() -> dict:
    return {"policy": governance.policy()}


@router.put("/policy")
async def put_policy(patch: dict[str, dict[str, Any]]) -> dict:
    return {"policy": governance.update_policy(patch)}


# ---------------------------------------------------------------------------
# Overview (dashboard ringkas)
# ---------------------------------------------------------------------------

@router.get("/overview")
async def overview(
    x_admin_token: str | None = Header(default=None),
) -> dict:
    counts = db.stats_counts()
    return {
        "counts": counts,
        "feedback": feedback.stats(),
        "policy": governance.policy(),
        "provider": settings.provider,
        "model": settings.active_model_label(),
        "admin_protected": bool((settings.admin_token or "").strip()),
        "auth": {**auth.admin_console_state(x_admin_token),
                 "auth_mode": settings.auth_mode,
                 "login_required": settings.auth_required()},
        "users": db.query_one("SELECT COUNT(*) AS n FROM users"),
    }


# ---------------------------------------------------------------------------
# Users — kelola akun & peran (admin | member), reset password, tugas
# ---------------------------------------------------------------------------

class UserIn(BaseModel):
    username: str
    password: str
    name: str = ""
    role: str = "member"
    active: bool = True
    must_change_password: bool = False


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    must_change_password: bool | None = None


class PasswordReset(BaseModel):
    password: str
    must_change_password: bool = True


@router.get("/users")
async def list_users() -> dict:
    """Daftar akun + jumlah task yang ditugaskan (untuk penugasan intern)."""
    items = users.list_users()
    row = db.query_all(
        "SELECT assignee, COUNT(*) AS n, "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done "
        "FROM tasks WHERE assignee<>'' GROUP BY assignee")
    counts = {(r["assignee"] or "").lower(): r for r in row}
    for user in items:
        key = (user["username"] or "").lower()
        stats = counts.get(key) or {}
        user["tasks_total"] = int(stats.get("n") or 0)
        user["tasks_done"] = int(stats.get("done") or 0)
        user["sessions"] = auth.active_sessions(user["id"])
    return {"users": items, "roles": list(users.ROLES),
            "role_labels": dict(users.ROLE_LABELS),
            "auth": auth.admin_console_state()}


@router.post("/users")
async def create_user(item: UserIn) -> dict:
    try:
        user = users.create_user(**item.model_dump())
    except users.UserError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"user": user, "users": users.list_users()}


@router.patch("/users/{user_id}")
async def patch_user(user_id: str, patch: UserPatch) -> dict:
    try:
        user = users.update_user(user_id, patch.model_dump(exclude_none=True))
    except users.UserError as exc:
        raise HTTPException(400, str(exc)) from exc
    if user is None:
        raise HTTPException(404, "user tidak ditemukan")
    return {"user": user, "users": users.list_users()}


@router.post("/users/{user_id}/password")
async def reset_password(user_id: str, item: PasswordReset) -> dict:
    """Reset password user (admin). Semua sesi user itu diputus."""
    try:
        user = users.set_password(user_id, item.password,
                                  must_change=item.must_change_password)
    except users.UserError as exc:
        raise HTTPException(400, str(exc)) from exc
    if user is None:
        raise HTTPException(404, "user tidak ditemukan")
    auth.destroy_user_sessions(user_id)
    return {"user": user, "users": users.list_users(), "sessions_revoked": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict:
    try:
        removed = users.delete_user(user_id)
    except users.UserError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not removed:
        raise HTTPException(404, "user tidak ditemukan")
    return {"ok": True, "users": users.list_users()}


# ---------------------------------------------------------------------------
# Memory management
# ---------------------------------------------------------------------------

class MemoryIn(BaseModel):
    scope: str = "global"
    key: str = ""
    content: str
    enabled: bool = True

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("content tidak boleh kosong")
        return v


class MemoryPatch(BaseModel):
    scope: str | None = None
    key: str | None = None
    content: str | None = None
    enabled: bool | None = None


@router.get("/memories")
async def list_memories() -> dict:
    return {"memories": memory.list_memories()}


@router.post("/memories")
async def create_memory(item: MemoryIn) -> dict:
    return memory.add_memory(**item.model_dump())


@router.patch("/memories/{mid}")
async def patch_memory(mid: str, patch: MemoryPatch) -> dict:
    out = memory.update_memory(mid, patch.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404, "memori tidak ditemukan")
    return out


@router.delete("/memories/{mid}")
async def remove_memory(mid: str) -> dict:
    if not memory.delete_memory(mid):
        raise HTTPException(404, "memori tidak ditemukan")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

@router.get("/artifacts")
async def list_artifacts(kind: str | None = None, limit: int = 200) -> dict:
    return {"artifacts": artifacts.list_artifacts(kind=kind, limit=limit)}


@router.delete("/artifacts/{aid}")
async def delete_artifact(aid: str) -> dict:
    if not artifacts.delete_artifact(aid, settings=settings):
        raise HTTPException(404, "artifact tidak ditemukan")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackPatch(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in feedback.STATUSES:
            raise ValueError(f"status harus salah satu dari: {', '.join(feedback.STATUSES)}")
        return v


@router.get("/feedback")
async def list_feedback(status: str | None = None, limit: int = 200) -> dict:
    return {"feedback": feedback.list_feedback(status=status, limit=limit),
            "stats": feedback.stats()}


@router.patch("/feedback/{fid}")
async def patch_feedback(fid: str, patch: FeedbackPatch) -> dict:
    out = feedback.set_status(fid, patch.status)
    if not out:
        raise HTTPException(404, "feedback tidak ditemukan")
    return out


@router.post("/feedback/{fid}/apply")
async def apply_feedback(fid: str) -> dict:
    try:
        return feedback.apply_feedback(fid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/feedback/{fid}")
async def delete_feedback(fid: str) -> dict:
    if not feedback.delete_feedback(fid):
        raise HTTPException(404, "feedback tidak ditemukan")
    return {"ok": True}
