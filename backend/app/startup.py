"""Catatan startup — kenapa backend jalan dalam mode terbatas (kalau ada).

Backend harus **selalu hidup** walau sub-sistem opsional gagal: model lokal
rusak (Windows: `OSError WinError 1114` pada `torch/lib/c10.dll`), folder model
tak bisa dibuat, autoload gagal, dsb. Kegagalan seperti itu dulu bisa membuat
uvicorn mati saat startup → `run.py` melaporkan "backend did not become
healthy" tanpa petunjuk apa pun.

Sekarang setiap masalah dicatat di sini (bukan dilempar), lalu:
  * diteruskan ke `/api/health` (`warnings`) supaya UI & `run.py` bisa
    menampilkan sebab yang sebenarnya,
  * dicetak ke stdout backend (masuk `data/backend.log`).

Isi modul ini sengaja tanpa dependensi lain agar aman diimpor kapan saja.
"""
from __future__ import annotations

import time
from typing import Any

#: daftar catatan (terbaru terakhir). Maksimum dijaga agar tidak tumbuh terus.
_NOTES: list[dict[str, Any]] = []
_MAX = 40


def add(component: str, message: str, hint: str = "", detail: str = "") -> dict:
    """Catat satu masalah startup (tidak pernah melempar)."""
    note = {
        "component": component,
        "message": " ".join(str(message).split()),
        "hint": " ".join(str(hint).split()),
        "detail": " ".join(str(detail).split())[:1200],
        "ts": time.time(),
    }
    _NOTES.append(note)
    if len(_NOTES) > _MAX:
        del _NOTES[0 : len(_NOTES) - _MAX]
    print(f"[startup:{component}] {note['message']}"
          + (f" → {note['hint']}" if note["hint"] else ""), flush=True)
    return note


def notes() -> list[dict[str, Any]]:
    return [dict(n) for n in _NOTES]


def clear() -> None:
    _NOTES.clear()


def ok() -> bool:
    return not _NOTES
