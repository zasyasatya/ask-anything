"""Pipeline governance — satu sumber kebijakan untuk apa yang boleh dijalankan.

Halaman admin mengatur **policy** ini; setiap permintaan pengguna melewati
gate di sini sebelum menyentuh model atau tool. Penegakan terjadi di server
(`agent/loop.py`, route chat/RAG/deep-research), bukan cuma menyembunyikan
tombol di UI — jadi policy tetap berlaku walau request dibuat langsung ke API.

Struktur policy (disimpan per-section sebagai JSON di tabel `admin_policy`):

  modes       — mode yang boleh dipakai user (text/image/diagram/ppt/rag/research)
  tools       — tool yang boleh dieksekusi agent (web_search, generate_ppt, …)
  roles       — batas per peran (admin | member): mode & tool yang boleh,
                akses model offline & setelan provider, unggah dokumen RAG,
                dan cakupan papan task (semua task vs hanya yang ditugaskan)
  memory      — manajemen memori (injection + boleh tulis oleh AI)
  rag         — parameter pipeline RAG (chunking, top-k, batas upload)
  feedback    — thumbs up/down + auto-guidance
  interpreter — mechanistic interpreter (selalu aktif; dikunci di kode)
  artifacts   — penyimpanan artefak (retensi, jumlah maksimum)
  quota       — batas token harian/mingguan per end user (lihat `quota.py`)

Mode/tool yang benar-benar berlaku bagi seorang user = global (section `modes`
/ `tools`) **AND** izin perannya (`roles.<peran>`). Jadi mematikan mode global
selalu menang, dan member tidak bisa naik sendiri ke fitur admin.

Aturan default untuk member: playground (teks, diagram, RAG) boleh; mode
gambar/PPT/deep-research, model offline (HuggingFace lokal), setelan provider,
dan unggah dokumen ke knowledge base tidak. Semua ini bisa diubah admin di
konsol Admin → Pipeline (bagian "Akses per peran") dan tetap ditegakkan di
server — bukan hanya disembunyikan di UI.

`always_on` interpreter sengaja tidak bisa dimatikan lewat API: dokumentasi dan
audit adalah janji produk ("semua langkah terecord"), bukan preferensi.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from . import db

#: Mode yang bisa diatur admin (label UI ada di frontend).
MODES: tuple[str, ...] = ("text", "image", "diagram", "ppt", "rag", "research")

#: Tool yang bisa diatur admin (urutan = urutan tampilan di UI).
TOOLS: tuple[str, ...] = (
    "web_search", "fetch_url", "create_diagram", "calculator",
    "generate_image", "generate_ppt", "save_memory",
)

#: Peran yang punya policy sendiri.
ROLES: tuple[str, ...] = ("admin", "member")

#: Flag non-mode/tool per peran (dipakai `auth.capabilities` & penegakan route).
ROLE_FLAGS: tuple[str, ...] = (
    "allow_offline_models",     # /api/hf/* : unduh/muat model HuggingFace lokal
    "allow_provider_settings",  # POST /api/settings : ganti provider/base URL/key
    "allow_admin_console",      # /api/admin/*
    "allow_rag_upload",         # POST /api/rag/upload : menambah knowledge base
    "allow_task_write",         # ubah status/komentar task yang ditugaskan
)

#: Nilai teks per peran (bukan boolean).
ROLE_ENUMS: dict[str, tuple[str, ...]] = {
    "chat_provider": ("openai", "auto"),   # "openai" = model offline tak pernah dipakai
    "tasks_scope": ("assigned", "all"),    # "assigned" = hanya task untuk dirinya
}

_DEFAULT_MEMBER: dict[str, Any] = {
    # Playground untuk member: teks, diagram, dan tanya-jawab dokumen (RAG).
    "modes": {
        "text": True, "diagram": True, "rag": True,
        "image": False, "ppt": False, "research": False,
    },
    # Tool yang aman untuk member (tanpa generate gambar/PPT & tanpa tulis memori).
    "tools": {
        "web_search": True, "fetch_url": True, "create_diagram": True,
        "calculator": True, "generate_image": False, "generate_ppt": False,
        "save_memory": False,
    },
    "allow_offline_models": False,   # hanya model OpenAI (bukan model offline)
    "allow_provider_settings": False,
    "allow_admin_console": False,
    "allow_rag_upload": False,       # member menanyai knowledge base, bukan mengubahnya
    "allow_task_write": True,        # boleh update status/komentar task sendiri
    "chat_provider": "openai",
    "tasks_scope": "assigned",
}

_DEFAULT_ADMIN: dict[str, Any] = {
    "modes": {m: True for m in MODES},
    "tools": {t: True for t in TOOLS},
    "allow_offline_models": True,
    "allow_provider_settings": True,
    "allow_admin_console": True,
    "allow_rag_upload": True,
    "allow_task_write": True,
    "chat_provider": "auto",
    "tasks_scope": "all",
}

DEFAULT_POLICY: dict[str, Any] = {
    "modes": {m: True for m in MODES},
    "tools": {t: True for t in TOOLS},
    "roles": {"admin": _DEFAULT_ADMIN, "member": _DEFAULT_MEMBER},
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


def policy() -> dict[str, Any]:
    """Policy efektif = default di-merge dengan override admin (per-section).

    Section `roles` di-merge dua tingkat (peran → key → nilai) supaya
    mengubah satu peran tidak menghapus setelan peran lainnya.
    """
    merged: dict[str, Any] = {
        section: (copy.deepcopy(values) if isinstance(values, dict) else values)
        for section, values in DEFAULT_POLICY.items()
    }
    for section, values in _load_overrides().items():
        if not isinstance(values, dict) or section not in merged:
            continue
        if section == "roles":
            _merge_roles(merged["roles"], values)
            continue
        for k, v in values.items():
            if k in merged[section]:
                merged[section][k] = v
    # Interpreter selalu aktif — bagian dari kontrak produk, bukan pengaturan.
    merged["interpreter"]["always_on"] = True
    return merged


def _merge_roles(target: dict[str, Any], patch: dict[str, Any]) -> None:
    """Merge peran (nested): `{member: {modes: {...}, allow_…: false}}`."""
    for role, values in (patch or {}).items():
        if role not in target or not isinstance(values, dict):
            continue
        bucket = target[role]
        for key, value in values.items():
            if key in ("modes", "tools") and isinstance(value, dict):
                allowed = bucket.get(key) or {}
                for name, flag in value.items():
                    if name in allowed:
                        allowed[name] = bool(flag)
            elif key in ROLE_FLAGS:
                bucket[key] = bool(value)
            elif key in ROLE_ENUMS and str(value) in ROLE_ENUMS[key]:
                bucket[key] = str(value)


def update_policy(patch: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Deep-merge patch per-section (hanya key yang dikenal yang tersentuh)."""
    current = policy()
    for section, values in (patch or {}).items():
        if section not in DEFAULT_POLICY or not isinstance(values, dict):
            continue
        if section == "roles":
            merged_roles = copy.deepcopy(current["roles"])
            _merge_roles(merged_roles, values)
            db.execute(
                "INSERT INTO admin_policy(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (section, json.dumps(merged_roles)),
            )
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

