"""Pipeline kuota token — batas pemakaian harian/mingguan per end user.

Kenapa ada: tanpa batas, satu pengguna (atau satu skrip) bisa menghabiskan
kuota provider untuk semua orang. Modul ini membuat pemakaian **terukur,
tertegakkan di server, dan terlihat di halaman admin**.

Alur satu request chat:

    resolve_user(request)        → identitas end user (header X-User-Id / IP)
    check(user_key)              → boleh jalan? sisa berapa? kapan reset?
      ├─ ditolak → SSE `error` + event trace `quota`, agent tidak pernah jalan
      └─ diizinkan → agent jalan
    record(user_key, usage)      → tulis pemakaian nyata dari event `usage`

Desain periode: memakai **kalender**, bukan sliding window — `day_key`
(`YYYY-MM-DD`) dan `week_key` (`YYYY-Www`, ISO) disimpan di setiap baris
pemakaian. Akibatnya reset terjadi otomatis saat tanggal/pekan berganti, tanpa
scheduler, dan angka di admin mudah dijelaskan ke pengguna ("kuota harian Anda
reset tengah malam").

Batas berlaku berlapis:
  1. `usage_limits` — override per user (diatur admin; menang atas policy)
  2. policy `quota` di `governance.py` — batas default untuk semua user

Nilai batas `0` berarti **tanpa batas** untuk dimensi itu.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from . import db, governance

#: Header yang dipakai frontend/klien untuk menandai end user.
USER_HEADER = "X-User-Id"

#: Batas panjang identitas supaya tidak ada baris raksasa di DB.
_MAX_KEY = 120


# ---------------------------------------------------------------------------
# Identitas & periode
# ---------------------------------------------------------------------------

def normalise_user(raw: str | None, fallback_ip: str | None = None) -> str:
    """Identitas end user yang stabil dan aman disimpan.

    Aplikasi ini belum punya sistem login, jadi identitas diambil dari header
    `X-User-Id` (diisi frontend, mis. id device/akun). Bila tidak ada, dipakai
    alamat IP klien agar kuota tetap berlaku untuk pemanggil anonim — lebih
    baik daripada tidak ada batas sama sekali.
    """
    value = (raw or "").strip()
    if value:
        return value[:_MAX_KEY]
    ip = (fallback_ip or "").strip()
    return f"ip:{ip[:_MAX_KEY - 3]}" if ip else "anonymous"


def day_key(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts if ts is not None else time.time()).strftime(
        "%Y-%m-%d")


def week_key(ts: float | None = None) -> str:
    date = datetime.fromtimestamp(ts if ts is not None else time.time()).date()
    iso_year, iso_week, _ = date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _next_day_reset(ts: float | None = None) -> float:
    now = datetime.fromtimestamp(ts if ts is not None else time.time())
    start_of_next = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return start_of_next.timestamp()


def _next_week_reset(ts: float | None = None) -> float:
    now = datetime.fromtimestamp(ts if ts is not None else time.time())
    # ISO: Senin = awal pekan (isoweekday 1).
    days_ahead = 8 - now.isoweekday()
    start_of_next = (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return start_of_next.timestamp()


# ---------------------------------------------------------------------------
# Batas efektif
# ---------------------------------------------------------------------------

def _policy_quota() -> dict[str, Any]:
    return governance.policy()["quota"]


def get_override(user_key: str) -> dict[str, Any] | None:
    return db.query_one("SELECT * FROM usage_limits WHERE user_key=?", (user_key,))


def effective_limits(user_key: str) -> dict[str, Any]:
    """Gabungan policy global + override per user (override menang)."""
    pol = _policy_quota()
    limits = {
        "daily_tokens": int(pol.get("daily_tokens") or 0),
        "weekly_tokens": int(pol.get("weekly_tokens") or 0),
        "daily_requests": int(pol.get("daily_requests") or 0),
        "source": "policy",
    }
    row = get_override(user_key)
    if row:
        for field in ("daily_tokens", "weekly_tokens", "daily_requests"):
            value = row.get(field)
            # NULL = "ikut policy"; 0 = "tanpa batas" (sengaja dibedakan).
            if value is not None:
                limits[field] = int(value)
        limits["source"] = "override"
        limits["note"] = row.get("note") or ""
    return limits


def set_override(user_key: str, *, daily_tokens: int | None = None,
                 weekly_tokens: int | None = None,
                 daily_requests: int | None = None,
                 note: str = "") -> dict[str, Any]:
    db.execute(
        "INSERT INTO usage_limits(user_key, daily_tokens, weekly_tokens, "
        "daily_requests, note, updated_at) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(user_key) DO UPDATE SET "
        "daily_tokens=excluded.daily_tokens, "
        "weekly_tokens=excluded.weekly_tokens, "
        "daily_requests=excluded.daily_requests, "
        "note=excluded.note, updated_at=excluded.updated_at",
        (user_key, daily_tokens, weekly_tokens, daily_requests, note or "",
         time.time()),
    )
    return effective_limits(user_key)


def clear_override(user_key: str) -> bool:
    existed = get_override(user_key) is not None
    db.execute("DELETE FROM usage_limits WHERE user_key=?", (user_key,))
    return existed


# ---------------------------------------------------------------------------
# Pemakaian
# ---------------------------------------------------------------------------

def consumption(user_key: str, ts: float | None = None) -> dict[str, int]:
    """Token & jumlah request yang sudah dipakai pada periode berjalan."""
    today = db.query_one(
        "SELECT COALESCE(SUM(total_tokens),0) AS tokens, COUNT(*) AS requests "
        "FROM token_usage WHERE user_key=? AND day_key=?",
        (user_key, day_key(ts)),
    ) or {}
    week = db.query_one(
        "SELECT COALESCE(SUM(total_tokens),0) AS tokens, COUNT(*) AS requests "
        "FROM token_usage WHERE user_key=? AND week_key=?",
        (user_key, week_key(ts)),
    ) or {}
    return {
        "day_tokens": int(today.get("tokens") or 0),
        "day_requests": int(today.get("requests") or 0),
        "week_tokens": int(week.get("tokens") or 0),
        "week_requests": int(week.get("requests") or 0),
    }


def _remaining(limit: int, used: int) -> int | None:
    """Sisa kuota; `None` = tanpa batas (limit 0)."""
    return None if limit <= 0 else max(0, limit - used)


def status(user_key: str, ts: float | None = None) -> dict[str, Any]:
    """Snapshot lengkap untuk UI end user maupun dashboard admin."""
    pol = _policy_quota()
    limits = effective_limits(user_key)
    used = consumption(user_key, ts)
    return {
        "user_key": user_key,
        "enabled": bool(pol.get("enabled")),
        "block_on_exceed": bool(pol.get("block_on_exceed")),
        "limits": limits,
        "used": used,
        "remaining": {
            "day_tokens": _remaining(limits["daily_tokens"], used["day_tokens"]),
            "week_tokens": _remaining(limits["weekly_tokens"], used["week_tokens"]),
            "day_requests": _remaining(limits["daily_requests"],
                                       used["day_requests"]),
        },
        "period": {
            "day_key": day_key(ts),
            "week_key": week_key(ts),
            "day_reset_at": _next_day_reset(ts),
            "week_reset_at": _next_week_reset(ts),
        },
    }


def check(user_key: str, ts: float | None = None) -> dict[str, Any]:
    """Boleh menjalankan satu request lagi?

    Mengembalikan `{"allowed": bool, "reason": str, "status": {...}}`.
    Pengecekan dilakukan terhadap pemakaian yang **sudah** tercatat: request
    berjalan tidak pernah ditolak di tengah jalan, tetapi begitu batas
    terlampaui request berikutnya ditolak.
    """
    snapshot = status(user_key, ts)
    if not snapshot["enabled"]:
        return {"allowed": True, "reason": "", "status": snapshot}

    limits, used = snapshot["limits"], snapshot["used"]
    checks = (
        ("daily_tokens", "day_tokens", "token harian"),
        ("weekly_tokens", "week_tokens", "token mingguan"),
        ("daily_requests", "day_requests", "jumlah permintaan harian"),
    )
    for limit_field, used_field, label in checks:
        limit = int(limits.get(limit_field) or 0)
        if limit > 0 and int(used[used_field]) >= limit:
            reset_at = (snapshot["period"]["week_reset_at"]
                        if limit_field == "weekly_tokens"
                        else snapshot["period"]["day_reset_at"])
            reason = (
                f"Kuota {label} sudah habis "
                f"({used[used_field]:,}/{limit:,}). "
                f"Kuota terisi lagi otomatis pada "
                f"{datetime.fromtimestamp(reset_at):%d %b %Y %H:%M}."
            ).replace(",", ".")
            if not snapshot["block_on_exceed"]:
                # Mode pemantauan: lewatkan request, tapi tetap laporkan.
                return {"allowed": True, "reason": reason, "status": snapshot,
                        "over_limit": True}
            return {"allowed": False, "reason": reason, "status": snapshot,
                    "over_limit": True}
    return {"allowed": True, "reason": "", "status": snapshot}


def record(user_key: str, usage: dict[str, Any] | None, *,
           conversation_id: str = "", run_id: str = "", mode: str = "",
           provider: str = "", model: str = "",
           ts: float | None = None) -> dict[str, Any]:
    """Catat pemakaian nyata satu run (dipanggil setelah agent selesai)."""
    usage = usage or {}

    def _int(*names: str) -> int:
        for name in names:
            try:
                value = int(usage.get(name) or 0)
            except (TypeError, ValueError):
                continue
            if value:
                return value
        return 0

    prompt_tokens = _int("prompt_tokens")
    completion_tokens = _int("completion_tokens")
    total = _int("total_tokens") or (prompt_tokens + completion_tokens)
    moment = ts if ts is not None else time.time()

    db.execute(
        "INSERT INTO token_usage(id, user_key, conversation_id, run_id, mode, "
        "provider, model, prompt_tokens, completion_tokens, total_tokens, "
        "day_key, week_key, ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (uuid.uuid4().hex[:12], user_key, conversation_id, run_id, mode,
         provider, model, prompt_tokens, completion_tokens, total,
         day_key(moment), week_key(moment), moment),
    )
    touch_user(user_key, ts=moment)
    return status(user_key, moment)


def touch_user(user_key: str, *, ts: float | None = None) -> None:
    """Daftarkan/segarkan end user supaya admin bisa melihat daftarnya."""
    moment = ts if ts is not None else time.time()
    db.execute(
        "INSERT INTO usage_users(user_key, first_seen, last_seen) VALUES(?,?,?) "
        "ON CONFLICT(user_key) DO UPDATE SET last_seen=excluded.last_seen",
        (user_key, moment, moment),
    )


# ---------------------------------------------------------------------------
# Monitoring (halaman admin)
# ---------------------------------------------------------------------------

def list_users(limit: int = 200, ts: float | None = None) -> list[dict[str, Any]]:
    """Semua end user + pemakaian periode berjalan + batas efektifnya."""
    rows = db.query_all(
        "SELECT u.user_key, u.first_seen, u.last_seen, "
        "  COALESCE(d.tokens,0) AS day_tokens, COALESCE(d.requests,0) AS day_requests, "
        "  COALESCE(w.tokens,0) AS week_tokens, COALESCE(w.requests,0) AS week_requests, "
        "  COALESCE(t.tokens,0) AS total_tokens, COALESCE(t.requests,0) AS total_requests "
        "FROM usage_users u "
        "LEFT JOIN (SELECT user_key, SUM(total_tokens) tokens, COUNT(*) requests "
        "           FROM token_usage WHERE day_key=? GROUP BY user_key) d "
        "       ON d.user_key = u.user_key "
        "LEFT JOIN (SELECT user_key, SUM(total_tokens) tokens, COUNT(*) requests "
        "           FROM token_usage WHERE week_key=? GROUP BY user_key) w "
        "       ON w.user_key = u.user_key "
        "LEFT JOIN (SELECT user_key, SUM(total_tokens) tokens, COUNT(*) requests "
        "           FROM token_usage GROUP BY user_key) t "
        "       ON t.user_key = u.user_key "
        "ORDER BY day_tokens DESC, u.last_seen DESC LIMIT ?",
        (day_key(ts), week_key(ts), int(limit)),
    )
    out = []
    for row in rows:
        limits = effective_limits(row["user_key"])
        row["limits"] = limits
        row["remaining"] = {
            "day_tokens": _remaining(limits["daily_tokens"], row["day_tokens"]),
            "week_tokens": _remaining(limits["weekly_tokens"], row["week_tokens"]),
        }
        row["over_limit"] = any(
            limits[lf] > 0 and row[uf] >= limits[lf]
            for lf, uf in (("daily_tokens", "day_tokens"),
                           ("weekly_tokens", "week_tokens"),
                           ("daily_requests", "day_requests"))
        )
        out.append(row)
    return out


def overview(ts: float | None = None) -> dict[str, Any]:
    """Ringkasan pipeline kuota untuk dashboard admin."""
    pol = _policy_quota()
    totals = db.query_one(
        "SELECT COUNT(*) AS runs, COALESCE(SUM(total_tokens),0) AS tokens, "
        "       COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
        "       COALESCE(SUM(completion_tokens),0) AS completion_tokens "
        "FROM token_usage") or {}
    today = db.query_one(
        "SELECT COUNT(*) AS runs, COALESCE(SUM(total_tokens),0) AS tokens "
        "FROM token_usage WHERE day_key=?", (day_key(ts),)) or {}
    this_week = db.query_one(
        "SELECT COUNT(*) AS runs, COALESCE(SUM(total_tokens),0) AS tokens "
        "FROM token_usage WHERE week_key=?", (week_key(ts),)) or {}
    users = db.query_one("SELECT COUNT(*) AS n FROM usage_users") or {}
    by_provider = db.query_all(
        "SELECT provider, COUNT(*) AS runs, COALESCE(SUM(total_tokens),0) AS tokens "
        "FROM token_usage GROUP BY provider ORDER BY tokens DESC")
    by_mode = db.query_all(
        "SELECT mode, COUNT(*) AS runs, COALESCE(SUM(total_tokens),0) AS tokens "
        "FROM token_usage GROUP BY mode ORDER BY tokens DESC")
    return {
        "policy": pol,
        "users": int(users.get("n") or 0),
        "overrides": len(db.query_all("SELECT user_key FROM usage_limits")),
        "totals": {
            "runs": int(totals.get("runs") or 0),
            "tokens": int(totals.get("tokens") or 0),
            "prompt_tokens": int(totals.get("prompt_tokens") or 0),
            "completion_tokens": int(totals.get("completion_tokens") or 0),
        },
        "today": {"runs": int(today.get("runs") or 0),
                  "tokens": int(today.get("tokens") or 0),
                  "day_key": day_key(ts)},
        "this_week": {"runs": int(this_week.get("runs") or 0),
                      "tokens": int(this_week.get("tokens") or 0),
                      "week_key": week_key(ts)},
        "by_provider": by_provider,
        "by_mode": by_mode,
        "blocked_today": int(db.query_one(
            "SELECT COUNT(*) AS n FROM quota_rejections WHERE day_key=?",
            (day_key(ts),)).get("n") or 0),
    }


def record_rejection(user_key: str, reason: str, *, mode: str = "",
                     ts: float | None = None) -> None:
    """Simpan penolakan supaya admin tahu siapa yang kena limit dan kapan."""
    moment = ts if ts is not None else time.time()
    db.execute(
        "INSERT INTO quota_rejections(id, user_key, mode, reason, day_key, ts) "
        "VALUES(?,?,?,?,?,?)",
        (uuid.uuid4().hex[:12], user_key, mode, reason[:500], day_key(moment),
         moment),
    )
    touch_user(user_key, ts=moment)


def list_rejections(limit: int = 100) -> list[dict[str, Any]]:
    return db.query_all(
        "SELECT * FROM quota_rejections ORDER BY ts DESC LIMIT ?", (int(limit),))


def reset_user(user_key: str, *, scope: str = "day",
               ts: float | None = None) -> int:
    """Hapus pemakaian periode berjalan (tombol "reset kuota" di admin).

    Menghapus baris pemakaian, bukan menambah baris kompensasi, supaya angka
    di dashboard tetap konsisten dengan penjumlahan `token_usage`.
    """
    if scope == "week":
        rows = db.query_all(
            "SELECT id FROM token_usage WHERE user_key=? AND week_key=?",
            (user_key, week_key(ts)))
        db.execute("DELETE FROM token_usage WHERE user_key=? AND week_key=?",
                   (user_key, week_key(ts)))
    elif scope == "all":
        rows = db.query_all("SELECT id FROM token_usage WHERE user_key=?",
                            (user_key,))
        db.execute("DELETE FROM token_usage WHERE user_key=?", (user_key,))
    else:
        rows = db.query_all(
            "SELECT id FROM token_usage WHERE user_key=? AND day_key=?",
            (user_key, day_key(ts)))
        db.execute("DELETE FROM token_usage WHERE user_key=? AND day_key=?",
                   (user_key, day_key(ts)))
    return len(rows)
