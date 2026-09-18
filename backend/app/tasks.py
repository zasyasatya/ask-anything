"""Task management — papan kerja developer (Jira/ClickUp-style, versi ringkas).

Satu modul memegang seluruh logika papan `/tasks`:

  * CRUD task + komentar/aktivitas,
  * pindah kolom (drag & drop) dengan penomoran posisi,
  * checklist kriteria selesai,
  * statistik progres per status/fase,
  * seeder rencana RAG (`tasks_plan.py`) yang idempoten,
  * **sinkronisasi git**: branch/commit yang memuat `ASK-NNN` menaikkan status
    task, dan berkas `evidence` yang sudah ada menandai task siap review.

Konvensi penting: `id` task (`ASK-012`) dipakai apa adanya di nama branch
GitLab (`feat/ASK-012-judul-singkat`) — lihat `branch_name()` dan
`git_command()`, keduanya ditampilkan di UI supaya developer tinggal salin.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from . import db
from .config import PROJECT_ROOT, settings
from .tasks_plan import (
    PHASES,
    PHASE_IDS,
    PRIORITIES,
    STATUSES,
    STATUS_LABELS,
    TASKS as PLAN_TASKS,
    summary as plan_summary,
)

TASK_ID_RE = re.compile(r"\bASK-(\d{3,4})\b", re.IGNORECASE)
#: status yang menandakan pekerjaan sudah dianggap selesai (untuk auto-done).
DONE_KEYWORDS = ("close", "closes", "closed", "fix", "fixes", "fixed",
                 "done", "selesai", "merge")
#: batas panjang teks agar payload API & UI tetap ringan.
MAX_COMMENT = 4000


class TaskError(ValueError):
    """Kesalahan yang aman ditampilkan ke pengguna (→ HTTP 400)."""


# ---------------------------------------------------------------------------
# Utilitas kecil
# ---------------------------------------------------------------------------

def _rank(status: str) -> int:
    return STATUSES.index(status) if status in STATUSES else 1


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    try:
        out = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return out if isinstance(out, type(fallback)) else fallback


def _row(row: dict[str, Any]) -> dict[str, Any]:
    """Baris DB → dict task dengan field JSON yang sudah diparse."""
    task = dict(row)
    task["labels"] = [str(x) for x in _loads(task.get("labels"), [])]
    task["depends_on"] = [str(x) for x in _loads(task.get("depends_on"), [])]
    task["commits"] = _loads(task.get("commits"), [])
    acceptance = _loads(task.get("acceptance"), [])
    task["acceptance"] = [
        {"text": str(a.get("text", "")), "done": bool(a.get("done"))}
        if isinstance(a, dict) else {"text": str(a), "done": False}
        for a in acceptance
    ]
    task["evidence"] = [str(x) for x in _loads(task.get("evidence"), [])]
    task["seeded"] = bool(task.get("seeded"))
    task["branch_name"] = branch_name(task)
    task["git_command"] = f"git checkout -b {task['branch_name']}"
    task["acceptance_done"] = sum(1 for a in task["acceptance"] if a["done"])
    task["acceptance_total"] = len(task["acceptance"])
    task["progress"] = (
        round(100 * task["acceptance_done"] / task["acceptance_total"])
        if task["acceptance_total"] else (100 if task["status"] == "done" else 0)
    )
    return task


def slugify(text: str, max_len: int = 42) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].strip("-") or "task"


def branch_name(task: dict[str, Any]) -> str:
    """Nama branch yang disarankan: `feat/ASK-012-judul-singkat`."""
    prefix = {"bug": "fix", "bugfix": "fix", "docs": "docs",
              "test": "test", "testing": "test",
              "performance": "perf"}.get(
        next((l for l in task.get("labels", []) if l in
              ("bug", "bugfix", "docs", "test", "testing", "performance")),
             ""), "feat")
    return f"{prefix}/{task['id'].upper()}-{slugify(task.get('title', ''))}"


def git_command(task: dict[str, Any]) -> str:
    return f"git checkout -b {branch_name(task)}"


def project_root() -> Path:
    if settings.repo_dir:
        return Path(settings.repo_dir).expanduser().resolve()
    return PROJECT_ROOT


# ---------------------------------------------------------------------------
# Baca
# ---------------------------------------------------------------------------

def list_tasks(*, status: str | None = None, phase: str | None = None,
               assignee: str | None = None, priority: str | None = None,
               label: str | None = None, q: str | None = None,
               seeded: bool | None = None) -> list[dict]:
    sql = "SELECT * FROM tasks"
    where: list[str] = []
    params: list[Any] = []
    if status and status in STATUSES:
        where.append("status=?")
        params.append(status)
    if phase:
        where.append("phase=?")
        params.append(phase)
    if assignee:
        where.append("assignee=?")
        params.append(assignee)
    if priority and priority in PRIORITIES:
        where.append("priority=?")
        params.append(priority)
    if seeded is not None:
        where.append("seeded=?")
        params.append(1 if seeded else 0)
    if label:
        where.append("labels LIKE ?")
        params.append(f'%"{label}"%')
    if q:
        needle = f"%{q.strip().lower()}%"
        where.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR "
                     "LOWER(id) LIKE ? OR LOWER(labels) LIKE ?)")
        params.extend([needle, needle, needle, needle])
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = "CASE status " + " ".join(
        f"WHEN '{s}' THEN {i}" for i, s in enumerate(STATUSES)) + " END, position"
    sql += f" ORDER BY {order}, id"
    tasks = [_row(r) for r in db.query_all(sql, tuple(params))]
    return _annotate(tasks)


def _annotate(tasks: list[dict]) -> list[dict]:
    """Tambahkan info turunan: blocker (dependency belum selesai) & subtask."""
    by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        deps = [(by_id.get(d) or {}).get("status", "missing")
                for d in t["depends_on"]]
        t["blocked_by"] = [d for d, st in zip(t["depends_on"], deps)
                           if st != "done"]
        t["ready"] = not t["blocked_by"] and t["status"] in ("backlog", "todo")
    return tasks


def get_task(task_id: str) -> dict | None:
    row = db.query_one("SELECT * FROM tasks WHERE id=?", (_norm(task_id),))
    return _row(row) if row else None


def _norm(task_id: str) -> str:
    return (task_id or "").strip().upper()


def task_detail(task_id: str) -> dict | None:
    task = get_task(task_id)
    if not task:
        return None
    task["comments"] = list_comments(task["id"])
    others = list_tasks()
    by_id = {t["id"]: t for t in others}
    task["blocked_by"] = [d for d in task["depends_on"]
                          if (by_id.get(d) or {}).get("status") != "done"]
    task["ready"] = (not task["blocked_by"]
                     and task["status"] in ("backlog", "todo"))
    task["depends_on_tasks"] = [
        {"id": d, "title": (by_id.get(d) or {}).get("title", ""),
         "status": (by_id.get(d) or {}).get("status", "missing"),
         "missing": d not in by_id}
        for d in task["depends_on"]
    ]
    task["dependents"] = [{"id": t["id"], "title": t["title"],
                           "status": t["status"]}
                          for t in others if task["id"] in t["depends_on"]]
    return task


def list_comments(task_id: str) -> list[dict]:
    return db.query_all(
        "SELECT * FROM task_comments WHERE task_id=? ORDER BY created_at ASC",
        (_norm(task_id),))


# ---------------------------------------------------------------------------
# Tulis
# ---------------------------------------------------------------------------

def next_task_id() -> str:
    rows = db.query_all("SELECT id FROM tasks")
    top = 0
    for r in rows:
        m = TASK_ID_RE.search(r["id"] or "")
        if m:
            top = max(top, int(m.group(1)))
    return f"ASK-{top + 1:03d}"


def _clean_acceptance(items: Iterable[Any]) -> list[dict]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            done = bool(item.get("done"))
        else:
            text, done = str(item).strip(), False
        if text:
            out.append({"text": text[:500], "done": done})
    return out


def create_task(*, title: str, description: str = "", phase: str = "f0",
                status: str = "todo", priority: str = "medium",
                assignee: str = "", estimate: float = 0,
                labels: Iterable[str] | None = None,
                acceptance: Iterable[Any] | None = None,
                depends_on: Iterable[str] | None = None,
                evidence: Iterable[str] | None = None, source: str = "",
                task_id: str = "", seeded: bool = False,
                branch: str = "", position: int | None = None) -> dict:
    title = (title or "").strip()
    if not title:
        raise TaskError("judul task wajib diisi")
    tid = _norm(task_id) or next_task_id()
    if not TASK_ID_RE.fullmatch(tid):
        raise TaskError("id task harus berbentuk ASK-NNN (mis. ASK-012)")
    if get_task(tid):
        raise TaskError(f"task {tid} sudah ada")
    if status not in STATUSES:
        raise TaskError(f"status tidak dikenal: {status}")
    if priority not in PRIORITIES:
        raise TaskError(f"prioritas tidak dikenal: {priority}")
    if phase not in PHASE_IDS:
        raise TaskError(f"fase tidak dikenal: {phase}")
    if position is None:
        row = db.query_one(
            "SELECT COALESCE(MAX(position),-1) AS p FROM tasks WHERE status=?",
            (status,))
        position = int(row["p"]) + 1 if row else 0

    ts = db.now()
    db.execute(
        "INSERT INTO tasks(id,title,description,phase,status,priority,assignee,"
        "estimate,labels,acceptance,depends_on,evidence,source,branch,mr_url,"
        "commits,position,seeded,created_at,updated_at,completed_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'[]',?,?,?,?,?)",
        (tid, title[:300], description or "", phase, status, priority,
         assignee or "", float(estimate or 0), json.dumps(list(labels or [])),
         json.dumps(_clean_acceptance(acceptance or [])),
         json.dumps([_norm(d) for d in (depends_on or [])]),
         json.dumps([str(e) for e in (evidence or [])]),
         source or "", branch or "", "", int(position), 1 if seeded else 0,
         ts, ts, 0.0 if status != "done" else ts),
    )
    return get_task(tid) or {}


EDITABLE = ("title", "description", "phase", "status", "priority", "assignee",
            "estimate", "labels", "acceptance", "depends_on", "evidence",
            "source", "branch", "mr_url", "position", "commits")


def update_task(task_id: str, patch: dict[str, Any]) -> dict | None:
    """Perbarui task; hanya field yang dikenal. ``acceptance``/``labels`` list."""
    current = get_task(task_id)
    if not current:
        return None
    fields: list[str] = []
    params: list[Any] = []
    for key in EDITABLE:
        if key not in patch or patch[key] is None:
            continue
        value = patch[key]
        if key == "status":
            if value not in STATUSES:
                raise TaskError(f"status tidak dikenal: {value}")
        if key == "priority" and value not in PRIORITIES:
            raise TaskError(f"prioritas tidak dikenal: {value}")
        if key == "phase" and value not in PHASE_IDS:
            raise TaskError(f"fase tidak dikenal: {value}")
        if key == "title":
            value = str(value).strip()
            if not value:
                raise TaskError("judul task tidak boleh kosong")
            value = value[:300]
        if key == "labels":
            value = json.dumps([str(x) for x in (value or [])])
        elif key in ("depends_on", "evidence"):
            value = json.dumps([_norm(x) if key == "depends_on" else str(x)
                                for x in (value or [])])
        elif key == "acceptance":
            value = json.dumps(_clean_acceptance(value))
        elif key == "commits":
            value = json.dumps([
                {"sha": str(c.get("sha", ""))[:40],
                 "subject": str(c.get("subject", ""))[:300]}
                for c in (value or []) if isinstance(c, dict)][-20:])
        elif key in ("estimate", "position"):
            value = float(value or 0) if key == "estimate" else int(value or 0)
        fields.append(f"{key}=?")
        params.append(value)

    if patch.get("status") == "done" and current["status"] != "done":
        fields.append("completed_at=?")
        params.append(db.now())
    if not fields:
        return current

    fields.append("updated_at=?")
    params.append(db.now())
    params.append(current["id"])
    db.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", tuple(params))
    updated = get_task(current["id"])
    if patch.get("status") and patch["status"] != current["status"] and updated:
        log_activity(updated["id"],
                     f"status: {current['status']} → {updated['status']}")
    return updated


def delete_task(task_id: str) -> bool:
    tid = _norm(task_id)
    if not get_task(tid):
        return False
    db.execute("DELETE FROM task_comments WHERE task_id=?", (tid,))
    db.execute("DELETE FROM tasks WHERE id=?", (tid,))
    return True


def move_task(task_id: str, status: str, before_id: str | None = None) -> dict | None:
    """Pindahkan task ke kolom `status`, opsional sebelum task lain (drag & drop)."""
    task = get_task(task_id)
    if not task:
        return None
    if status not in STATUSES:
        raise TaskError(f"status tidak dikenal: {status}")

    column = [t for t in list_tasks(status=status) if t["id"] != task["id"]]
    if before_id:
        idx = next((i for i, t in enumerate(column)
                    if t["id"] == _norm(before_id)), len(column))
        column.insert(idx, task)
    else:
        column.append(task)

    updated = update_task(task["id"], {"status": status})
    for i, t in enumerate(column):
        db.execute("UPDATE tasks SET position=? WHERE id=?", (i, t["id"]))
    return get_task(task["id"]) if updated else None


def set_acceptance(task_id: str, index: int, done: bool) -> dict | None:
    task = get_task(task_id)
    if not task:
        return None
    items = task["acceptance"]
    if not 0 <= index < len(items):
        raise TaskError("kriteria tidak ditemukan")
    items[index]["done"] = bool(done)
    return update_task(task["id"], {"acceptance": items})


def add_acceptance(task_id: str, text: str) -> dict | None:
    task = get_task(task_id)
    if not task:
        return None
    text = (text or "").strip()
    if not text:
        raise TaskError("kriteria tidak boleh kosong")
    return update_task(task["id"], {"acceptance": task["acceptance"] + [text]})


def remove_acceptance(task_id: str, index: int) -> dict | None:
    task = get_task(task_id)
    if not task:
        return None
    items = task["acceptance"]
    if not 0 <= index < len(items):
        raise TaskError("kriteria tidak ditemukan")
    items.pop(index)
    return update_task(task["id"], {"acceptance": items})


def add_comment(task_id: str, body: str, author: str = "dev",
                kind: str = "comment") -> dict:
    task = get_task(task_id)
    if not task:
        raise TaskError("task tidak ditemukan")
    body = (body or "").strip()
    if not body:
        raise TaskError("komentar tidak boleh kosong")
    if kind not in ("comment", "activity"):
        kind = "comment"
    cid = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO task_comments(id,task_id,author,kind,body,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (cid, task["id"], (author or "dev")[:60], kind, body[:MAX_COMMENT],
         db.now()),
    )
    db.execute("UPDATE tasks SET updated_at=? WHERE id=?", (db.now(), task["id"]))
    return db.query_one("SELECT * FROM task_comments WHERE id=?", (cid,)) or {}


def log_activity(task_id: str, body: str, author: str = "system") -> dict | None:
    try:
        return add_comment(task_id, body, author=author, kind="activity")
    except TaskError:
        return None


def delete_comment(comment_id: str) -> bool:
    row = db.query_one("SELECT * FROM task_comments WHERE id=?", (comment_id,))
    if not row:
        return False
    db.execute("DELETE FROM task_comments WHERE id=?", (comment_id,))
    return True


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------

def stats() -> dict[str, Any]:
    tasks = list_tasks()
    per_status = {s: 0 for s in STATUSES}
    per_phase: dict[str, dict[str, int]] = {
        p["id"]: {"total": 0, "done": 0} for p in PHASES}
    per_priority = {p: 0 for p in PRIORITIES}
    estimate_total = 0.0
    estimate_done = 0.0
    assignees: dict[str, int] = {}
    labels: dict[str, int] = {}
    blocked = 0
    for t in tasks:
        per_status[t["status"]] = per_status.get(t["status"], 0) + 1
        per_priority[t["priority"]] = per_priority.get(t["priority"], 0) + 1
        bucket = per_phase.setdefault(t["phase"], {"total": 0, "done": 0})
        bucket["total"] += 1
        if t["status"] == "done":
            bucket["done"] += 1
        estimate_total += float(t["estimate"] or 0)
        if t["status"] == "done":
            estimate_done += float(t["estimate"] or 0)
        if t["assignee"]:
            assignees[t["assignee"]] = assignees.get(t["assignee"], 0) + 1
        for l in t["labels"]:
            labels[l] = labels.get(l, 0) + 1
        if t["blocked_by"]:
            blocked += 1

    done = per_status.get("done", 0)
    return {
        "total": len(tasks),
        "done": done,
        "open": len(tasks) - done,
        "progress": round(100 * done / len(tasks)) if tasks else 0,
        "per_status": per_status,
        "per_phase": per_phase,
        "per_priority": per_priority,
        "estimate_total": round(estimate_total, 1),
        "estimate_done": round(estimate_done, 1),
        "assignees": dict(sorted(assignees.items(), key=lambda kv: -kv[1])),
        "labels": dict(sorted(labels.items(), key=lambda kv: -kv[1])),
        "blocked": blocked,
        "ready": sum(1 for t in tasks if t["ready"]),
        "statuses": list(STATUSES),
        "status_labels": dict(STATUS_LABELS),
        "phases": PHASES,
        "priorities": list(PRIORITIES),
    }


# ---------------------------------------------------------------------------
# Seeder rencana RAG
# ---------------------------------------------------------------------------

def seed_tasks(*, reset: bool = False) -> dict[str, Any]:
    """Muat rencana dari `tasks_plan.py`.

    Idempoten: task yang id-nya sudah ada **tidak** ditimpa (perubahan tangan
    developer aman), kecuali ``reset=True`` — di situ task rencana
    (``seeded=1``) dihapus lalu dibuat ulang; task buatan sendiri dibiarkan.
    """
    if reset:
        db.execute("DELETE FROM task_comments WHERE task_id IN "
                   "(SELECT id FROM tasks WHERE seeded=1)")
        db.execute("DELETE FROM tasks WHERE seeded=1")

    created: list[str] = []
    existing = {r["id"] for r in db.query_all("SELECT id FROM tasks")}
    position_by_status: dict[str, int] = {}
    for task in PLAN_TASKS:
        if task["id"] in existing:
            continue
        payload = dict(task)
        payload["task_id"] = payload.pop("id")
        status = payload["status"]
        position_by_status[status] = position_by_status.get(status, 0) + 1
        create_task(**payload, seeded=True,
                    position=position_by_status[status] - 1)
        created.append(task["id"])
        existing.add(task["id"])
    return {"created": created, "total": len(PLAN_TASKS), "reset": reset}


def seed_if_empty() -> list[str]:
    """Seed otomatis saat papan masih kosong (dipakai saat startup)."""
    row = db.query_one("SELECT COUNT(*) AS n FROM tasks")
    if row and int(row["n"]) > 0:
        return []
    report = seed_tasks()
    if report["created"]:
        sync(silent=True)
    return report["created"]


# ---------------------------------------------------------------------------
# Sinkronisasi kode & git
# ---------------------------------------------------------------------------

def _git(args: list[str], timeout: float = 8.0) -> str:
    """Jalankan git; kembalikan stdout atau '' bila git/git-repo tidak ada."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root()), *args],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def git_snapshot(limit: int = 600) -> dict[str, Any]:
    """Branch + commit yang bisa dipetakan ke task id ('' bila bukan git repo)."""
    branches = [b.strip() for b in _git(
        ["branch", "-a", "--format=%(refname:short)"]).splitlines() if b.strip()]
    branches = [b for b in branches if "HEAD ->" not in b]
    commits: list[dict[str, str]] = []
    raw = _git(["log", "--all", f"-n{limit}", "--pretty=%H%x1f%s"])
    for line in raw.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        commits.append({"sha": sha.strip()[:12], "subject": subject.strip()})
    return {"branches": branches, "commits": commits,
            "repo": str(project_root()),
            "is_repo": bool(branches or commits)}


