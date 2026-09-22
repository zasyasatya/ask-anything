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

from .. import (artifacts, auth, db, feedback, governance, instructions,
                memory, persistence, quota, users)
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
        "quota": quota.overview(),
        "instructions": instructions.stats(),
        "auth": {**auth.admin_console_state(x_admin_token),
                 "auth_mode": settings.auth_mode,
                 "login_required": settings.auth_required()},
        "users": db.query_one("SELECT COUNT(*) AS n FROM users"),
    }


# ---------------------------------------------------------------------------
# Pipeline instruksi advanced (playbook domain + teori cara menjawab)
# ---------------------------------------------------------------------------

class PlaybookIn(BaseModel):
    name: str
    domain: str = ""
    persona: str = ""
    method: str = ""
    theory: str = ""
    rules: str = ""
    output_format: str = ""
    triggers: list[str] = []
    modes: list[str] = []
    activation: str = "keywords"
    priority: int = 100
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("name tidak boleh kosong")
        return v

    @field_validator("activation")
    @classmethod
    def _known_activation(cls, v: str) -> str:
        if v not in instructions.ACTIVATIONS:
            raise ValueError("activation harus salah satu dari: "
                             + ", ".join(instructions.ACTIVATIONS))
        return v

    @field_validator("theory")
    @classmethod
    def _known_theory(cls, v: str) -> str:
        value = (v or "").strip().lower()
        if value and value not in instructions.THEORIES:
            raise ValueError("teori tidak dikenal; lihat GET "
                             "/api/admin/instructions/theories")
        return value


class PlaybookPatch(BaseModel):
    name: str | None = None
    domain: str | None = None
    persona: str | None = None
    method: str | None = None
    theory: str | None = None
    rules: str | None = None
    output_format: str | None = None
    triggers: list[str] | None = None
    modes: list[str] | None = None
    activation: str | None = None
    priority: int | None = None
    enabled: bool | None = None


@router.get("/instructions")
async def list_instructions() -> dict:
    """Daftar playbook + statistik pemakaian nyata + katalog teori."""
    return {
        "playbooks": instructions.list_playbooks(),
        "stats": instructions.stats(),
        "theories": instructions.theory_catalog(),
        "activations": instructions.recent_activations(limit=100),
        "policy": governance.policy()["instructions"],
    }


@router.get("/instructions/theories")
async def list_theories() -> dict:
    return {"theories": instructions.theory_catalog()}


@router.post("/instructions")
async def create_playbook(item: PlaybookIn) -> dict:
    try:
        return instructions.add_playbook(**item.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/instructions/{pid}")
async def patch_playbook(pid: str, patch: PlaybookPatch) -> dict:
    try:
        out = instructions.update_playbook(
            pid, patch.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not out:
        raise HTTPException(404, "playbook tidak ditemukan")
    return out


@router.delete("/instructions/{pid}")
async def remove_playbook(pid: str) -> dict:
    if not instructions.delete_playbook(pid):
        raise HTTPException(404, "playbook tidak ditemukan")
    return {"ok": True}


class PlaybookPreview(BaseModel):
    message: str
    mode: str = "text"
    playbook_ids: list[str] | None = None


@router.post("/instructions/preview")
async def preview_playbooks(body: PlaybookPreview) -> dict:
    """Uji pemicu tanpa memanggil model: playbook mana yang akan menyala?

    Ini yang membuat pipeline bisa *dikelola*: admin bisa memverifikasi kata
    pemicu sebelum dilepas ke pengguna, alih-alih menebak.
    """
    block, selected = instructions.prompt_block(
        body.message, mode=body.mode,
        policy_instructions=governance.policy()["instructions"],
        playbook_ids=body.playbook_ids,
    )
    return {"block": block, "selected": selected, "count": len(selected)}


# ---------------------------------------------------------------------------
# Pipeline kuota token (monitoring + manage per end user)
# ---------------------------------------------------------------------------

class QuotaLimitIn(BaseModel):
    """Override batas untuk satu end user.

    `None` = ikut policy global, `0` = tanpa batas untuk dimensi itu.
    """

    daily_tokens: int | None = None
    weekly_tokens: int | None = None
    daily_requests: int | None = None
    note: str = ""

    @field_validator("daily_tokens", "weekly_tokens", "daily_requests")
    @classmethod
    def _not_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("batas tidak boleh negatif (0 = tanpa batas)")
        return v


@router.get("/quota")
async def quota_dashboard(limit: int = 200) -> dict:
    """Monitoring pipeline kuota: agregat, daftar user, dan penolakan."""
    return {
        "overview": quota.overview(),
        "users": quota.list_users(limit=limit),
        "rejections": quota.list_rejections(limit=100),
    }


@router.get("/quota/users/{user_key}")
async def quota_user(user_key: str) -> dict:
    return {"status": quota.status(user_key),
            "override": quota.get_override(user_key)}


@router.put("/quota/users/{user_key}")
async def quota_set_limit(user_key: str, body: QuotaLimitIn) -> dict:
    quota.touch_user(user_key)
    limits = quota.set_override(user_key, **body.model_dump())
    return {"ok": True, "limits": limits, "status": quota.status(user_key)}


@router.delete("/quota/users/{user_key}")
async def quota_clear_limit(user_key: str) -> dict:
    """Hapus override → user kembali mengikuti policy global."""
    return {"ok": quota.clear_override(user_key),
            "status": quota.status(user_key)}


@router.post("/quota/users/{user_key}/reset")
async def quota_reset(user_key: str, scope: str = "day") -> dict:
    if scope not in ("day", "week", "all"):
        raise HTTPException(422, "scope harus day, week, atau all")
    removed = quota.reset_user(user_key, scope=scope)
    return {"ok": True, "scope": scope, "removed_rows": removed,
            "status": quota.status(user_key)}


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
    email: str = ""


class UserPatch(BaseModel):
    name: str | None = None
    email: str | None = None
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
# Storage / persistence (kenapa data bisa "hilang" setelah redeploy)
# ---------------------------------------------------------------------------

@router.get("/storage")
async def storage_status() -> dict:
    """Kondisi direktori data: mount point, writable, sisa disk, backup.

    Dipakai untuk memastikan reset password & data transaksi benar-benar
    mendarat di disk server, bukan di lapisan tulis container yang terhapus
    tiap redeploy.
    """
    return {"storage": persistence.report(),
            "backups": persistence.list_backups()}


@router.post("/storage/backup")
async def storage_backup() -> dict:
    """Backup SQLite sekarang juga (selain backup otomatis tiap start)."""
    try:
        path = persistence.backup_now()
    except OSError as exc:
        raise HTTPException(500, f"backup gagal: {exc}") from exc
    return {"ok": True, "backup": str(path),
            "backups": persistence.list_backups()}


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
