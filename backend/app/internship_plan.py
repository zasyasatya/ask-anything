"""Rencana proyek internship — **AI chatbot agent + RAG dari nol** (track sendiri).

Papan ini terpisah dari rencana platform (`tasks_plan.py`, id `ASK-NNN`): id di
sini memakai prefix `INT-NNN` dan halaman-nya `/internship`. Isinya adalah
penjabaran *Task Breakdown* di slide `docs/slides-rag-agent.html` (5 task besar)
menjadi task harian yang bisa dikerjakan berurutan oleh 2-3 orang intern.

Aturan yang sama dengan papan platform:
  * `id` (`INT-NNN`) dipakai di nama branch git (`feat/INT-007-…`),
  * `evidence` = berkas yang menandakan task selesai (di repo proyek baru
    `projects/rag-agent/…`), diperiksa `POST /api/tasks/sync`,
  * `acceptance` = kriteria selesai yang bisa dicentang,
  * `depends_on` = prasyarat (UI menandai task yang belum siap),
  * `source` = rujukan slide / dokumen (`docs/internship/*`).

Dokumen pendamping (dibaca intern sebelum mulai):
  docs/internship/01-spesifikasi-produk.md
  docs/internship/02-arsitektur-dan-tech-stack.md
  docs/internship/03-kontrak-api-dan-data.md
  docs/internship/04-rencana-sprint-dan-task.md
  docs/internship/05-kriteria-sukses-dan-demo.md
  docs/internship/06-panduan-kerja-dan-review.md
"""
from __future__ import annotations

from typing import Any

from .tasks_plan import PRIORITIES, STATUSES, STATUS_LABELS  # noqa: F401  (re-export)

#: Penanda papan (dipakai filter `/api/tasks?track=internship`).
TRACK = "internship"

#: Folder proyek baru di dalam repo ini (dokumentasi memakai path ini).
PROJECT_DIR = "projects/rag-agent"

PHASES: list[dict[str, str]] = [
    {"id": "i0", "name": "Fase 0 — Fondasi Proyek",
     "subtitle": "Repo, stack, kontrak API, docker-compose, kerangka streaming SSE."},
    {"id": "i1", "name": "Fase 1 — Ingest & Struktur Dokumen",
     "subtitle": "Upload PDF/DOCX/MD → parser structure-aware → chunking → simpan."},
    {"id": "i2", "name": "Fase 2 — Retrieval & Vector Store",
     "subtitle": "Embedding, Chroma/SQLite-vector, top-k + threshold, API query."},
    {"id": "i3", "name": "Fase 3 — Agent, Memori & Sesi",
     "subtitle": "ReAct loop, tool retrieve_knowledge, sitasi, memori, riwayat sesi."},
    {"id": "i4", "name": "Fase 4 — Visual Web Native",
     "subtitle": "create_chart/table/timeline/graph → registry renderer React."},
    {"id": "i5", "name": "Fase 5 — Polish, Demo & Serah Terima",
     "subtitle": "Uploader+chat+visual satu layar, export, test, dokumen, demo video."},
]

PHASE_IDS = tuple(p["id"] for p in PHASES)

#: Rujukan slide/dokumen yang paling sering dipakai di `source`.
_SLIDE = "slides: Task Breakdown (rag-agent)"
_STACK = "slides: Tech Stack"
_ARCH = "slides: Goal Architecture"
_SUCCESS = "slides: Kriteria Sukses"
_DOC = "docs/internship"

#: Berkas referensi di **ask-anything** yang bisa dibaca sebagai contoh pola
#: (bukan untuk di-copy: proyek baru ditulis sendiri, lihat dokumen 06).
REF = {
    "rag": "ask-anything: backend/app/rag.py",
    "agent": "ask-anything: backend/app/agent/loop.py",
    "tools": "ask-anything: backend/app/tools/__init__.py",
    "diagram": "ask-anything: backend/app/tools/diagrams.py",
    "sources": "ask-anything: backend/app/sources.py",
    "graph": "ask-anything: frontend/lib/graph/parseMermaid.ts",
    "graphview": "ask-anything: frontend/components/GraphView.tsx",
    "stream": "ask-anything: frontend/lib/live.ts",
    "db": "ask-anything: backend/app/db.py",
    "memory": "ask-anything: backend/app/memory.py",
}


def _t(task_id: str, title: str, phase: str, *, priority: str = "medium",
       estimate: float = 1.0, labels: tuple[str, ...] = (),
       description: str = "", acceptance: tuple[str, ...] = (),
       evidence: tuple[str, ...] = (), depends_on: tuple[str, ...] = (),
       source: str = "", status: str = "todo", assignee: str = "") -> dict[str, Any]:
    return {
        "id": task_id, "title": title, "phase": phase, "priority": priority,
        "estimate": estimate, "labels": list(labels),
        "description": description, "acceptance": list(acceptance),
        "evidence": list(evidence), "depends_on": list(depends_on),
        "source": source, "status": status, "assignee": assignee,
    }


