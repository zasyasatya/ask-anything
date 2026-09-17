#!/usr/bin/env python3
"""Build docs/slides-admin-pipeline.pptx — versi PPTX dari deck HTML
docs/slides-admin-pipeline.html (cara kerja tiap pipeline + paket).

Dogfooding: memakai generator yang sama dengan tool `generate_ppt`.
Jalankan:  python scripts/build_admin_slides_pptx.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.tools.generate_ppt import build_pptx  # noqa: E402

TITLE = "Ask Anything — Admin Pipeline & Governance"

DECK = [
    {
        "title": "Kenapa perlu governance?",
        "bullets": [
            "Satu konsol admin mengatur mode, tool, memori, artifact, feedback, RAG",
            "Penegakan server-side: UI hanya menyembunyikan, API yang menolak",
            "Interpreter always-on: semua langkah terecord di SQLite (dikunci di kode)",
            "Semua fitur jalan offline (provider mock / HuggingFace lokal)",
        ],
    },
    {
        "title": "Alur chat yang di-govern",
        "bullets": [
            "Request {message, mode} → mode gate → prompt assembly",
            "System prompt = dasar + MEMORI + PEDOMAN FEEDBACK + arah mode",
            "Tool schema difilter: hanya tool diizinkan yang diiklankan",
            "Panggilan tool liar ditolak + event policy terecord",
            "Artifact (gambar/PPT) → file + registry + kartu unduh",
        ],
    },
    {
        "title": "Mode pipeline",
        "bullets": [
            "text — chat + agent browsing (inti)",
            "image — generate_image: poster offline / gateway OpenAI-compatible",
            "diagram — create_diagram: kanvas interaktif",
            "ppt — generate_ppt: deck .pptx dari outline",
            "rag — upload PDF → parse → chunk → embed → retrieve → generate",
            "research — deep research multi-query",
        ],
    },
    {
        "title": "Manajemen memori",
        "bullets": [
            "Tiga jalur tulis: admin manual, tool save_memory (AI), pedoman feedback",
            "Injection: blok MEMORI + PEDOMAN FEEDBACK di system prompt tiap run",
            "Perilaku berubah tanpa restart; asal memori selalu ber-badge",
            "Kontrol: memory.enabled, memory.allow_ai_write",
        ],
    },
    {
        "title": "Feedback 👍/👎 → pedoman perilaku",
        "bullets": [
            "Terecord lengkap: rating, komentar, message_id, mode, tools, cuplikan",
            "👎 + komentar → auto-guidance (memori source=feedback)",
            "Admin review: 'Jadikan pedoman' / abaikan / hapus",
            "Run berikutnya otomatis mematuhi pedoman (inject ke prompt)",
        ],
    },
    {
        "title": "Penyimpanan artifact",
        "bullets": [
            "File di data/artifacts/<id>_<nama>, metadata di tabel artifacts",
            "Generator gambar jujur: openai-images atau poster-v1 (offline)",
            "PPTX dibangun python-pptx dari outline terstruktur",
            "Registry FIFO (max_artifacts) + download endpoint publik",
        ],
    },
    {
        "title": "RAG — ingest (upload otomatis)",
        "bullets": [
            "POST /api/rag/upload → policy gate (mode + batas MB)",
            "Parsing pypdf per halaman; halaman rusak dilewati",
            "Chunking sliding window per halaman (1200 char, overlap 150)",
            "Embedding hashing-v1 384-dim (deterministik, tanpa server)",
            "Status per tahap terlihat di panel RAG + timings tersimpan",
        ],
    },
    {
        "title": "RAG — query (retrieve → generate)",
        "bullets": [
            "Embed query → cosine vs semua chunk ready → top-k + skor",
            "Context bernomor [1..k] + register sumber rag://…",
            "Generate streaming, wajib sitasi [n], diverifikasi final",
            "0 potongan cocok → diakui eksplisit, tidak mengarang",
            "Semua event (rag_stage, rag_retrieve) masuk interpreter",
        ],
    },
    {
        "title": "Mechanistic Interpreter (always-on)",
        "bullets": [
            "Record: meta+policy, prompt, LLM request/response, token, tool, RAG",
            "Event baru: rag_stage, rag_retrieve, artifact, policy",
            "always_on dikunci True — admin mengatur detail (logprobs, payload)",
            "Live saat run dan replay dari riwayat",
        ],
    },
    {
        "title": "Paket backend (Python)",
        "bullets": [
            "fastapi + uvicorn (SSE), pydantic-settings (env ASK_*), httpx",
            "pypdf (RAG parsing), python-multipart (upload), python-pptx (deck)",
            "beautifulsoup4 (browsing), pytest + pytest-asyncio (185+ tes)",
            "Opsional: torch/transformers untuk inference HuggingFace lokal",
        ],
    },
    {
        "title": "Paket frontend (Node)",
        "bullets": [
            "Next.js 16 + React 19 (App Router, proxy rewrite ke backend)",
            "Tailwind design system light/indigo, mermaid (mode pembanding)",
            "vitest + testing-library: 161 tes termasuk konsol admin",
            "Komponen baru: /admin, RagPanel, FeedbackButtons, ArtifactCards",
        ],
    },
    {
        "title": "Checklist sebelum publish",
        "bullets": [
            "Set ASK_ADMIN_TOKEN (header X-Admin-Token wajib)",
            "Review tab Pipeline: matikan mode/tool yang belum diinginkan",
            "Isi memori dasar (tone, batasan produk)",
            "Aktifkan feedback + auto-guidance; pantau rasio 👍/👎",
            "Upload dokumen RAG resmi; biarkan interpreter selalu-on",
        ],
    },
]


def main() -> None:
    out = ROOT / "docs" / "slides-admin-pipeline.pptx"
    data = build_pptx(TITLE, DECK)
    out.write_bytes(data)
    print(f"ok: {out} ({len(data) / 1024:.0f} KB, {len(DECK)} slide)")


if __name__ == "__main__":
    main()