def _touched(evidence: Iterable[str]) -> bool:
    """True bila SEMUA berkas penanda implementasi ada di disk."""
    items = [e for e in evidence if e]
    if not items:
        return False
    root = PROJECT_ROOT
    return all((root / e).exists() for e in items)


def sync(*, silent: bool = False) -> dict[str, Any]:
    """Selaraskan papan dengan kenyataan kode & riwayat git.

    Aturan (status hanya boleh **naik**, tidak pernah turun otomatis):
      * semua berkas `evidence` ada → minimal `review`;
      * branch yang memuat `ASK-NNN` ada → isi `branch`, minimal `in_progress`;
      * commit yang menyebut `ASK-NNN` → simpan sha, minimal `in_progress`;
        bila subjeknya memuat kata selesai/close/fix/merge → `done`.
    """
    snapshot = git_snapshot()
    tasks = list_tasks()
    changed: list[dict[str, str]] = []

    for task in tasks:
        patch: dict[str, Any] = {}
        notes: list[str] = []

        # 1) bukti implementasi di repo
        if task["evidence"] and _touched(task["evidence"]):
            if _rank(task["status"]) < _rank("review"):
                patch["status"] = "review"
                notes.append("berkas implementasi terdeteksi → review")

        # 2) branch git
        branch = task["branch"]
        if not branch:
            for b in snapshot["branches"]:
                if task["id"].upper() in b.upper():
                    branch = b
                    patch["branch"] = b
                    notes.append(f"branch terdeteksi: {b}")
                    break
        if branch and _rank(patch.get("status", task["status"])) < _rank("in_progress"):
            patch["status"] = "in_progress"
            notes.append("branch aktif → in_progress")

        # 3) commit git
        hits = [c for c in snapshot["commits"]
                if task["id"].upper() in (c["subject"] or "").upper()]
        if hits:
            known = {c.get("sha") for c in task["commits"]}
            fresh = [c for c in hits if c["sha"] not in known]
            if fresh:
                patch["commits"] = (task["commits"] + fresh)[-20:]
                notes.append(f"{len(fresh)} commit baru menyebut {task['id']}")
            if _rank(patch.get("status", task["status"])) < _rank("in_progress"):
                patch["status"] = "in_progress"
            if any(k in (c["subject"] or "").lower() for c in hits
                   for k in DONE_KEYWORDS) and task["status"] != "done":
                patch["status"] = "done"
                notes.append("commit menandai pekerjaan selesai")

        if patch:
            try:
                update_task(task["id"], patch)
            except TaskError:
                continue
            changed.append({"id": task["id"], "status": patch.get(
                "status", task["status"]), "notes": "; ".join(notes)})
            if not silent:
                for note in notes:
                    log_activity(task["id"], note)

    report = {
        "repo": snapshot["repo"],
        "is_repo": snapshot["is_repo"],
        "branches": len(snapshot["branches"]),
        "commits": len(snapshot["commits"]),
        "changed": changed,
    }
    if not snapshot["is_repo"]:
        report["note"] = ("Folder ini bukan repo git (atau `git` tidak tersedia) — "
                          "hanya pemeriksaan berkas implementasi yang dijalankan.")
    return report


def plan() -> dict[str, Any]:
    return plan_summary()
