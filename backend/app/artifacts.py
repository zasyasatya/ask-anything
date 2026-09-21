"""Artifact storage — setiap keluaran biner (gambar, PPTX, dokumen) disimpan
sekali, terregistry di SQLite, dan bisa diunduh/audit/dihapus dari halaman admin.

File fisik ada di `<data>/artifacts/` (di luar Git); metadata (kind, ukuran,
asal run, meta JSON) ada di tabel `artifacts`. Registry dipangkas FIFO bila
melewati `artifacts.max_artifacts` supaya disk tidak bocor tanpa batas.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from . import db

KINDS = ("image", "pptx", "diagram", "document", "data")


def _dir(settings: Any) -> Path:
    resolver = getattr(settings, "resolved_artifacts_dir", None)
    if callable(resolver):
        p = Path(resolver())
    else:  # pragma: no cover - settings tiruan di test lama
        p = Path(getattr(settings, "artifacts_dir", "data/artifacts"))
        if not p.is_absolute():
            from .config import PROJECT_ROOT
            p = PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def register_artifact(*, settings: Any, kind: str, title: str, filename: str,
                      mime: str, data: bytes, conversation_id: str = "",
                      run_id: str = "", meta: dict | None = None) -> dict:
    if kind not in KINDS:
        kind = "data"
    aid = uuid.uuid4().hex[:12]
    safe_name = (filename or f"artifact-{aid}").replace("/", "_").replace("\\", "_")
    path = _dir(settings) / f"{aid}_{safe_name}"
    path.write_bytes(data)

    db.execute(
        "INSERT INTO artifacts(id,conversation_id,run_id,kind,title,filename,"
        "mime,size_bytes,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (aid, conversation_id or "", run_id or "", kind, title or safe_name,
         safe_name, mime or "application/octet-stream", len(data),
         json.dumps(meta or {}, default=str), db.now()),
    )
    _prune(settings)
    art = get_artifact(aid)
    if art:
        art["url"] = f"/api/artifacts/{aid}/download"
        art["path"] = str(path)
    return art or {}


def _prune(settings: Any, max_items: int | None = None) -> None:
    if max_items is None:
        from .governance import policy
        max_items = int(policy()["artifacts"].get("max_artifacts", 500))
    if max_items <= 0:
        return
    rows = db.query_all(
        "SELECT id, filename FROM artifacts ORDER BY created_at DESC "
        f"LIMIT -1 OFFSET {int(max_items)}")
    for r in rows:
        delete_artifact(r["id"], settings=settings)


def get_artifact(aid: str) -> dict | None:
    row = db.query_one("SELECT * FROM artifacts WHERE id=?", (aid,))
    if not row:
        return None
    try:
        row["meta"] = json.loads(row.get("meta") or "{}")
    except (TypeError, ValueError):
        row["meta"] = {}
    return row


def list_artifacts(kind: str | None = None, limit: int = 200) -> list[dict]:
    sql, params = "SELECT * FROM artifacts", []
    if kind:
        sql += " WHERE kind=?"
        params.append(kind)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    out = []
    for row in db.query_all(sql, tuple(params)):
        try:
            row["meta"] = json.loads(row.get("meta") or "{}")
        except (TypeError, ValueError):
            row["meta"] = {}
        row["url"] = f"/api/artifacts/{row['id']}/download"
        out.append(row)
    return out


def read_artifact(aid: str, settings: Any) -> tuple[dict, bytes] | None:
    art = get_artifact(aid)
    if not art:
        return None
    path = _dir(settings) / f"{aid}_{art['filename']}"
    if not path.exists():
        return None
    return art, path.read_bytes()


def delete_artifact(aid: str, settings: Any | None = None) -> bool:
    art = get_artifact(aid)
    if not art:
        return False
    if settings is not None:
        path = _dir(settings) / f"{aid}_{art['filename']}"
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    db.execute("DELETE FROM artifacts WHERE id=?", (aid,))
    return True
