"""API task management (`/api/tasks/*`) — papan kerja platform & internship.

Akses mengikuti **peran** (lihat `governance.roles` + `auth.current_principal`):

  * **admin** — semua papan, semua aksi (buat/ubah/pindah/hapus/seed/sync).
    Bisa juga memakai header `X-Admin-Token` seperti sebelumnya.
  * **member** — hanya task yang **ditugaskan kepadanya** (`tasks_scope=assigned`
    default): boleh membaca, mengomentari, mencentang kriteria selesai, dan
    memindahkan status task-nya sendiri (bila `allow_task_write=true`);
    membuat/menghapus task, seed, dan sinkronisasi git tetap khusus admin.

Task id (`ASK-NNN` / `INT-NNN`) adalah kunci yang dipakai nama branch GitLab,
jadi tiap task memuat `branch_name` + `git_command` siap salin.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import governance, tasks
from ..auth import current_principal, require_admin

router = APIRouter(prefix="/api/tasks")


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
    track: str = ""


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
# Cakupan peran
# ---------------------------------------------------------------------------

def _scope_names(principal: dict[str, Any]) -> list[str] | None:
    """Nama penanggung jawab yang boleh dilihat.

    `None` = tidak dibatasi (admin / `tasks_scope=all`).
    """
    role = (principal or {}).get("role") or "member"
    if role == "admin":
        return None
    if governance.role_setting(role, "tasks_scope", "assigned") == "all":
        return None
    names = [(principal or {}).get("username") or "",
             (principal or {}).get("name") or ""]
    return [n for n in names if n]


def _task_in_scope(task: dict[str, Any], principal: dict[str, Any]) -> bool:
    names = _scope_names(principal)
    if names is None:
        return True
    return (task.get("assignee") or "").strip().lower() in {
        n.lower() for n in names}


def _require_in_scope(task: dict[str, Any] | None, principal: dict[str, Any]) -> dict:
    if task is None:
        raise HTTPException(404, "task tidak ditemukan")
    if not _task_in_scope(task, principal):
        raise HTTPException(403, "Task ini bukan untuk Anda — minta admin "
                                 "menugaskannya bila memang untuk Anda.")
    return task


def _require_task_write(principal: dict[str, Any]) -> None:
    role = (principal or {}).get("role") or "member"
    if role == "admin":
        return
    if not governance.role_allows(role, "allow_task_write"):
        raise HTTPException(403, "Role ini hanya bisa membaca papan task "
                                 "(ubah izin di Admin → Pipeline → Akses per peran).")


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
    track: str = Query(default="platform"),
    principal: dict[str, Any] = Depends(current_principal),
) -> dict:
    scope = _scope_names(principal)
    items = tasks.list_tasks(status=status, phase=phase, assignee=assignee,
                             priority=priority, label=label, q=q, seeded=seeded,
                             track=track, assignee_in=scope)
    return {
        "tasks": items,
        "stats": tasks.stats(track, assignee_in=scope),
        "plan": tasks.plan(track),
        "statuses": list(tasks.STATUSES),
        "repo": str(tasks.project_root()),
        "track": track,
        "tracks": list(tasks.TRACKS),
        "track_labels": dict(tasks.TRACK_LABELS),
        "scope": "all" if scope is None else "assigned",
        "me": {"username": (principal or {}).get("username", ""),
               "role": (principal or {}).get("role", "")},
    }


@router.get("/plan")
async def get_plan(track: str = Query(default="platform")) -> dict:
    return tasks.plan(track)


@router.post("", dependencies=[Depends(require_admin)])
async def create_task(item: TaskIn) -> dict:
    try:
        task = tasks.create_task(**item.model_dump())
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    return {"task": task, "stats": tasks.stats(task["track"])}


@router.post("/seed", dependencies=[Depends(require_admin)])
async def seed(reset: bool = Query(default=False),
               track: str = Query(default="platform")) -> dict:
    """Muat ulang rencana satu papan (idempoten kecuali `reset=true`)."""
    report = tasks.seed_tasks(reset=reset, track=track)
    return {**report, "stats": tasks.stats(report.get("track") or track)}


@router.post("/sync", dependencies=[Depends(require_admin)])
async def sync(silent: bool = Query(default=False),
               track: str = Query(default="platform")) -> dict:
    """Selaraskan papan dengan kode & git (branch/commit menyebut ASK/INT-NNN)."""
    report = tasks.sync(silent=silent)
    return {**report, "tasks": tasks.list_tasks(track=track),
            "stats": tasks.stats(track)}


# ---------------------------------------------------------------------------
# Satu task
# ---------------------------------------------------------------------------

@router.get("/{task_id}")
async def get_task(task_id: str,
                   principal: dict[str, Any] = Depends(current_principal)) -> dict:
    task = tasks.task_detail(task_id)
    if task is None:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    if not _task_in_scope(task, principal):
        raise HTTPException(403, "Task ini bukan untuk Anda.")
    task["can_write"] = (
        (principal or {}).get("role") == "admin"
        or governance.role_allows((principal or {}).get("role"), "allow_task_write")
    )
    return {"task": task}


@router.patch("/{task_id}")
async def patch_task(task_id: str, patch: TaskPatch,
                     principal: dict[str, Any] = Depends(current_principal)) -> dict:
    task = _require_in_scope(tasks.get_task(task_id), principal)
    _require_task_write(principal)
    values = patch.model_dump(exclude_none=True)
    role = (principal or {}).get("role") or "member"
    if role != "admin":
        # Member boleh memindahkan status & menandai kriteria, bukan mengubah
        # penugasan/prioritas/branch — itu keputusan admin.
        for field in ("assignee", "phase", "priority", "depends_on", "evidence",
                      "branch", "mr_url", "source", "estimate"):
            values.pop(field, None)
    try:
        updated = tasks.update_task(task["id"], values)
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not updated:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": updated, "stats": tasks.stats(updated["track"]),
            "scope": "all" if _scope_names(principal) is None else "assigned"}


@router.delete("/{task_id}", dependencies=[Depends(require_admin)])
async def delete_task(task_id: str) -> dict:
    if not tasks.delete_task(task_id):
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"ok": True, "stats": tasks.stats()}


@router.post("/{task_id}/move")
async def move_task(task_id: str, body: MoveIn,
                    principal: dict[str, Any] = Depends(current_principal)) -> dict:
    task = _require_in_scope(tasks.get_task(task_id), principal)
    _require_task_write(principal)
    try:
        updated = tasks.move_task(task["id"], body.status, body.before_id)
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not updated:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    scope = _scope_names(principal)
    return {"task": updated, "tasks": tasks.list_tasks(track=task["track"],
                                                       assignee_in=scope),
            "stats": tasks.stats(task["track"], assignee_in=scope)}


@router.post("/{task_id}/comments")
async def add_comment(task_id: str, item: CommentIn,
                      principal: dict[str, Any] = Depends(current_principal)) -> dict:
    task = _require_in_scope(tasks.get_task(task_id), principal)
    _require_task_write(principal)
    # Nama penulis mengikuti akun yang login (bukan input bebas) supaya
    # aktivitas papan bisa dipercaya.
    author = (principal or {}).get("name") or (principal or {}).get("username") \
        or item.author
    try:
        comment = tasks.add_comment(task["id"], item.body, author=author)
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    return {"comment": comment, "comments": tasks.list_comments(task_id)}


@router.delete("/comments/{comment_id}", dependencies=[Depends(require_admin)])
async def delete_comment(comment_id: str) -> dict:
    if not tasks.delete_comment(comment_id):
        raise HTTPException(404, "komentar tidak ditemukan")
    return {"ok": True}


@router.post("/{task_id}/acceptance")
async def acceptance(task_id: str, body: AcceptanceIn,
                     principal: dict[str, Any] = Depends(current_principal)) -> dict:
    task = _require_in_scope(tasks.get_task(task_id), principal)
    _require_task_write(principal)
    try:
        if body.text:
            updated = tasks.add_acceptance(task["id"], body.text)
        elif body.remove:
            if body.index is None:
                raise tasks.TaskError("index kriteria wajib diisi")
            updated = tasks.remove_acceptance(task["id"], body.index)
        else:
            if body.index is None:
                raise tasks.TaskError("index kriteria wajib diisi")
            updated = tasks.set_acceptance(task["id"], body.index, bool(body.done))
    except tasks.TaskError as exc:
        raise _guard(exc) from exc
    if not updated:
        raise HTTPException(404, f"task {task_id} tidak ditemukan")
    return {"task": updated, "stats": tasks.stats(updated["track"])}