_INTERN_LABELS = ("internship",)

#: Akun member contoh (dibuat otomatis saat backend pertama kali start, lihat
#: `users.ensure_seed_users`). Pembagian di bawah hanya titik awal — admin bisa
#: memindahkan task di papan /internship kapan saja.
INTERNS: tuple[str, ...] = ("intern1", "intern2", "intern3")

TASKS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- Fase 0
    _t("INT-001", "Setup repo proyek baru + struktur folder backend/frontend",
       "i0", priority="critical", estimate=0.5,
       labels=(*_INTERN_LABELS, "setup"),
       description="Buat folder projects/rag-agent/ berisi backend/ (FastAPI) dan "
                   "frontend/ (Next.js). Ikuti struktur di "
                   "docs/internship/02-arsitektur-dan-tech-stack.md; README proyek "
                   "menjelaskan cara menjalankan satu perintah.",
       acceptance=("Struktur folder sesuai dokumen 02",
                   "README proyek baru berisi cara setup & run",
                   "python -m venv + pip install -r requirements.txt jalan",
                   "npm install di frontend jalan"),
       evidence=(f"{PROJECT_DIR}/README.md", f"{PROJECT_DIR}/backend/requirements.txt"),
       source=f"{_DOC}/02-arsitektur-dan-tech-stack.md"),

    _t("INT-002", "Kontrak API & skema database disepakati",
       "i0", priority="critical", estimate=0.5,
       labels=(*_INTERN_LABELS, "design"),
       description="Tulis dokumen kontrak API (endpoint, request/response) dan "
                   "skema tabel SQLite (documents, chunks, conversations, "
                   "messages, memories) di proyek baru. Kontrak harus persis "
                   "seperti docs/internship/03-kontrak-api-dan-data.md supaya "
                   "frontend & backend bisa dikerjakan paralel.",
       acceptance=("Semua endpoint punya contoh request + response JSON",
                   "Skema tabel ditulis lengkap dengan tipe & index",
                   "Konvensi error (400/403/404) disepakati",
                   "Dokumen direview pembimbing"),
       evidence=(f"{PROJECT_DIR}/docs/API.md", f"{PROJECT_DIR}/docs/DATA-MODEL.md"),
       depends_on=("INT-001",), source=f"{_DOC}/03-kontrak-api-dan-data.md"),

    _t("INT-003", "Kerangka backend: health, config, logger, error handler",
       "i0", priority="high", estimate=1,
       labels=(*_INTERN_LABELS, "backend"),
       description="FastAPI app dengan /api/health, konfigurasi .env (kunci API, "
                   "path data), logging terstruktur, dan error handler yang "
                   "mengembalikan JSON rapi. Belum ada fitur AI: fokus fondasi.",
       acceptance=("/api/health membalas {status, version, provider}",
                   "Config dibaca dari .env (tanpa hardcode rahasia)",
                   "Error 4xx/5xx selalu JSON, bukan HTML traceback",
                   "Ada test pytest untuk health & config"),
       evidence=(f"{PROJECT_DIR}/backend/app/main.py",
                 f"{PROJECT_DIR}/backend/tests/test_health.py"),
       depends_on=("INT-001",), source=f"{_ARCH}"),

    _t("INT-004", "Kerangka frontend Next.js + Tailwind + proxy /api",
       "i0", priority="high", estimate=1,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Halaman shell (navbar, area konten), Tailwind, dan rewrite "
                   "/api/* ke backend sehingga browser tidak perlu tahu port "
                   "backend. Belum ada chat: cukup halaman kosong yang memanggil "
                   "/api/health dan menampilkan status.",
       acceptance=("npm run dev menampilkan shell halaman",
                   "Proxy /api/health mengembalikan data backend",
                   "Ada layout responsif dasar + komponen Navbar",
                   "npm run build lolos"),
       evidence=(f"{PROJECT_DIR}/frontend/app/page.tsx",
                 f"{PROJECT_DIR}/frontend/next.config.ts"),
       depends_on=("INT-001",), source=f"{_STACK}"),

    _t("INT-005", "docker-compose dev + seed script",
       "i0", priority="medium", estimate=0.5,
       labels=(*_INTERN_LABELS, "setup"),
       description="docker-compose.yml untuk menjalankan backend & frontend "
                   "sekaligus, plus scripts/seed.py yang mengisi 1 dokumen contoh "
                   "sehingga demo bisa langsung jalan.",
       acceptance=("docker compose up menjalankan kedua service",
                   "Data persist (volume) tidak hilang saat restart",
                   "scripts/seed.py idempoten",
                   "Cara pakai tertulis di README"),
       evidence=(f"{PROJECT_DIR}/docker-compose.yml", f"{PROJECT_DIR}/scripts/seed.py"),
       depends_on=("INT-003", "INT-004"), source=f"{_DOC}/02-arsitektur-dan-tech-stack.md"),

    # ---------------------------------------------------------------- Fase 1
    _t("INT-006", "Endpoint upload dokumen (multipart) + penyimpanan file",
       "i1", priority="critical", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "ingest"),
       description="POST /api/documents/upload menerima PDF/DOCX/MD/TXT, "
                   "menyimpan file asli di data/documents/{id}/original.*, dan "
                   "mencatat baris di tabel documents (nama, tipe, ukuran, "
                   "status). Validasi tipe & ukuran maksimum.",
       acceptance=("Upload PDF/DOCX/MD berhasil dan tercatat di DB",
                   "Tipe/ukuran tidak valid ditolak 4xx dengan pesan jelas",
                   "File tersimpan di folder per dokumen",
                   "Ada test upload (file kecil fixture)"),
       evidence=(f"{PROJECT_DIR}/backend/app/api/documents.py",
                 f"{PROJECT_DIR}/backend/tests/test_upload.py"),
       depends_on=("INT-002", "INT-003"), source=f"{_ARCH}"),

    _t("INT-007", "Parser PDF structure-aware (heading, tabel, flow)",
       "i1", priority="critical", estimate=2,
       labels=(*_INTERN_LABELS, "backend", "parser"),
       description="Ekstrak teks PDF beserta strukturnya memakai PyMuPDF "
                   "(blok/bbox/font-size) dan pdfplumber (tabel utuh). Hasilkan "
                   "structure.json berisi daftar elemen {type, level, text, page, "
                   "hierarchy} — tabel tidak boleh terpotong.",
       acceptance=("Heading terdeteksi dari ukuran font dan diberi level",
                   "Tabel diekstrak utuh sebagai satu elemen type=table",
                   "Output JSON valid & tersimpan di folder dokumen",
                   "Diuji pada minimal 3 PDF berbeda (termasuk hasil scan → pesan jelas)"),
       evidence=(f"{PROJECT_DIR}/backend/app/ingest/pdf_parser.py",
                 f"{PROJECT_DIR}/backend/tests/test_pdf_parser.py"),
       depends_on=("INT-006",), source=f"{_SLIDE} Task 1"),

    _t("INT-008", "Parser DOCX & Markdown/TXT",
       "i1", priority="high", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "parser"),
       description="python-docx untuk paragraf, heading & tabel; markdown-it "
                   "untuk .md; TXT dibaca apa adanya. Semua menghasilkan format "
                   "structure.json yang sama seperti parser PDF (satu kontrak "
                   "internal untuk seluruh pipeline).",
       acceptance=("DOCX dengan tabel & heading terparse benar",
                   "Markdown menghasilkan hierarchy dari ## heading",
                   "Format JSON identik dengan parser PDF",
                   "Ada test untuk tiap format"),
       evidence=(f"{PROJECT_DIR}/backend/app/ingest/docx_parser.py",
                 f"{PROJECT_DIR}/backend/app/ingest/md_parser.py"),
       depends_on=("INT-007",), source=f"{_SLIDE} Task 1"),

    _t("INT-009", "UI uploader drag & drop + preview struktur",
       "i1", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Komponen DocumentUploader (drag & drop, progress, daftar "
                   "dokumen) dan halaman preview struktur (tree view hierarchy "
                   "per halaman) supaya user bisa memastikan parser benar.",
       acceptance=("Drag & drop PDF/DOCX/MD mengunggah lewat proxy /api",
                   "Progress & error upload terlihat",
                   "Preview struktur menampilkan hierarki heading → paragraf/tabel",
                   "Dokumen bisa dihapus dari daftar"),
       evidence=(f"{PROJECT_DIR}/frontend/components/DocumentUploader.tsx",
                 f"{PROJECT_DIR}/frontend/app/documents/page.tsx"),
       depends_on=("INT-006", "INT-004"), source=f"{_SLIDE} Task 1"),

    _t("INT-010", "Chunking structure-aware (400 token, overlap 50)",
       "i1", priority="critical", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "rag"),
       description="Pecah struktur dokumen menjadi chunk yang menghormati batas "
                   "semantik: tabel & flow selalu utuh dalam satu chunk, heading "
                   "menempel ke paragraf pertamanya, sisa teks dipecah sliding "
                   "window ±400 token dengan overlap 50. Simpan metadata "
                   "(doc_id, page, hierarchy, type).",
       acceptance=("Tabel besar tidak pernah terpotong antar chunk",
                   "Setiap chunk punya metadata hierarchy lengkap",
                   "Ukuran chunk sesuai konfigurasi (.env) & bisa diubah",
                   "Ada unit test chunking dengan fixture dokumen"),
       evidence=(f"{PROJECT_DIR}/backend/app/rag/chunking.py",
                 f"{PROJECT_DIR}/backend/tests/test_chunking.py"),
       depends_on=("INT-007", "INT-008"), source=f"{_SLIDE} Task 2"),

    # ---------------------------------------------------------------- Fase 2
    _t("INT-011", "Embedding service (lokal all-MiniLM-L6-v2 + fallback offline)",
       "i2", priority="critical", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "rag"),
       description="Modul embedding: sentence-transformers all-MiniLM-L6-v2 "
                   "(384 dim) untuk kualitas, dengan fallback deterministik "
                   "hashing-v1 (tanpa unduhan model) supaya pipeline tetap bisa "
                   "diuji offline. Embedding di-cache per chunk.",
       acceptance=("Chunk tersimpan bersama vektor 384 dim",
                   "Fallback offline dipakai otomatis bila model belum ada",
                   "Ada test yang memverifikasi determinisme & kemiripan query",
                   "Waktu embed 100 chunk terukur (< 30 dtk lokal)"),
       evidence=(f"{PROJECT_DIR}/backend/app/rag/embeddings.py",
                 f"{PROJECT_DIR}/backend/tests/test_embeddings.py"),
       depends_on=("INT-010",), source=f"{_STACK} Embedding & Vector DB"),

    _t("INT-012", "Vector store (Chroma/SQLite) + simpan metadata hierarchy",
       "i2", priority="critical", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "rag"),
       description="Index chunk+vektor di Chroma persistent (data/chroma) atau "
                   "tabel SQLite + cosine bila Chroma tidak tersedia. Metadata: "
                   "doc_id, page, hierarchy, type, visualizable. Termasuk "
                   "re-index saat dokumen dihapus.",
       acceptance=("Chunk bisa ditambah/dihapus per dokumen",
                   "Query vektor mengembalikan chunk + skor + metadata",
                   "Index tetap konsisten setelah restart",
                   "Ada test store (tambah, cari, hapus)"),
       evidence=(f"{PROJECT_DIR}/backend/app/rag/store.py",
                 f"{PROJECT_DIR}/backend/tests/test_store.py"),
       depends_on=("INT-011",), source=f"{_STACK} Embedding & Vector DB"),

    _t("INT-013", "API retrieval: POST /api/rag/query (top-k + threshold + filter)",
       "i2", priority="critical", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "rag"),
       description="Endpoint retrieval murni (tanpa LLM): query → embedding → "
                   "top-k (default 5) dengan threshold kemiripan 0.7 dan filter "
                   "opsional (doc_id, type). Respons berisi contexts, scores, "
                   "metadata.",
       acceptance=("Query 'cuti tahunan' mengembalikan chunk tabel dari halaman yang benar",
                   "Parameter top_k/threshold/filter dihormati & tervalidasi",
                   "Skor kemiripan ikut dikembalikan",
                   "Test end-to-end ingest → query"),
       evidence=(f"{PROJECT_DIR}/backend/app/api/rag.py",
                 f"{PROJECT_DIR}/backend/tests/test_retrieval.py"),
       depends_on=("INT-012",), source=f"{_SLIDE} Task 2"),

    _t("INT-014", "Panel RAG: status dokumen & hasil retrieval",
       "i2", priority="high", estimate=1,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Panel di UI menampilkan status pipeline per dokumen "
                   "(uploaded → parsed → chunked → embedded → ready) beserta "
                   "jumlah chunk, plus daftar skor retrieval saat query dijalankan "
                   "supaya kualitas bisa dievaluasi tanpa buka log.",
       acceptance=("Status per dokumen tampil & berubah setelah ingest",
                   "Skor retrieval tampil per chunk (doc, page, hierarchy)",
                   "Tombol re-index / hapus dokumen bekerja",
                   "Gagal ingest menampilkan pesan sebabnya"),
       evidence=(f"{PROJECT_DIR}/frontend/components/RagPanel.tsx"),
       depends_on=("INT-013", "INT-009"), source=f"{_ARCH}"),

    _t("INT-015", "Evaluasi retrieval: dataset pertanyaan + laporan akurasi",
       "i2", priority="medium", estimate=1,
       labels=(*_INTERN_LABELS, "test", "rag"),
       description="Siapkan 15-20 pertanyaan uji beserta chunk yang seharusnya "
                   "muncul (ground truth) untuk 3 dokumen contoh, lalu script "
                   "evaluasi menghitung hit-rate/recall@k. Dipakai untuk "
                   "membandingkan strategi chunking & threshold.",
       acceptance=("Dataset uji tersimpan di repo (JSON/CSV)",
                   "Script evaluasi mencetak recall@k & rata-rata skor",
                   "Hasil dibandingkan minimal 2 konfigurasi chunking",
                   "Angka dilaporkan di dokumen 05 (kriteria sukses)"),
       evidence=(f"{PROJECT_DIR}/evaluation/questions.json",
                 f"{PROJECT_DIR}/evaluation/run_eval.py"),
       depends_on=("INT-013",), source=f"{_SUCCESS}"),

    # ---------------------------------------------------------------- Fase 3
    _t("INT-016", "Agent loop ReAct + streaming SSE",
       "i3", priority="critical", estimate=2,
       labels=(*_INTERN_LABELS, "backend", "agent"),
       description="Loop agent: susun prompt (system + history + tool schema) → "
                   "stream token LLM → jalankan tool_call → masukkan hasil sebagai "
                   "observasi → ulangi maksimal max_steps (6) → jawaban akhir. "
                   "Semua event di-stream ke frontend lewat SSE.",
       acceptance=("Chat streaming token-per-token di UI",
                   "Tool call dieksekusi dan hasilnya masuk konteks langkah berikutnya",
                   "Batas max_steps dipatuhi (tidak pernah loop tak berujung)",
                   "Timeout tool 30 dtk, error tool jadi data bukan crash"),
       evidence=(f"{PROJECT_DIR}/backend/app/agent/loop.py",
                 f"{PROJECT_DIR}/backend/tests/test_agent_loop.py"),
       depends_on=("INT-003",), source=f"{REF['agent']}"),

    _t("INT-017", "Tool retrieve_knowledge (RAG sebagai tool agent)",
       "i3", priority="critical", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "agent", "rag"),
       description="Bungkus pipeline retrieval menjadi tool agent "
                   "retrieve_knowledge {query, top_k, filter} yang mengembalikan "
                   "contexts + sumber bernomor. Daftarkan di registry tool supaya "
                   "otomatis masuk tool_schemas yang dikirim ke LLM.",
       acceptance=("Agent memanggil retrieve_knowledge untuk pertanyaan dokumen",
                   "Hasil retrieval masuk sources registry (untuk sitasi)",
                   "Deskripsi & JSON schema tool jelas (LLM tahu kapan memakainya)",
                   "Ada test: pertanyaan dokumen → tool terpanggil"),
       evidence=(f"{PROJECT_DIR}/backend/app/tools/retrieve_knowledge.py",
                 f"{PROJECT_DIR}/backend/tests/test_tool_retrieve.py"),
       depends_on=("INT-016", "INT-013"), source=f"{_SLIDE} Task 3"),

    _t("INT-018", "Prompt grounded + verifikasi sitasi [n] di server",
       "i3", priority="critical", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "agent"),
       description="System prompt mewajibkan jawaban hanya dari konteks + "
                   "menulis sitasi [1][2]. Backend memverifikasi setiap marker: "
                   "nomor yang tidak ada di sources ditandai (bukan ditampilkan "
                   "sebagai bukti), dan bila hasil retrieval kosong agent harus "
                   "mengatakan tidak tahu.",
       acceptance=("Jawaban menyertakan sitasi yang bisa diklik di UI",
                   "Nomor sitasi liar terdeteksi & ditandai (tidak dikarang)",
                   "Pertanyaan di luar dokumen → jawaban 'tidak tahu', bukan halusinasi",
                   "Ada test verifikasi sitasi (kasus valid & liar)"),
       evidence=(f"{PROJECT_DIR}/backend/app/agent/citations.py",
                 f"{PROJECT_DIR}/backend/tests/test_citations.py"),
       depends_on=("INT-017",), source=f"{REF['sources']}"),

    _t("INT-019", "Manajemen memori (simpan, injeksi, lupa)",
       "i3", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "memory"),
       description="Tabel memories + API CRUD. Memori aktif di-inject ke system "
                   "prompt setiap run sehingga perilaku berubah tanpa restart; "
                   "agent bisa menyimpan memori baru lewat tool save_memory "
                   "(dengan batas & sumber yang tercatat).",
       acceptance=("Tambah/edit/hapus memori lewat API & UI",
                   "Memori aktif terlihat di prompt run berikutnya",
                   "Memori punya sumber (user/agent) & status aktif",
                   "Memori yang dimatikan tidak ikut di prompt"),
       evidence=(f"{PROJECT_DIR}/backend/app/memory.py",
                 f"{PROJECT_DIR}/backend/tests/test_memory.py"),
       depends_on=("INT-016",), source=f"{REF['memory']}"),

    _t("INT-020", "Manajemen sesi: riwayat percakapan per user + lanjut sesi",
       "i3", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "frontend"),
       description="Simpan percakapan & pesan (termasuk sumber/jawaban) sehingga "
                   "user bisa membuka sesi lama, melanjutkannya, mengganti judul, "
                   "dan menghapusnya. Konteks N pesan terakhir dikirim ke LLM saat "
                   "melanjutkan.",
       acceptance=("Riwayat tampil & bisa dibuka kembali setelah restart",
                   "Melanjutkan sesi lama memakai konteks sebelumnya",
                   "Judul otomatis dari pesan pertama, bisa diganti",
                   "Hapus sesi membersihkan pesan & trace-nya"),
       evidence=(f"{PROJECT_DIR}/backend/app/api/conversations.py",
                 f"{PROJECT_DIR}/frontend/components/Sidebar.tsx"),
       depends_on=("INT-016", "INT-004"), source=f"{_DOC}/03-kontrak-api-dan-data.md"),

    _t("INT-021", "Frontend chat: streaming, chip tool, panel langkah agent",
       "i3", priority="high", estimate=2,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Halaman chat: kirim pertanyaan, render streaming token, "
                   "tampilkan chip tool yang dipanggil (retrieve_knowledge, "
                   "create_chart, …), dan panel langkah agent (panggilan, argumen, "
                   "durasi, hasil) supaya prosesnya transparan.",
       acceptance=("Streaming terlihat tanpa reload",
                   "Chip tool menampilkan nama, status, dan durasi",
                   "Panel langkah bisa dibuka/tutup",
                   "Error (API key kosong, dokumen kosong) tampil sebagai pesan, bukan layar putih"),
       evidence=(f"{PROJECT_DIR}/frontend/components/ChatView.tsx",
                 f"{PROJECT_DIR}/frontend/components/StepPanel.tsx"),
       depends_on=("INT-016", "INT-020"), source=f"{REF['stream']}"),

    _t("INT-022", "Artifact & jejak (trace) run tersimpan",
       "i3", priority="medium", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "agent"),
       description="Setiap run menyimpan jejak langkah (prompt, tool call, hasil, "
                   "metrik token) dan artefak keluaran (chart/table/diagram) di DB "
                   "sehingga bisa ditampilkan ulang saat sesi lama dibuka.",
       acceptance=("Trace run tersimpan & bisa dimuat ulang per sesi",
                   "Artefak punya metadata (jenis, judul, payload)",
                   "Ada endpoint untuk membaca trace & artefak",
                   "Test: buka sesi lama → langkah & artefak tetap ada"),
       evidence=(f"{PROJECT_DIR}/backend/app/artifacts.py",
                 f"{PROJECT_DIR}/backend/tests/test_artifacts.py"),
       depends_on=("INT-020",), source=f"{REF['db']}"),

    # ---------------------------------------------------------------- Fase 4
    _t("INT-023", "Tool create_chart & create_table (output JSON terstruktur)",
       "i4", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "backend", "visual"),
       description="Dua tool baru yang mengembalikan data terstruktur "
                   "({type:'chart', chart_type, data, x_key, y_key} dan "
                   "{type:'table', headers, rows}) — bukan string markdown. "
                   "Contoh pemakaian: mengubah tabel cuti hasil retrieval menjadi "
                   "bar chart.",
       acceptance=("Tool mengembalikan JSON tervalidasi (bukan string)",
                   "Argumen divalidasi & error dijelaskan ke model",
                   "Terdaftar otomatis di tool_schemas",
                   "Ada test untuk bentuk payload"),
       evidence=(f"{PROJECT_DIR}/backend/app/tools/create_chart.py",
                 f"{PROJECT_DIR}/backend/app/tools/create_table.py"),
       depends_on=("INT-017",), source=f"{_SLIDE} Task 4"),

    _t("INT-024", "Tool create_timeline & create_knowledge_graph",
       "i4", priority="medium", estimate=1,
       labels=(*_INTERN_LABELS, "backend", "visual"),
       description="Dua tool visual lanjutan: timeline dari langkah proses (mis. "
                   "alur SOP) dan knowledge graph relasi entitas (dokumen → "
                   "kebijakan → peran). Tetap mengembalikan JSON terstruktur.",
       acceptance=("Timeline & graph mengembalikan JSON sesuai kontrak",
                   "Data bisa berasal dari chunk bertipe flow/table",
                   "Ada test payload",
                   "Dokumentasi tool diperbarui"),
       evidence=(f"{PROJECT_DIR}/backend/app/tools/create_timeline.py",
                 f"{PROJECT_DIR}/backend/app/tools/create_knowledge_graph.py"),
       depends_on=("INT-023",), source=f"{_SLIDE} Task 4"),

    _t("INT-025", "Registry renderer + ChartRenderer & TableRenderer interaktif",
       "i4", priority="high", estimate=2,
       labels=(*_INTERN_LABELS, "frontend", "visual"),
       description="Peta `type → komponen React` (visualRegistry) dan dua renderer "
                   "pertama: bar/line/pie chart (sortable/filter) dan tabel "
                   "interaktif (sort kolom, scroll, ekspor CSV). Bukan Mermaid: "
                   "DOM native.",
       acceptance=("Payload chart/table dari tool langsung ter-render",
                   "Tabel bisa disortir per kolom",
                   "Chart punya label, legenda, dan fallback bila data kosong",
                   "Renderer tidak crash untuk payload asing (fallback JSON)"),
       evidence=(f"{PROJECT_DIR}/frontend/lib/visualRegistry.ts",
                 f"{PROJECT_DIR}/frontend/components/ChartRenderer.tsx",
                 f"{PROJECT_DIR}/frontend/components/TableRenderer.tsx"),
       depends_on=("INT-023", "INT-021"), source=f"{_SLIDE} Task 4"),

    _t("INT-026", "Renderer flowchart/graph & timeline (pan, zoom, drag)",
       "i4", priority="high", estimate=2,
       labels=(*_INTERN_LABELS, "frontend", "visual"),
       description="Renderer graph interaktif (pan/zoom/drag node/klik relasi) "
                   "untuk payload flowchart & knowledge graph, plus timeline "
                   "vertikal. Boleh meniru pola GraphView di ask-anything, tetapi "
                   "ditulis sendiri di proyek baru.",
       acceptance=("Node bisa di-drag, kanvas di-zoom/pan",
                   "Klik node menampilkan detail relasinya",
                   "Timeline menampilkan urutan kejadian dengan tanggal/langkah",
                   "Ada test util parse/layout (murni, tanpa DOM)"),
       evidence=(f"{PROJECT_DIR}/frontend/components/GraphView.tsx",
                 f"{PROJECT_DIR}/frontend/lib/graph/layout.ts"),
       depends_on=("INT-025",), source=f"{REF['graphview']}"),

    _t("INT-027", "Visual artifact: simpan, buka lagi, layar penuh",
       "i4", priority="medium", estimate=1,
       labels=(*_INTERN_LABELS, "frontend", "visual"),
       description="Visual hasil agent menjadi kartu artefak di percakapan "
                   "(tersimpan bersama pesan) yang bisa dibuka layar penuh, "
                   "diunduh sebagai JSON, dan dirender ulang identik saat sesi lama "
                   "dibuka.",
       acceptance=("Kartu visual muncul di dalam jawaban",
                   "Layar penuh & ekspor JSON bekerja",
                   "Membuka sesi lama menampilkan visual yang sama",
                   "Payload tersimpan juga di DB (bukan hanya state UI)"),
       evidence=(f"{PROJECT_DIR}/frontend/components/ArtifactCards.tsx"),
       depends_on=("INT-026", "INT-022"), source=f"{_SLIDE} Task 5"),

    # ---------------------------------------------------------------- Fase 5
    _t("INT-028", "Satu layar: dokumen | chat | visual + pilih knowledge base",
       "i5", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Susun layout 3 kolom (daftar dokumen, chat, panel visual) dan "
                   "filter dokumen yang dipakai untuk pertanyaan berikutnya "
                   "(multi-dokumen). Pilih dokumen → retrieval dibatasi ke "
                   "dokumen itu.",
       acceptance=("Layout 3 kolom rapi di desktop & tetap bisa dipakai di layar kecil",
                   "Memilih dokumen membatasi retrieval (terlihat di panel skor)",
                   "Status dokumen terlihat dari layout utama",
                   "Tidak ada state yang hilang saat berpindah dokumen"),
       evidence=(f"{PROJECT_DIR}/frontend/app/page.tsx"),
       depends_on=("INT-025", "INT-014"), source=f"{_SLIDE} Task 5"),

    _t("INT-029", "Sitasi interaktif + sumber terverifikasi di panel",
       "i5", priority="medium", estimate=1,
       labels=(*_INTERN_LABELS, "frontend"),
       description="Klik [1] pada jawaban → panel membuka chunk sumber lengkap "
                   "(dokumen, halaman, hierarchy) dengan highlight kutipan, dan "
                   "menandai bila ada nomor sitasi yang tidak terverifikasi.",
       acceptance=("Klik sitasi membuka sumber yang benar",
                   "Highlight kutipan di dalam chunk",
                   "Sitasi liar ditandai jelas",
                   "Berfungsi juga saat sesi lama dibuka ulang"),
       evidence=(f"{PROJECT_DIR}/frontend/components/CitationBar.tsx"),
       depends_on=("INT-018", "INT-028"), source=f"{_SUCCESS}"),

    _t("INT-030", "Ekspor percakapan + visual (Markdown/PDF)",
       "i5", priority="low", estimate=1,
       labels=(*_INTERN_LABELS, "frontend", "nice-to-have"),
       description="Tombol ekspor: percakapan + visual (chart/table/diagram) → "
                   "Markdown (wajib) dan PDF bila memungkinkan, supaya hasil "
                   "prototipe bisa dilampirkan ke laporan.",
       acceptance=("Ekspor Markdown berisi jawaban + sitasi",
                   "Payload visual disertakan (JSON/embedded)",
                   "Nama file memuat judul & tanggal",
                   "Gagal ekspor menampilkan pesan, bukan crash"),
       evidence=(f"{PROJECT_DIR}/frontend/lib/export.ts"),
       depends_on=("INT-028",), source=f"{_SUCCESS}"),

    _t("INT-031", "Test menyeluruh + coverage jalur utama",
       "i5", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "test"),
       description="Test backend (ingest → chunk → embed → retrieve → tool → "
                   "sitasi) dan frontend (renderer, chat streaming mock) sehingga "
                   "regresi ketahuan sebelum demo. Fokus jalur utama, bukan angka "
                   "coverage.",
       acceptance=("pytest backend hijau & mencakup jalur utama",
                   "Vitest frontend hijau untuk renderer & util",
                   "Ada test yang memastikan 'tidak tahu' saat retrieval kosong",
                   "CI lokal: satu perintah menjalankan semua test"),
       evidence=(f"{PROJECT_DIR}/backend/tests/test_pipeline_e2e.py",
                 f"{PROJECT_DIR}/frontend/lib/visualRegistry.test.ts"),
       depends_on=("INT-018", "INT-025", "INT-026"), source=f"{_SUCCESS}"),

    _t("INT-032", "Dokumentasi proyek + demo scenario & video",
       "i5", priority="high", estimate=1.5,
       labels=(*_INTERN_LABELS, "docs"),
       description="README proyek baru (arsitektur, cara jalan, keputusan teknis), "
                   "demo scenario 5 menit (upload SOP → tanya → flowchart → chart), "
                   "dan video/screenshot demo untuk serah terima ke pembimbing.",
       acceptance=("README bisa diikuti orang lain dari nol",
                   "Demo scenario tertulis langkah demi langkah",
                   "Ada video/screenshot bukti prototipe berjalan",
                   "Keterbatasan & rencana lanjutan jujur ditulis"),
       evidence=(f"{PROJECT_DIR}/README.md", f"{PROJECT_DIR}/docs/DEMO.md"),
       depends_on=("INT-028",), source=f"{_DOC}/05-kriteria-sukses-dan-demo.md"),

    _t("INT-033", "Review akhir & presentasi internal",
       "i5", priority="medium", estimate=0.5,
       labels=(*_INTERN_LABELS, "review"),
       description="Demo di depan pembimbing, bandingkan hasil dengan kriteria "
                   "sukses (must have & nice to have), catat utang teknis, dan "
                   "tentukan pekerjaan lanjutan bila prototipe diteruskan.",
       acceptance=("Semua kriteria 'must have' terpenuhi atau dijelaskan sebabnya",
                   "Utang teknis & batasan terdokumentasi",
                   "Papan task diperbarui (status akhir semua task)",
                   "Rencana lanjutan (bila ada) tertulis"),
       evidence=(f"{PROJECT_DIR}/docs/HANDOVER.md",),
       depends_on=("INT-032",), source=f"{_SUCCESS}"),
]


