"""Pipeline governance — satu sumber kebijakan untuk apa yang boleh dijalankan.

Halaman admin mengatur **policy** ini; setiap permintaan pengguna melewati
gate di sini sebelum menyentuh model atau tool. Penegakan terjadi di server
(`agent/loop.py`, route chat/RAG/deep-research), bukan cuma menyembunyikan
tombol di UI — jadi policy tetap berlaku walau request dibuat langsung ke API.

Struktur policy (disimpan per-section sebagai JSON di tabel `admin_policy`):

  modes       — mode yang boleh dipakai user (text/image/diagram/ppt/rag/research)
  tools       — tool yang boleh dieksekusi agent (web_search, generate_ppt, …)
  memory      — manajemen memori (injection + boleh tulis oleh AI)
  rag         — parameter pipeline RAG (chunking, top-k, batas upload)
  feedback    — thumbs up/down + auto-guidance
  interpreter — mechanistic interpreter (selalu aktif; dikunci di kode)
  artifacts   — penyimpanan artefak (retensi, jumlah maksimum)
  quota       — batas token harian/mingguan per end user (lihat `quota.py`)

`always_on` interpreter sengaja tidak bisa dimatikan lewat API: dokumentasi dan
audit adalah janji produk ("semua langkah terecord"), bukan preferensi.
"""
from __future__ import annotations

import json
from typing import Any

from . import db

#: Mode yang bisa diatur admin (label UI ada di frontend).
MODES: tuple[str, ...] = ("text", "image", "diagram", "ppt", "rag", "research")

DEFAULT_POLICY: dict[str, dict[str, Any]] = {
    "modes": {m: True for m in MODES},
    "tools": {
        "web_search": True,
        "fetch_url": True,
        "create_diagram": True,
        "calculator": True,
        "generate_image": True,
        "generate_ppt": True,
        "save_memory": True,
    },
    "memory": {
        "enabled": True,        # injeksi memori ke system prompt
        "allow_ai_write": True, # tool save_memory boleh dipakai agent
    },
    "rag": {
        "chunk_size": 1200,     # karakter per chunk (sliding window)
        "chunk_overlap": 150,   # overlap antar chunk
        "top_k": 4,             # chunk yang diretrieval per pertanyaan
        "max_upload_mb": 25,    # batas ukuran PDF
        # --- Kecerdasan retrieval (lihat `rag.retrieve`) ---
        "retrieval_mode": "hybrid",   # hybrid | vector | lexical
        "retrieval_candidates": 50,   # kandidat yang di-rerank sebelum MMR
        "mmr_lambda": 0.7,            # 1.0 = murni relevansi, 0 = murni beragam
        "min_score": 0.0,             # buang hit cosine di bawah ini
        "context_neighbors": 0,       # sambung n chunk sebelum/sesudah (0 = mati)
        # --- OCR (PDF hasil scan & berkas gambar) — lihat `ocr.py` ---
        "ocr_enabled": True,
        "ocr_engine": "auto",   # auto | rapidocr | tesseract
        "ocr_min_chars": 80,    # halaman dgn teks < ini dianggap hasil scan
        "ocr_dpi": 200,         # resolusi render halaman sebelum OCR
        "ocr_max_pages": 40,    # pagar pengaman dokumen scan raksasa
        "ocr_deskew": True,     # luruskan halaman miring sebelum OCR
    },
    "feedback": {
        "enabled": True,        # tombol 👍/👎 tampil & direcord
        "auto_guidance": True,  # feedback 👎 + komentar → pedoman otomatis
        "max_guidance": 8,      # jumlah pedoman feedback yang di-inject
    },
    "interpreter": {
        # Dikunci: recorded selalu, apa pun isi policy (lihat validate below).
        "always_on": True,
        "record_logprobs": True,
        "record_tool_payloads": True,
    },
    "artifacts": {
        "max_artifacts": 500,   # registry dipangkas FIFO melewati batas ini
        "retention_days": 30,   # 0 = simpan selamanya (pembersihan manual)
    },
    "quota": {
        # Batas pemakaian token per END USER. 0 = tanpa batas untuk dimensi itu.
        # Periode berbasis kalender (hari & pekan ISO) → reset otomatis.
        "enabled": True,
        "daily_tokens": 100_000,
        "weekly_tokens": 500_000,
        "daily_requests": 300,
        # False = mode pemantauan: pemakaian tetap dicatat & dilaporkan, tapi
        # request tidak diblokir (berguna saat menakar batas sebelum diberlakukan).
        "block_on_exceed": True,
    },
    "instructions": {
        # Playbook domain + teori cara menjawab (lihat `instructions.py`).
        "enabled": True,
        "max_active": 3,        # playbook yang boleh aktif bersamaan per run
        "max_chars": 4000,      # batas panjang blok instruksi di system prompt
    },
}

# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def _load_overrides() -> dict[str, dict[str, Any]]:
    rows = db.query_all("SELECT key, value FROM admin_policy")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except (TypeError, ValueError):
            continue
    return out


def policy() -> dict[str, dict[str, Any]]:
    """Policy efektif = default di-merge dengan override admin (per-section)."""
    merged = {section: dict(values) for section, values in DEFAULT_POLICY.items()}
    for section, values in _load_overrides().items():
        if isinstance(values, dict) and section in merged:
            for k, v in values.items():
                if k in merged[section]:
                    merged[section][k] = v
    # Interpreter selalu aktif — bagian dari kontrak produk, bukan pengaturan.
    merged["interpreter"]["always_on"] = True
    return merged


def update_policy(patch: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Deep-merge patch per-section (hanya key yang dikenal yang tersentuh)."""
    current = policy()
    for section, values in (patch or {}).items():
        if section not in DEFAULT_POLICY or not isinstance(values, dict):
            continue
        clean = {k: v for k, v in values.items() if k in DEFAULT_POLICY[section]}
        merged = {**current[section], **clean}
        if section == "interpreter":
            merged["always_on"] = True  # tidak bisa dimatikan
        db.execute(
            "INSERT INTO admin_policy(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (section, json.dumps(merged)),
        )
    return policy()


# ---------------------------------------------------------------------------
# Gate helpers (dipakai agent loop + route)
# ---------------------------------------------------------------------------

def mode_allowed(mode: str) -> bool:
    return bool(policy()["modes"].get((mode or "text").strip().lower(), False))


def allowed_tools() -> list[str]:
    pol = policy()["tools"]
    return [name for name, on in pol.items() if on]


def tool_allowed(name: str) -> bool:
    return bool(policy()["tools"].get(name, False))


def public_policy() -> dict[str, Any]:
    """Subset yang aman dikirim ke browser (menggerakkan UI, bukan keamanan)."""
    pol = policy()
    return {
        "modes": pol["modes"],
        "tools": pol["tools"],
        "memory": pol["memory"],
        "feedback": pol["feedback"],
        "interpreter": pol["interpreter"],
        "rag": {
            "top_k": pol["rag"]["top_k"],
            "max_upload_mb": pol["rag"]["max_upload_mb"],
        },
        # Cukup untuk UI menampilkan sisa kuota; angka pemakaian nyata per user
        # diambil dari GET /api/quota/me (butuh identitas pemanggil).
        "quota": {
            "enabled": pol["quota"]["enabled"],
            "daily_tokens": pol["quota"]["daily_tokens"],
            "weekly_tokens": pol["quota"]["weekly_tokens"],
            "daily_requests": pol["quota"]["daily_requests"],
            "block_on_exceed": pol["quota"]["block_on_exceed"],
        },
        "labels": {
            "text": "Teks", "image": "Gambar", "diagram": "Diagram",
            "ppt": "PPT", "rag": "RAG", "research": "Deep Research",
        },
    }
