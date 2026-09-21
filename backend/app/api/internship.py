"""API halaman `/internship` — papan + materi proyek "from scratch".

Halaman ini untuk anak internship (role **member**): mereka melihat
  * ringkasan rencana (fase, estimasi hari, pembagian per orang),
  * task **miliknya sendiri** (task orang lain tidak terlihat),
  * materi/dokumen proyek (`docs/internship/*.md`) langsung dari backend,
  * slide rujukan (`/slides/slides-rag-agent.html`) dan kriteria sukses.

Dokumen dibaca dari folder `docs/internship/` — nama file divalidasi (tanpa
`..`/`/`) supaya endpoint ini tidak bisa dipakai membaca berkas lain di server.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import internship_plan, tasks
from ..auth import current_principal
from ..config import PROJECT_ROOT

router = APIRouter(prefix="/api/internship")

DOCS_DIR = PROJECT_ROOT / "docs" / "internship"
#: Slide rujukan (disajikan backend pada /slides/…).
SLIDES = [
    {"href": "/slides/slides-rag-agent.html",
     "title": "Slide: RAG + AI Agent (materi utama)",
     "note": "Arsitektur, chunking, tool, visual web native, task breakdown."},
    {"href": "/slides/slides-cara-kerja.html",
     "title": "Slide: cara kerja sistem (ask-anything)",
     "note": "Contoh nyata alur agent + RAG yang sudah jalan."},
    {"href": "/slides/slides-admin-pipeline.html",
     "title": "Slide: pipeline & governance",
     "note": "Mode/tool, memori, artifact, feedback, interpreter."},
]


def _doc_title(path: Path) -> str:
    """Judul dokumen = heading `#` pertama (fallback: nama file)."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def _doc_excerpt(path: Path, limit: int = 220) -> str:
    """Ringkasan: paragraf pertama yang bukan heading/kode."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        text = line.strip()
        if not text or text.startswith(("#", ">", "|", "-", "*", "```")):
            continue
        return text[:limit] + ("…" if len(text) > limit else "")
    return ""


def list_docs() -> list[dict[str, Any]]:
    if not DOCS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        out.append({
            "name": path.name,
            "title": _doc_title(path),
            "excerpt": _doc_excerpt(path),
            "size_bytes": path.stat().st_size,
        })
    return out


@router.get("/overview")
async def overview(principal: dict[str, Any] = Depends(current_principal)
                   ) -> dict[str, Any]:
    """Ringkasan proyek + kemajuan papan, disesuaikan dengan peran pemanggil."""
    role = (principal or {}).get("role") or "member"
    username = (principal or {}).get("username") or ""
    names = None if role == "admin" else [
        n for n in [username, (principal or {}).get("name") or ""] if n]
    plan = tasks.plan(internship_plan.TRACK)
    board = tasks.list_tasks(track=internship_plan.TRACK, assignee_in=names)
    stats = tasks.stats(internship_plan.TRACK, assignee_in=names)

    per_assignee: dict[str, dict[str, int]] = {}
    for task in tasks.list_tasks(track=internship_plan.TRACK):
        who = (task.get("assignee") or "belum ditugaskan").strip() or "belum ditugaskan"
        bucket = per_assignee.setdefault(who, {"total": 0, "done": 0,
                                              "in_progress": 0})
        bucket["total"] += 1
        if task["status"] == "done":
            bucket["done"] += 1
        if task["status"] in ("in_progress", "review"):
            bucket["in_progress"] += 1
    return {
        "track": internship_plan.TRACK,
        "project_dir": internship_plan.PROJECT_DIR,
        "plan": plan,
        "stats": stats,
        "tasks": board,
        "per_assignee": per_assignee,
        "interns": list(internship_plan.INTERNS),
        "docs": list_docs(),
        "slides": SLIDES,
        "scope": "all" if names is None else "assigned",
        "me": {"username": username, "role": role},
    }


@router.get("/docs")
async def docs_index() -> dict[str, Any]:
    return {"docs": list_docs(), "slides": SLIDES,
            "dir": str(DOCS_DIR.relative_to(PROJECT_ROOT))
            if DOCS_DIR.is_dir() else "docs/internship"}


@router.get("/docs/{name}")
async def read_doc(name: str) -> dict[str, Any]:
    safe = Path(name).name  # buang komponen path apa pun
    if not safe.endswith(".md"):
        safe += ".md"
    path = (DOCS_DIR / safe).resolve()
    try:
        path.relative_to(DOCS_DIR.resolve())
    except ValueError:
        raise HTTPException(400, "nama dokumen tidak valid") from None
    if not path.is_file():
        raise HTTPException(404, f"dokumen {safe} tidak ditemukan")
    return {"name": safe, "title": _doc_title(path),
            "markdown": path.read_text(encoding="utf-8")}