def normalise_role(role: str | None) -> str:
    """Peran yang dikenal; `None`/tidak dikenal → `member` (paling ketat)."""
    role = (role or "").strip().lower()
    return role if role in ROLES else "member"


def _check_role(role: str | None) -> str:
    """Peran untuk pemeriksaan izin. `None` = periksa gerbang **global**
    (perilaku lama `mode_allowed("rag")` = "boleh secara umum?"), bukan izin
    member — supaya pemanggil lama tidak ikut terkena batas member."""
    return normalise_role(role) if role else "admin"


def role_policy(role: str | None) -> dict[str, Any]:
    """Izin satu peran (default + override admin)."""
    return policy()["roles"].get(normalise_role(role), _DEFAULT_MEMBER)


def role_allows(role: str | None, flag: str) -> bool:
    if flag not in ROLE_FLAGS:
        return False
    return bool(role_policy(role).get(flag))


def role_setting(role: str | None, key: str, default: str = "") -> str:
    value = role_policy(role).get(key, default)
    return str(value) if value else default


def effective_modes(role: str | None = None) -> dict[str, bool]:
    """Mode berlaku = global AND peran (memisahkan izin admin vs member)."""
    pol = policy()
    per_role = role_policy(_check_role(role))["modes"]
    return {m: bool(pol["modes"].get(m)) and bool(per_role.get(m))
            for m in MODES}


def effective_tools(role: str | None = None) -> dict[str, bool]:
    pol = policy()
    per_role = role_policy(_check_role(role))["tools"]
    return {t: bool(pol["tools"].get(t)) and bool(per_role.get(t))
            for t in TOOLS}


def mode_allowed(mode: str, role: str | None = None) -> bool:
    return bool(effective_modes(role).get((mode or "text").strip().lower(), False))


def allowed_tools(role: str | None = None) -> list[str]:
    return [name for name, on in effective_tools(role).items() if on]


def tool_allowed(name: str, role: str | None = None) -> bool:
    return bool(effective_tools(role).get(name, False))


def public_policy(role: str | None = "admin") -> dict[str, Any]:
    """Subset yang aman dikirim ke browser (menggerakkan UI, bukan keamanan).

    Mode & tool yang dikirim adalah yang **berlaku untuk peran pemanggil**,
    jadi UI member tidak menampilkan tombol yang akan ditolak server.
    """
    pol = policy()
    role = normalise_role(role)
    rp = role_policy(role)
    return {
        "role": role,
        "modes": effective_modes(role),
        "tools": effective_tools(role),
        "roles": {
            role: {
                "modes": rp["modes"],
                "tools": rp["tools"],
                **{flag: bool(rp.get(flag)) for flag in ROLE_FLAGS},
                "chat_provider": rp.get("chat_provider", "openai"),
                "tasks_scope": rp.get("tasks_scope", "assigned"),
            }
        },
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
