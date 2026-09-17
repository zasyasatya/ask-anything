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

from .. import artifacts, db, feedback, governance, memory
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
    }


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
