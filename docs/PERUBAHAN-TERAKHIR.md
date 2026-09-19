# Perubahan Terakhir

Dokumen ini merangkum perubahan yang **belum di-commit** (working tree) di atas
commit `1de20c7` (*Merge pull request #15*). Ringkasan dihasilkan dari `git diff`
nyata, bukan asumsi.

Skala perubahan: **25 file dimodifikasi + 10 file baru**, `+2119 / −73` baris
(belum termasuk file untracked).

## Ringkasan fitur baru

Ada empat fitur besar yang ditambahkan, semuanya ditegakkan di server dan
terekspos ke halaman `/admin`.

### 1. OCR untuk RAG — `backend/app/ocr.py` (baru)

Menutup celah dokumen hasil scan/foto yang sebelumnya masuk index sebagai
halaman kosong.

- `pypdf` hanya mengambil teks tertanam; halaman dengan teks < `ocr_min_chars`
  dianggap hasil scan (`needs_ocr`).
- Halaman dirender `pypdfium2` → bitmap → praproses (grayscale, upscale,
  deskew) → mesin OCR.
- Mesin berlapis: `rapidocr` (PP-OCRv4 di onnxruntime, murni wheel pip) lalu
  `tesseract` (bila `pytesseract` + binary tersedia).
- Upload gambar (`.png/.jpg/.webp/.bmp/.tif`) juga menjadi dokumen RAG.
- Tidak melempar bila tak ada mesin OCR: dokumen tetap diproses dengan teks
  yang ada, alasannya dilaporkan ke status dokumen + `/api/health`.
- Install: `pip install -r backend/requirements-ocr.txt` (file baru).

### 2. Kuota token per end user — `backend/app/quota.py` (baru)

Membuat pemakaian token terukur, tertegakkan di server, dan terlihat di admin.

- Identitas dari header `X-User-Id`, fallback ke IP (`normalise_user`).
- Alur: `resolve_user` → `check` (sebelum agent jalan) → `record` (dari event
  `usage`). Request yang melebihi batas ditolak lewat SSE `error` + event trace
  `quota`, agent tidak pernah dipanggil.
- Periode **berbasis kalender** (`day_key = YYYY-MM-DD`, `week_key = YYYY-Www`
  ISO) → reset otomatis tanpa scheduler.
- Batas berlapis: `usage_limits` (override per user) menang atas policy global.
  Nilai `0` = tanpa batas.
- `block_on_exceed=false` = mode pemantauan (dicatat tapi tidak diblokir).

### 3. Instruksi advanced / playbook — `backend/app/instructions.py` (baru)

Lapisan di atas memori: menjadikan asisten ahli domain dengan metode menjawab
tertentu.

- Struktur playbook: **domain + method + rules + format**.
- Katalog `THEORIES` siap pakai (IRAC, SOAP, Piramida Minto, Feynman,
  Socratic, dll.) sebagai *prosedur*, bukan deskripsi.
- Aktivasi: `always` / `keywords` (kata utuh) / `manual`.
- Playbook aktif dirangkai ke system prompt tiap run + direkam sebagai event
  `instructions` di Interpreter dan tabel `instruction_activations`, sehingga
  bisa diaudit playbook mana yang benar-benar terpakai.

### 4. Retrieval RAG hibrida — `backend/app/rag.py` (dimodifikasi, +418 baris)

Peningkatan besar pada kualitas retrieval.

- **BM25** (`bm25_scores`, `_BM25_K1=1.5`, `_BM25_B=0.75`) menangkap istilah
  persis (nomor pasal, kode produk, nama) yang embedding lewatkan.
- **Reciprocal Rank Fusion** (`reciprocal_rank_fusion`, `k=60`) menggabungkan
  peringkat vektor + leksikal (bukan skor mentah, karena skala BM25 dan cosine
  tidak sebanding).
- **MMR** (`mmr_select`, default `mmr_lambda=0.7`) membuang hasil duplikat.
- Perluasan konteks: `_with_neighbours` menyambung n chunk tetangga.
- Mode retrieval: `hybrid | vector | lexical`.
- Ingest kini berjalan di latar belakang (`ingest_file_background`) dengan
  status `queued → ocr → chunking → embedding → ready`.
- Rincian skor (`vector`/`lexical`/`fused`) tampil di Interpreter untuk audit.

## Perubahan pendukung

| Area | File | Isi |
|---|---|---|
| Policy default | `backend/app/governance.py` (+41) | Section baru `quota` & `instructions`; parameter retrieval (`retrieval_mode`, `retrieval_candidates`, `mmr_lambda`, `min_score`, `context_neighbors`) & OCR (`ocr_enabled`, `ocr_engine`, `ocr_min_chars`, `ocr_dpi`, `ocr_max_pages`, `ocr_deskew`); proyeksi kuota di `public_policy` |
| Skema DB | `backend/app/db.py` (+113) | Tabel untuk pemakaian kuota, override batas, aktivasi instruksi |
| Agent loop | `backend/app/agent/loop.py` (+84), `rag_loop.py` (+22) | Integrasi kuota (check/record) + injeksi playbook ke prompt |
| API admin | `backend/app/api/admin.py` (+190) | Endpoint CRUD kuota, instruksi (+preview pemicu), monitoring |
| API publik | `backend/app/api/routes.py` (+122) | `GET /api/quota/me`, `GET /api/rag/ocr`, upload gambar, ingest latar belakang |
| Startup | `backend/app/startup.py` (+27), `main.py` (+4) | Registrasi modul baru + warning kesiapan OCR |
| Inference lokal | `backend/app/local_inference.py` (+71) | Robustifikasi load/stream |
| Launcher | `run.py` (+118) | Pemasangan paket fitur inti |

## Frontend (admin console)

- `frontend/components/admin/QuotaTab.tsx` (baru) — monitoring kuota per user,
  batas efektif, override, reset, daftar penolakan.
- `frontend/components/admin/InstructionsTab.tsx` (baru) — CRUD playbook,
  katalog teori, uji pemicu tanpa memanggil model, statistik pemakaian.
- `frontend/components/admin/PipelineTab.tsx` (+115) — kontrol retrieval & OCR.
- `frontend/components/admin/AdminConsole.tsx` (+185) — integrasi tab baru.
- `frontend/lib/api.ts` (+146), `frontend/lib/types.ts` (+188) — client & tipe.

## Tes yang ditambahkan

- `backend/tests/test_ocr.py`
- `backend/tests/test_quota.py`
- `backend/tests/test_instructions.py`
- `backend/tests/test_rag_retrieval.py`
- Pembaruan: `test_rag.py`, `test_local_inference.py`,
  `test_autoload_and_loadpath.py`, `AdminConsole.test.tsx` (+219).

## Cara verifikasi

```bash
# Backend
.venv/Scripts/python -m pytest backend/tests -q

# Frontend
cd frontend
npm test
npx tsc --noEmit

# OCR (opsional)
pip install -r backend/requirements-ocr.txt
```

> Catatan: semua perubahan di atas masih **uncommitted**. Belum ada commit baru
> maupun perubahan yang di-stage.
