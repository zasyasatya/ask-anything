"""Admin API — mengatur pipeline (policy), memori, artifact, feedback.

Auth: bila env `ASK_ADMIN_TOKEN` diset, semua endpoint /api/admin/* mewajibkan
header `X-Admin-Token` yang cocok. Bila kosong (default, mode lokal/demo),
endpoint terbuka — governance tetap ditegakkan di server untuk *end-user*,
token ini hanya untuk melindungi konsol admin di deployment publik.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator

from .. import (artifacts, db, feedback, governance, instructions, memory,
                quota)
from ..config import settings

router = APIRouter(prefix="/api/admin")


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = (getattr(settings, "admin_token", "") or "").strip()
    if not expected:
        return  # mode lokal/demo: konsol terbuka, enforcement tetap server-side
    if (x_admin_token or "") != expected:
        raise HTTPException(status_code=401, detail="Token admin salah/absen")


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
async def overview() -> dict:
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
