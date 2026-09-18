"""API task management (`/api/tasks/*`) — papan kerja rencana RAG.

Semua endpoint memakai pengaman yang sama dengan konsol admin: bila env
`ASK_ADMIN_TOKEN` diset, header `X-Admin-Token` wajib (lihat `admin.require_admin`).
Di mode lokal/demo (tanpa token) papan terbuka supaya developer bisa langsung
memakainya.

Task id (`ASK-NNN`) adalah kunci yang dipakai nama branch GitLab, jadi:
  * `GET  /api/tasks/{id}` memuat `branch_name` + `git_command` siap salin,
  * `POST /api/tasks/sync` menyelaraskan status dari branch/commit & berkas kode.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import tasks
from .admin import require_admin

router = APIRouter(prefix="/api/tasks", dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Skema input
# ---------------------------------------------------------------------------

class TaskIn(BaseModel):
    title: str
    description: str = ""
    phase: str = "f0"
    status: str = "todo"
    priority: str = "medium"
    assignee: str = ""
    estimate: float = 0
    labels: list[str] = Field(default_factory=list)
    acceptance: list[Any] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    source: str = ""
    task_id: str = ""
    branch: str = ""


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    phase: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    estimate: float | None = None
    labels: list[str] | None = None
    acceptance: list[Any] | None = None
    depends_on: list[str] | None = None
    evidence: list[str] | None = None
    source: str | None = None
    branch: str | None = None
    mr_url: str | None = None


class MoveIn(BaseModel):
    status: str
    before_id: str | None = None


class CommentIn(BaseModel):
    body: str
    author: str = "dev"


class AcceptanceIn(BaseModel):
    """Aksi checklist: toggle index, tambah teks baru, atau hapus index."""

    index: int | None = None
    done: bool | None = None
    text: str | None = None
    remove: bool = False


def _guard(exc: Exception) -> HTTPException:
    return HTTPException(400, str(exc))


# ---------------------------------------------------------------------------
# Koleksi
# ---------------------------------------------------------------------------

@router.get("")
async def list_tasks(
    status: str | None = None,
    phase: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    label: str | None = None,
    q: str | None = None,
    seeded: bool | None = None,
) -> dict:
    items = tasks.list_tasks(status=status, phase=phase, assignee=assignee,
                             priority=priority, label=label, q=q, seeded=seeded)
    return {
        "tasks": items,
        "stats": tasks.stats(),
        "plan": tasks.plan(),
        "statuses": list(tasks.STATUSES),
        "repo": str(tasks.project_root()),
    }


@router.get("/plan")
async def get_plan() -> dict:
    return tasks.plan()


@router.post("")
async def create_task(item: TaskIn) -> dict:
    try:
        task = tasks.create_task(**item.model_dump())
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    return {"task": task, "stats": tasks.stats()}


@router.post("/seed")
async def seed(reset: bool = Query(default=False)) -> dict:
    """Muat ulang rencana RAG (idempoten kecuali `reset=true`)."""
    report = tasks.seed_tasks(reset=reset)
    return {**report, "stats": tasks.stats()}


@router.post("/sync")
async def sync(silent: bool = Query(default=False)) -> dict:
    """Selaraskan papan dengan kode & git (branch/commit menyebut ASK-NNN)."""
    report = tasks.sync(silent=silent)
    return {**report, "tasks": tasks.list_tasks(), "stats": tasks.stats()}


# ---------------------------------------------------------------------------
# Satu task
# ---------------------------------------------------------------------------

@router.get("/{task_id}")
async def get_task(task_id: str) -> dict:
    task = tasks.task_detail(task_id)
    if not task:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": task}


@router.patch("/{task_id}")
async def patch_task(task_id: str, patch: TaskPatch) -> dict:
    try:
        task = tasks.update_task(task_id, patch.model_dump(exclude_none=True))
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not task:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": task, "stats": tasks.stats()}


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict:
    if not tasks.delete_task(task_id):
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"ok": True, "stats": tasks.stats()}


@router.post("/{task_id}/move")
async def move_task(task_id: str, body: MoveIn) -> dict:
    try:
        task = tasks.move_task(task_id, body.status, body.before_id)
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not task:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": task, "tasks": tasks.list_tasks(), "stats": tasks.stats()}


@router.post("/{task_id}/comments")
async def add_comment(task_id: str, item: CommentIn) -> dict:
    try:
        comment = tasks.add_comment(task_id, item.body, author=item.author)
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    return {"comment": comment, "comments": tasks.list_comments(task_id)}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str) -> dict:
    if not tasks.delete_comment(comment_id):
        raise HTTPException(404, "komentar tidak ditemukan")
    return {"ok": True}


@router.post("/{task_id}/acceptance")
async def acceptance(task_id: str, body: AcceptanceIn) -> dict:
    try:
        if body.text:
            task = tasks.add_acceptance(task_id, body.text)
        elif body.remove:
            if body.index is None:
                raise tasks.TaskError("index kriteria wajib diisi")
            task = tasks.remove_acceptance(task_id, body.index)
        else:
            if body.index is None:
                raise tasks.TaskError("index kriteria wajib diisi")
            task = tasks.set_acceptance(task_id, body.index, bool(body.done))
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not task:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": task, "stats": tasks.stats()}