def _assign_round_robin() -> None:
    """Isi `assignee` yang belum di-set: intern1 → intern2 → intern3 → …"""
    for index, task in enumerate(TASKS):
        if not task.get("assignee"):
            task["assignee"] = INTERNS[index % len(INTERNS)]


_assign_round_robin()


def for_assignee(assignee: str) -> list[dict[str, Any]]:
    """Task milik satu orang (dipakai halaman /internship untuk member)."""
    name = (assignee or "").strip().lower()
    return [t for t in TASKS if (t.get("assignee") or "").lower() == name]


def summary() -> dict[str, Any]:
    """Ringkasan rencana intern (dipakai test, API, dan halaman /internship)."""
    per_phase: dict[str, int] = {p["id"]: 0 for p in PHASES}
    per_priority: dict[str, int] = {p: 0 for p in PRIORITIES}
    per_assignee: dict[str, int] = {}
    per_label: dict[str, int] = {}
    days = 0.0
    for t in TASKS:
        per_phase[t["phase"]] = per_phase.get(t["phase"], 0) + 1
        per_priority[t["priority"]] = per_priority.get(t["priority"], 0) + 1
        days += float(t["estimate"] or 0)
        if t.get("assignee"):
            per_assignee[t["assignee"]] = per_assignee.get(t["assignee"], 0) + 1
        for label in t.get("labels", []):
            per_label[label] = per_label.get(label, 0) + 1
    return {
        "track": TRACK,
        "project_dir": PROJECT_DIR,
        "phases": PHASES,
        "total": len(TASKS),
        "per_phase": per_phase,
        "per_priority": per_priority,
        "per_assignee": per_assignee,
        "per_label": per_label,
        "estimate_days": round(days, 1),
        "statuses": list(STATUSES),
        "status_labels": dict(STATUS_LABELS),
    }
