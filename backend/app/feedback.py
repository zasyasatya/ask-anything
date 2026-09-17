"""User feedback (👍/👎) — terecord penuh, lalu dipakai ulang untuk mengatur
perilaku AI.

Alur:
  1. User menekan 👍/👎 di chat (+ komentar opsional) → POST /api/feedback.
  2. Setiap feedback tersimpan bersama konteks run (mode, model, tool yang
     dipakai, cuplikan jawaban) supaya bisa dianalisis, bukan sekadar angka.
  3. Feedback 👎 berkomentar — kalau `feedback.auto_guidance` aktif — otomatis
     menjadi **pedoman** (memory source='feedback') yang di-inject ke system
     prompt run berikutnya. Admin bisa meninjul, menonaktifkan, atau
     menerapkan manual dari halaman admin.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from . import db, memory

RATINGS = ("up", "down")
STATUSES = ("new", "reviewed", "applied", "dismissed")

SNIPPET = 400


def add_feedback(rating: str, conversation_id: str = "", message_id: str = "",
                 comment: str = "", context: dict | None = None) -> dict:
    rating = (rating or "").strip().lower()
    if rating not in RATINGS:
        raise ValueError("rating harus 'up' atau 'down'")
    fid = uuid.uuid4().hex[:12]
    ctx = context or {}
    db.execute(
        "INSERT INTO feedback(id,conversation_id,message_id,rating,comment,"
        "context,status,created_at) VALUES(?,?,?,?,?,?, 'new', ?)",
        (fid, conversation_id or "", message_id or "", rating,
         (comment or "").strip(), json.dumps(ctx, default=str, ensure_ascii=False),
         db.now()),
    )
    return get_feedback(fid) or {}


def get_feedback(fid: str) -> dict | None:
    row = db.query_one("SELECT * FROM feedback WHERE id=?", (fid,))
    return _hydrate(row)


def list_feedback(status: str | None = None, limit: int = 200) -> list[dict]:
    sql, params = "SELECT * FROM feedback", []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    return [r for r in (_hydrate(row) for row in db.query_all(sql, tuple(params))) if r]


def _hydrate(row: dict | None) -> dict | None:
    if not row:
        return None
    try:
        row["context"] = json.loads(row.get("context") or "{}")
    except (TypeError, ValueError):
        row["context"] = {}
    return row


def set_status(fid: str, status: str) -> dict | None:
    if status not in STATUSES:
        raise ValueError(f"status harus salah satu dari: {', '.join(STATUSES)}")
    if not get_feedback(fid):
        return None
    db.execute("UPDATE feedback SET status=? WHERE id=?", (status, fid))
    return get_feedback(fid)


def delete_feedback(fid: str) -> bool:
    if not get_feedback(fid):
        return False
    db.execute("DELETE FROM feedback WHERE id=?", (fid,))
    return True


# ---------------------------------------------------------------------------
# Feedback → guidance (mengatur ulang behaviour)
# ---------------------------------------------------------------------------

def guidance_text(fid: str) -> str:
    """Bangun teks pedoman dari satu feedback (dipakai auto & manual apply)."""
    fb = get_feedback(fid)
    if not fb:
        raise ValueError("feedback tidak ditemukan")
    comment = (fb.get("comment") or "").strip()
    ctx = fb.get("context") or {}
    answer = (ctx.get("answer_snippet") or "").strip()
    if fb["rating"] == "down":
        base = comment or f"Hindari gaya jawaban seperti: {answer[:SNIPPET]!r}"
        return f"Perbaikan dari feedback user (👎): {base}"
    base = comment or f"Pertahankan gaya jawaban seperti: {answer[:SNIPPET]!r}"
    return f"Apresiasi dari feedback user (👍): {base}"


def apply_feedback(fid: str, actor: str = "admin") -> dict:
    """Ubah feedback jadi pedoman permanen (memory source='feedback')."""
    fb = get_feedback(fid)
    if not fb:
        raise ValueError("feedback tidak ditemukan")
    if fb.get("guidance_memory_id"):
        return {"feedback": fb, "memory": memory.get_memory(fb["guidance_memory_id"])}
    content = guidance_text(fid)
    mem = memory.add_memory(
        scope="global",
        content=content,
        key=f"feedback-{fb['created_at']:.0f}",
        source="feedback",
        enabled=True,
    )
    db.execute(
        "UPDATE feedback SET status='applied', guidance_memory_id=? WHERE id=?",
        (mem["id"], fid),
    )
    return {"feedback": get_feedback(fid), "memory": mem}


def maybe_auto_apply(fid: str, policy_feedback: dict[str, Any]) -> dict | None:
    """Auto-apply 👎 berkomentar bila policy mengizinkan (dipanggil route)."""
    if not policy_feedback.get("auto_guidance", False):
        return None
    fb = get_feedback(fid)
    if not fb or fb["rating"] != "down" or not (fb.get("comment") or "").strip():
        return None
    try:
        applied = apply_feedback(fid, actor="auto")
    except ValueError:
        return None
    return applied


def guidance_block(limit: int = 8) -> str:
    """Blok PEDOMAN FEEDBACK untuk system prompt ('' bila belum ada)."""
    mems = [m for m in memory.list_memories(include_disabled=False)
            if m["source"] == "feedback"][: max(0, limit)]
    if not mems:
        return ""
    lines = ["PEDOMAN DARI FEEDBACK USER (tercipta dari evaluasi 👍/👎):"]
    for m in mems:
        lines.append(f"- {m['content']}")
    lines.append("Terapkan pedoman ini tanpa perlu menyebutnya ke user.")
    return "\n".join(lines)


def stats() -> dict[str, Any]:
    total = db.query_one("SELECT COUNT(*) AS n FROM feedback") or {"n": 0}
    up = db.query_one("SELECT COUNT(*) AS n FROM feedback WHERE rating='up'") or {"n": 0}
    status_rows = db.query_all(
        "SELECT status, COUNT(*) AS n FROM feedback GROUP BY status")
    by_status = {r["status"]: r["n"] for r in status_rows}
    n_up, n_total = int(up["n"]), int(total["n"])
    return {
        "total": n_total,
        "up": n_up,
        "down": n_total - n_up,
        "ratio_up": round(n_up / n_total, 3) if n_total else None,
        "by_status": by_status,
    }
