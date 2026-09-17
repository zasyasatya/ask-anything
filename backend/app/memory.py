"""Memory management — fakta & pedoman jangka panjang yang di-inject ke prompt.

Tiga jalur tulis, satu pintu injection:

  admin    — ditulis manual di halaman admin (kebijakan produk, tone, batasan).
  ai       — ditulis agent via tool `save_memory` (butuh izin admin).
  feedback — pedoman hasil belajar dari feedback 👎 user (lihat feedback.py).

Semua entri aktif dirangkai jadi satu blok MEMORI di system prompt setiap run,
jadi perubahan di halaman admin langsung mengubah perilaku AI tanpa restart.
"""
from __future__ import annotations

import json
from typing import Any

from . import db

SCOPES = ("global", "conversation")
SOURCES = ("admin", "ai", "feedback", "user")

PROMPT_HEADING = "MEMORI JANGKA PANJANG (atur dari halaman admin):"


def add_memory(scope: str, content: str, key: str = "", source: str = "admin",
               enabled: bool = True, conversation_id: str = "") -> dict:
    content = (content or "").strip()
    if not content:
        raise ValueError("isi memori tidak boleh kosong")
    scope = scope if scope in SCOPES else "global"
    source = source if source in SOURCES else "admin"
    mid = db.now()
    import uuid
    mid = uuid.uuid4().hex[:12]
    ts = db.now()
    db.execute(
        "INSERT INTO memories(id,scope,key,content,source,enabled,created_at,"
        "updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (mid, scope, (key or "").strip(), content, source,
         1 if enabled else 0, ts, ts),
    )
    return get_memory(mid) or {}


def get_memory(mid: str) -> dict | None:
    row = db.query_one("SELECT * FROM memories WHERE id=?", (mid,))
    if row:
        row["enabled"] = bool(row["enabled"])
    return row


def list_memories(include_disabled: bool = True,
                  scope: str | None = None) -> list[dict]:
    sql = "SELECT * FROM memories"
    where, params = [], []
    if not include_disabled:
        where.append("enabled=1")
    if scope:
        where.append("scope=?")
        params.append(scope)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC"
    return [{**r, "enabled": bool(r["enabled"])} for r in db.query_all(sql, tuple(params))]


def update_memory(mid: str, patch: dict[str, Any]) -> dict | None:
    cur = get_memory(mid)
    if not cur:
        return None
    fields, params = [], []
    for k in ("scope", "key", "content"):
        if k in patch and patch[k] is not None:
            fields.append(f"{k}=?")
            params.append(str(patch[k]))
    if "enabled" in patch:
        fields.append("enabled=?")
        params.append(1 if patch["enabled"] else 0)
    if not fields:
        return cur
    fields.append("updated_at=?")
    params.extend([db.now()])
    params.append(mid)
    db.execute(f"UPDATE memories SET {', '.join(fields)} WHERE id=?", tuple(params))
    return get_memory(mid)


def delete_memory(mid: str) -> bool:
    if not get_memory(mid):
        return False
    db.execute("DELETE FROM memories WHERE id=?", (mid,))
    return True


def enabled_memories(limit: int = 24, max_chars: int = 4000) -> list[dict]:
    """Memori aktif, terbaru dulu, dipotong supaya prompt tetap ramping."""
    items = list_memories(include_disabled=False)
    items = items[: max(0, limit)]
    out, total = [], 0
    for m in items:
        n = len(m["content"])
        if total + n > max_chars and out:
            break
        out.append(m)
        total += n
    return out


def prompt_block(policy_memory: dict[str, Any] | None = None) -> str:
    """Blok MEMORI untuk system prompt ('' bila kosong / fitur dimatikan)."""
    if policy_memory is not None and not policy_memory.get("enabled", True):
        return ""
    items = enabled_memories()
    if not items:
        return ""
    lines = [PROMPT_HEADING]
    for m in items:
        label = f"[{m['key']}] " if m["key"] else ""
        tag = {"feedback": "hasil evaluasi user",
               "ai": "dicatat agent",
               "user": "diminta user"}.get(m["source"], "kebijakan admin")
        lines.append(f"- {label}{m['content']} ({tag})")
    lines.append(
        "Patuhi memori di atas untuk jawaban berikutnya; memori adalah "
        "kebijakan produk, bukan fakta yang perlu disitasi."
    )
    return "\n".join(lines)


def meta_of(mem: dict | None) -> dict:
    """Ringkas untuk trace/interpret (tanpa mengubah sumber kebenaran)."""
    if not mem:
        return {}
    return {"id": mem["id"], "scope": mem["scope"], "key": mem["key"],
            "source": mem["source"], "enabled": mem["enabled"],
            "content": mem["content"]}
