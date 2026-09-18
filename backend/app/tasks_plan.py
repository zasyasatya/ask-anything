"""Rencana kerja Ask Anything — sumber data papan task (`/tasks`).

Isi berkas ini adalah **rencana RAG + AI Agent** (slides `docs/slides-rag-agent.html`)
yang sudah dijabarkan jadi task-task kecil, ditambah pekerjaan platform
(Admin Console: Pipeline/Memori/Artifact/Feedback, mode Gambar/PPT/RAG,
interpreter selalu-on) yang diminta dalam rencana yang sama.

Aturan penulisan:
  * `id` berbentuk `ASK-NNN` — **kode ini dipakai di nama branch GitLab**
    (`feat/ASK-012-judul-singkat`), jadi jangan pernah mengubahnya setelah
    dipakai; buat task baru dengan nomor berikutnya.
  * `evidence` = berkas/glob yang menandakan task benar-benar sudah dikerjakan.
    `POST /api/tasks/sync` memeriksa ini dan menaikkan status ke `review`
    (tidak pernah menurunkan status yang sudah lebih maju).
  * `acceptance` = kriteria selesai (checklist di UI, bisa dicentang manual).
  * `depends_on` = prasyarat; dipakai UI untuk menandai task yang belum siap.

Data murni (tanpa I/O) supaya mudah diuji dan dipakai ulang oleh seeder.
"""
from __future__ import annotations

from typing import Any

#: Kolom papan (urutan = urutan kolom di UI).
STATUSES: tuple[str, ...] = ("backlog", "todo", "in_progress", "review", "done")
STATUS_LABELS: dict[str, str] = {
    "backlog": "Backlog",
    "todo": "To do",
    "in_progress": "In progress",
    "review": "Review",
    "done": "Done",
}
PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
PRIORITY_LABELS: dict[str, str] = {
    "low": "Low", "medium": "Medium", "high": "High", "critical": "Critical",
}

PHASES: list[dict[str, str]] = [
    {"id": "f0", "name": "Fase 0 — Platform & Governance",
     "subtitle": "Admin console, policy server-side, mode Gambar/PPT/RAG, interpreter."},
    {"id": "f1", "name": "Fase 1 — Ingest & Struktur Dokumen",
     "subtitle": "Upload → parser structure-aware → chunking → penyimpanan."},
    {"id": "f2", "name": "Fase 2 — Retrieval & Pipeline RAG",
     "subtitle": "Embedding, vector store, top-k, threshold, sitasi, panel RAG."},
    {"id": "f3", "name": "Fase 3 — Agent × RAG",
     "subtitle": "Tool retrieve_knowledge, prompt grounded, verifikasi sitasi."},
    {"id": "f4", "name": "Fase 4 — Visual Web Native",
     "subtitle": "Tool → JSON terstruktur → renderer React (chart/table/timeline)."},
    {"id": "f5", "name": "Fase 5 — Polish, Demo & Dokumentasi",
     "subtitle": "Integrasi UI, export, performa, test, demo scenario."},
]

PHASE_IDS = tuple(p["id"] for p in PHASES)


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


#: Slide/task besar dari rencana — dipakai untuk label & pengelompokan.
_BREAKDOWN = "slides: Task Breakdown"
_SUCCESS = "slides: Kriteria Sukses"

TASKS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- Fase 0
    _t("ASK-001", "Tab Pipeline: toggle 6 mode & 7 tool + parameter",
       "f0", priority="critical", estimate=2,
       labels=("admin", "governance"),
       description="Konsol admin punya tab Pipeline: toggle mode (Teks, Gambar, "
                   "Diagram, PPT, RAG, Deep Research) dan tool (web_search, "
                   "fetch_url, create_diagram, calculator, generate_image, "
                   "generate_ppt, save_memory), plus parameter RAG, memori, "
                   "feedback, dan interpreter.",
       acceptance=("6 mode tampil sebagai toggle dan tersimpan ke policy",
                   "7 tool tampil sebagai toggle dan tersimpan ke policy",
                   "Parameter RAG (chunk_size/overlap/top_k/max_upload_mb) bisa diubah",
                   "Interpreter tampil terkunci (always_on)"),
       evidence=("backend/app/governance.py",
                 "frontend/components/admin/PipelineTab.tsx"),
       source=_BREAKDOWN),

    _t("ASK-002", "Penegakan policy di server (bukan hanya UI)",
       "f0", priority="critical", estimate=2,
       labels=("admin", "security"),
       description="Mode yang dimatikan ditolak API (403/SSE error); tool yang "
                   "dimatikan tidak diiklankan ke model; panggilan liar (tool di "
                   "luar allowlist) ditolak dan tercatat di interpreter.",
       acceptance=("Chat dengan mode mati → ditolak server, bukan hanya tombol hilang",
                   "Tool mati tidak ada di tool_schemas yang dikirim ke model",
                   "Panggilan tool liar → event `policy` terecord & ditolak",
                   "Ada test otomatis untuk ketiga jalur di atas"),
       evidence=("backend/app/governance.py", "backend/tests/test_governance.py"),
       depends_on=("ASK-001",), source=_BREAKDOWN),

    _t("ASK-003", "Kunci konsol admin dengan ASK_ADMIN_TOKEN",
       "f0", priority="high", estimate=1,
       labels=("admin", "security"),
       description="Bila env ASK_ADMIN_TOKEN diset, semua endpoint /api/admin/* "
                   "mewajibkan header X-Admin-Token; UI menyimpan token di "
                   "localStorage dan menampilkan badge terkunci/terbuka.",
       acceptance=("Tanpa token → 401 saat env diset",
                   "Header X-Admin-Token benar → 200",
                   "UI menandai status terlindungi/terbuka"),
       evidence=("backend/app/api/admin.py", "backend/tests/test_admin_api.py",
                 "frontend/components/admin/AdminConsole.tsx"),
       depends_on=("ASK-001",), source=_BREAKDOWN),

    _t("ASK-004", "Parameter pipeline RAG dipakai sungguhan oleh RAG",
       "f0", priority="high", estimate=1,
       labels=("admin", "rag"),
       description="Nilai chunk_size/overlap/top_k/max_upload_mb dari policy "
                   "benar-benar dipakai ingesti & retrieval (bukan hanya angka "
                   "di UI), dan berubah tanpa restart.",
       acceptance=("Ubah top_k di admin → jumlah chunk yang diretrieval berubah",
                   "Upload melebihi max_upload_mb ditolak 413",
                   "Chunking memakai chunk_size + overlap dari policy"),
       evidence=("backend/app/rag.py", "backend/app/governance.py"),
       depends_on=("ASK-001",), source=_BREAKDOWN),

    _t("ASK-005", "Tab Memori: CRUD + badge asal + injeksi ke system prompt",
       "f0", priority="high", estimate=2,
       labels=("admin", "memory"),
       description="CRUD memori (admin/AI/feedback) dengan badge asal; semua "
                   "memori aktif di-inject ke system prompt setiap run sehingga "
                   "perubahan langsung mengubah perilaku AI tanpa restart.",
       acceptance=("Tambah/edit/hapus/disable memori dari UI",
                   "Badge membedakan sumber admin, AI, feedback",
                   "Memori aktif muncul di system prompt run berikutnya (terekam di trace)"),
       evidence=("backend/app/memory.py", "frontend/components/admin/MemoryTab.tsx",
                 "backend/tests/test_memory_feedback.py"),
       source=_BREAKDOWN),

    _t("ASK-006", "Tab Artifact: daftar keluaran + unduh/hapus + asal run",
       "f0", priority="medium", estimate=1.5,
       labels=("admin", "artifacts"),
       description="Semua keluaran biner (gambar, PPTX, dokumen) teregistry "
                   "dengan kind, ukuran, run asal, dan bisa diunduh/dihapus dari "
                   "konsol admin; kartu unduh juga muncul di chat.",
       acceptance=("Daftar artifact + filter kind",
                   "Tombol unduh & hapus berfungsi",
                   "Tercatat conversation_id/run_id asal artifact"),
       evidence=("backend/app/artifacts.py",
                 "frontend/components/admin/ArtifactTab.tsx",
                 "frontend/components/ArtifactCards.tsx"),
       source=_BREAKDOWN),

    _t("ASK-007", "Tab Feedback: 👍/👎 + komentar + 'Jadikan pedoman'",
       "f0", priority="high", estimate=2,
       labels=("admin", "feedback"),
       description="Feedback dari chat terecord lengkap dengan konteks run "
                   "(pertanyaan, jawaban, mode, tool yang dipakai). Tombol "
                   "'Jadikan pedoman' mengubah feedback → memori; 👎 + komentar "
                   "bisa auto-jadi pedoman.",
       acceptance=("👍/👎 tersimpan dengan konteks run",
                   "Komentar 👎 bisa jadi pedoman (manual & otomatis)",
                   "Pedoman hasil feedback muncul di tab Memori dengan badge feedback"),
       evidence=("backend/app/feedback.py", "frontend/components/admin/FeedbackTab.tsx",
                 "frontend/components/FeedbackButtons.tsx"),
       source=_BREAKDOWN),

    _t("ASK-008", "Mode Gambar: poster offline / gateway OpenAI → artifact",
       "f0", priority="high", estimate=2,
       labels=("mode", "tools"),
       description="Mode 🖼️ Gambar: tool generate_image membuat poster "
                   "(generator offline deterministik, atau gateway OpenAI bila "
                   "API key diset) dan hasilnya jadi artifact dengan kartu unduh "
                   "di chat.",
       acceptance=("Mode Gambar bisa dipilih di composer",
                   "Hasil tersimpan sebagai artifact kind=image + kartu unduh",
                   "Mode mati di policy → ditolak server"),
       evidence=("backend/app/tools/generate_image.py",
                 "frontend/components/ArtifactCards.tsx"),
       source=_BREAKDOWN),

    _t("ASK-009", "Mode PPT: deck .pptx via python-pptx → artifact",
       "f0", priority="high", estimate=2,
       labels=("mode", "tools"),
       description="Mode 📊 PPT: tool generate_ppt merakit deck .pptx dari "
                   "outline terstruktur (judul + bullet + catatan) memakai "
                   "python-pptx, lalu artifact-nya bisa diunduh dari chat.",
       acceptance=("Deck .pptx valid (bisa dibuka PowerPoint/LibreOffice)",
                   "Artifact kind=pptx dengan judul & ukuran benar",
                   "Tool gagal rapi (pesan jelas) bila python-pptx absen"),
       evidence=("backend/app/tools/generate_ppt.py",),
       source=_BREAKDOWN),

    _t("ASK-010", "Mode RAG: upload PDF → chunk → embed → retrieve → sitasi",
       "f0", priority="critical", estimate=3,
       labels=("mode", "rag"),
       description="Upload PDF otomatis: parsing (pypdf) → chunking per halaman → "
                   "embedding hashing deterministik 384-dim → retrieval cosine "
                   "top-k → generation dengan sitasi [n] terverifikasi backend.",
       acceptance=("Upload PDF → dokumen berstatus ready dengan jumlah chunk",
                   "Query menjawab dari dokumen + sitasi [n] terverifikasi",
                   "Tidak relevan → menjawab tidak tahu (threshold)"),
       evidence=("backend/app/rag.py", "backend/app/agent/rag_loop.py",
                 "backend/app/sources.py", "backend/tests/test_rag.py"),
       source=_SUCCESS),

    _t("ASK-011", "Interpreter selalu-on + event baru (rag_stage, artifact, policy)",
       "f0", priority="high", estimate=2,
       labels=("interpreter", "observability"),
       description="Interpreter dikunci di kode (bukan preferensi) dan merekam "
                   "event baru: rag_stage, rag_retrieve (dengan skor), artifact, "
                   "policy — semuanya bisa di-replay dari riwayat percakapan.",
       acceptance=("always_on tetap true walau API mencoba mematikannya",
                   "Panel RAG menampilkan skor retrieval tiap tahap",
                   "Event baru muncul di timeline dan ikut ter-replay"),
       evidence=("backend/app/agent/loop.py", "backend/app/agent/rag_loop.py",
                 "frontend/components/Interpreter.tsx"),
       depends_on=("ASK-010",), source=_BREAKDOWN),

    _t("ASK-012", "Bonus fix: system prompt benar-benar dikirim ke provider",
       "f0", priority="high", estimate=0.5,
       labels=("agent", "bugfix"),
       description="System prompt + blok MEMORI sebelumnya hanya terekam di trace "
                   "tetapi tidak pernah dikirim ke provider. Sekarang disusun di "
                   "satu tempat dan dikirim konsisten ke semua provider.",
       acceptance=("Prompt provider memuat system prompt (dibuktikan test)",
                   "Blok memori ikut terkirim saat ada memori aktif",
                   ("Semua provider (hf lokal/server, openai, mock) berperilaku sama")),
       evidence=("backend/app/agent/prompts.py", "backend/app/providers/base.py"),
       source=_BREAKDOWN),

    _t("ASK-013", "Perbaiki startup backend + preflight dependency di run.py",
       "f0", priority="critical", estimate=1,
       labels=("devx", "bugfix"),
       description="Backend tidak boleh mati karena sub-sistem opsional: autoload "
                   "model jalan di background thread & dicatat, folder model "
                   "gagal dibuat tidak mematikan server, route multipart absen "
                   "jadi 503 (bukan crash saat import). run.py melakukan "
                   "preflight `import app.main`, memperbaiki paket yang hilang, "
                   "dan menampilkan ekor data/backend.log saat health check gagal.",
       acceptance=("python run.py sehat walau torch rusak / python-multipart hilang",
                   "Health check gagal → sebab asli tercetak dari log",
                   "/api/health memuat `warnings` + `autoload`"),
       evidence=("backend/app/startup.py", "backend/app/main.py", "run.py"),
       source=_BREAKDOWN),

    _t("ASK-014", "Halaman task management (papan kanban + list)",
       "f0", priority="high", estimate=3,
       labels=("devx", "tracker"), status="in_progress",
       description="Halaman /tasks untuk developer: papan kanban drag & drop, "
                   "filter (fase/status/assignee/prioritas/pencarian), detail "
                   "task (checklist, komentar, dependency), statistik progres, "
                   "dan sinkronisasi branch/commit git → status task.",
       acceptance=("Board + list view, drag & drop antar kolom",
                   "Task punya ID ASK-NNN yang dipakai sebagai nama branch",
                   "Sinkronisasi git (branch/commit) memperbarui papan",
                   "Seed otomatis berisi seluruh rencana RAG"),
       evidence=("backend/app/tasks.py", "frontend/app/tasks/page.tsx"),
       source=_BREAKDOWN),

    # ---------------------------------------------------------------- Fase 1
    _t("ASK-015", "Endpoint upload dokumen (PDF/DOCX/MD) multipart",
       "f1", priority="high", estimate=1.5,
       labels=("ingest", "api"),
       description="POST /api/documents/upload menerima PDF/DOCX/MD multipart, "
                   "memvalidasi tipe & ukuran dari policy, lalu meneruskan ke "
                   "parser. Menggantikan jalur khusus PDF saat ini.",
       acceptance=("Menerima pdf, docx, md (tolak tipe lain dengan pesan jelas)",
                   "Batas ukuran dari policy rag.max_upload_mb",
                   "Respons memuat id dokumen + ringkasan tahap parsing"),
       evidence=("backend/app/api/routes.py", "backend/app/rag.py"),
       depends_on=("ASK-013",), source=_BREAKDOWN),

    _t("ASK-016", "Parser struktur PDF (heading, tabel, flow)",
       "f1", priority="high", estimate=3,
       labels=("parser", "ingest"),
       description="Ekstrak struktur, bukan text blob: heading berdasarkan font "
                   "size, tabel (pdfplumber), blok flow, plus nomor halaman → "
                   "disimpan sebagai structure.json.",
       acceptance=("Heading level terdeteksi dan berurutan",
                   "Tabel utuh (headers + rows) dengan nomor halaman",
                   "structure.json tersimpan per dokumen"),
       evidence=("backend/app/rag.py",),
       depends_on=("ASK-015",), source=_BREAKDOWN),

    _t("ASK-017", "Parser DOCX (paragraph, heading, tabel)",
       "f1", priority="medium", estimate=2,
       labels=("parser", "ingest"),
       description="Dukungan .docx via python-docx: paragraf, heading level dari "
                   "style, dan tabel → struktur yang sama dengan parser PDF.",
       acceptance=("DOCX dengan heading + tabel menghasilkan struktur sama bentuknya",
                   "Nomor halaman/hierarki tetap terekam (atau ditandai '-' )",
                   "Ada unit test dengan file DOCX contoh"),
       depends_on=("ASK-016",), source=_BREAKDOWN),

    _t("ASK-018", "Penyimpanan dokumen: data/documents/{id}/ + tabel documents",
       "f1", priority="medium", estimate=1.5,
       labels=("ingest", "storage"),
       description="Simpan file asli sebagai data/documents/{id}/original.pdf + "
                   "structure.json, dan registry di tabel documents (name, type, "
                   "pages, structure_path, created_at).",
       acceptance=("File & struktur ada di disk dengan id yang sama dengan DB",
                   "Hapus dokumen membersihkan file + chunk + registry",
                   "Halaman admin/RAG bisa menelusuri asal dokumen"),
       depends_on=("ASK-016",), source=_BREAKDOWN),

    _t("ASK-019", "Chunking structure-aware (400 token, overlap 50)",
       "f1", priority="critical", estimate=3,
       labels=("chunking", "rag"),
       description="Chunking mengikuti struktur: tabel/flow tidak dipotong, "
                   "heading digabung dengan paragraf berikutnya, hierarki "
                   "tersimpan sebagai metadata chunk.",
       acceptance=("Tabel & flow menjadi satu chunk utuh",
                   "Metadata chunk memuat doc_id, page, hierarchy, type",
                   "Ada unit test: chunk tidak pernah memotong tabel"),
       evidence=("backend/app/rag.py", "backend/tests/test_rag.py"),
       depends_on=("ASK-016",), source=_BREAKDOWN),

    _t("ASK-020", "Pembersihan dokumen sebelum embedding",
       "f1", priority="low", estimate=1,
       labels=("chunking", "quality"),
       description="Buang header/footer berulang, nomor halaman, dan spasi "
                   "berlebih sebelum chunking supaya embedding tidak berisi noise.",
       acceptance=("Header/footer berulang terdeteksi & dibuang",
                   "Konten tetap utuh (tidak ada kalimat hilang)",
                   "Terlihat di panel RAG sebagai tahap 'clean'"),
       depends_on=("ASK-018",), source=_BREAKDOWN),

    _t("ASK-021", "UI DocumentUploader drag & drop + preview struktur",
       "f1", priority="medium", estimate=2,
       labels=("frontend", "ingest"),
       description="Komponen uploader drag & drop dengan daftar dokumen dan "
                   "preview struktur (tree view hierarki) supaya user yakin "
                   "dokumennya terbaca benar.",
       acceptance=("Drag & drop + progress upload",
                   "Tree view hierarki muncul setelah parsing",
                   "Error parsing ditampilkan, tidak menelan berkas diam-diam"),
       evidence=("frontend/components/RagPanel.tsx",),
       depends_on=("ASK-015",), source=_BREAKDOWN),

    # ---------------------------------------------------------------- Fase 2
    _t("ASK-022", "Embedding: model lokal + fallback hashing 384-dim",
       "f2", priority="high", estimate=2,
       labels=("embedding", "rag"),
       description="Gunakan sentence-transformers (all-MiniLM-L6-v2) bila tersedia; "
                   "bila tidak, pakai embedding hashing deterministik 384-dim "
                   "(offline, tanpa unduhan model) agar RAG tetap jalan.",
       acceptance=("Tidak ada jaringan wajib untuk ingest",
                   "Dimensi & backend embedding tercatat di dokumen",
                   "Skor cosine masuk akal (query mirip > query tak relevan)"),
       evidence=("backend/app/rag.py",), source=_BREAKDOWN),

    _t("ASK-023", "Vector store persistent + metadata lengkap",
       "f2", priority="high", estimate=2,
       labels=("retrieval", "storage"),
       description="Simpan vektor secara persisten (Chroma bila tersedia; "
                   "fallback SQLite + cosine) beserta metadata doc_id, page, "
                   "hierarchy, type, visualizable.",
       acceptance=("Restart backend → indeks tetap ada tanpa re-embed",
                   "Metadata ikut terbawa ke hasil retrieval",
                   "Hapus dokumen menghapus vektor terkait"),
       evidence=("backend/app/rag.py",), depends_on=("ASK-022",),
       source=_BREAKDOWN),

    _t("ASK-024", "POST /api/rag/query → top-k + skor + metadata",
       "f2", priority="high", estimate=1.5,
       labels=("retrieval", "api"),
       description="Endpoint query mengembalikan top-k chunk dengan skor "
                   "similarity dan metadata, siap dipakai agent maupun UI.",
       acceptance=("Respons memuat chunk, skor, dan metadata",
                   "top_k mengikuti policy",
                   "Query kosong ditolak 422"),
       evidence=("backend/app/api/routes.py", "backend/app/rag.py"),
       depends_on=("ASK-023",), source=_BREAKDOWN),

    _t("ASK-025", "Metadata filtering (doc_ids, type=table/flow)",
       "f2", priority="medium", estimate=1.5,
       labels=("retrieval",),
       description="Filter pencarian: hanya di dokumen tertentu, atau hanya tipe "
                   "tertentu (table/flow/list) — dipakai tool retrieve_knowledge "
                   "dan UI filter dokumen.",
       acceptance=("Filter doc_ids & type bekerja di API",
                   "UI bisa memilih dokumen knowledge base per pertanyaan",
                   "Ada test untuk filter kombinasi"),
       depends_on=("ASK-024",), source=_BREAKDOWN),

    _t("ASK-026", "Threshold similarity + jawaban 'tidak tahu'",
       "f2", priority="high", estimate=1,
       labels=("retrieval", "grounding"),
       description="Bila skor tertinggi di bawah ambang, agent menjawab tidak ada "
                   "informasi di dokumen (bukan mengarang), dan ambang bisa diatur "
                   "di policy.",
       acceptance=("Ambang bisa diubah dari konsol admin",
                   "Kasus tidak relevan dijawab 'tidak tahu' + alasan skor",
                   "Event rag_retrieve mencatat skor tertinggi & keputusan"),
       evidence=("backend/app/agent/rag_loop.py",), depends_on=("ASK-024",),
       source=_SUCCESS),

    _t("ASK-027", "Panel RAG: setiap tahap pipeline terlihat di UI",
       "f2", priority="medium", estimate=1.5,
       labels=("frontend", "observability"),
       description="Panel RAG menampilkan tahap parsing → chunking → embedding → "
                   "retrieval (dengan skor) untuk setiap run, sinkron dengan "
                   "interpreter.",
       acceptance=("Tahap muncul berurutan dengan status & durasi",
                   "Skor retrieval tampil per chunk",
                   "Komponen punya test render"),
       evidence=("frontend/components/RagPanel.tsx",),
       depends_on=("ASK-024",), source=_BREAKDOWN),

    _t("ASK-028", "Sitasi [n] terverifikasi di backend",
       "f2", priority="high", estimate=1.5,
       labels=("citation", "grounding"),
       description="Sitasi yang diklaim model diverifikasi terhadap sumber yang "
                   "benar-benar diretrieval; sitasi palsu ditandai/dibuang, dan "
                   "klik sitasi membuka sumbernya.",
       acceptance=("Sitasi tanpa sumber valid tidak ditampilkan",
                   "Sumber menyimpan potongan teks + halaman",
                   "Ada test sitasi palsu ditolak"),
       evidence=("backend/app/sources.py", "backend/tests/test_sources_citations.py"),
       depends_on=("ASK-024",), source=_SUCCESS),

    _t("ASK-029", "Test end-to-end: query 'cuti tahunan' → chunk tabel p2",
       "f2", priority="medium", estimate=1,
       labels=("testing", "rag"),
       description="Test regresi sesuai demo scenario slide: query 'cuti tahunan' "
                   "harus mengembalikan chunk tabel halaman 2 sebagai hasil teratas.",
       acceptance=("Test berjalan tanpa jaringan & tanpa model besar",
                   "Assert chunk teratas memuat tabel cuti",
                   "Ikut dijalankan di CI"),
       depends_on=("ASK-024",), source=_SUCCESS),

    # ---------------------------------------------------------------- Fase 3
    _t("ASK-030", "Tool retrieve_knowledge (query, top_k, filter)",
       "f3", priority="critical", estimate=2,
       labels=("agent", "tools", "rag"),
       description="Tool baru backend/app/tools/rag.py dengan argumen query, "
                   "top_k, filter (doc_id/type); mengembalikan konteks + sumber "
                   "untuk sitasi.",
       acceptance=("Tool terdaftar otomatis di registry → muncul di tool_schemas",
                   "Argumen tervalidasi (query wajib, top_k dibatasi)",
                   "Tool mati di policy → tidak diiklankan ke model"),
       depends_on=("ASK-024", "ASK-019"), source=_BREAKDOWN),

    _t("ASK-031", "Tool result: source='knowledge' + evidence=True",
       "f3", priority="high", estimate=1,
       labels=("agent", "citation"),
       description="Hasil tool masuk registry sumber dengan source='knowledge' dan "
                   "evidence=True sehingga bisa disitasi & diaudit di interpreter.",
       acceptance=("Sumber 'knowledge' muncul di daftar sitasi",
                   "Potongan konteks + halaman tersimpan untuk audit",
                   "Terlihat di interpreter sebagai sumber, bukan teks biasa"),
       depends_on=("ASK-030",), source=_BREAKDOWN),

    _t("ASK-032", "Prompt: jawab hanya dari konteks + wajib sitasi",
       "f3", priority="high", estimate=1,
       labels=("prompt", "grounding"),
       description="System prompt run RAG/agent menginstruksikan: jawab hanya dari "
                   "konteks, sertakan sitasi [n], dan katakan tidak tahu bila "
                   "konteks tidak memuat jawaban.",
       acceptance=("Prompt memuat aturan sitasi & larangan mengarang",
                   "Instruksi ikut terekam di trace prompt",
                   "Diuji lewat test prompt provider (system prompt terkirim)"),
       evidence=("backend/app/agent/prompts.py", "backend/app/agent/rag_loop.py"),
       depends_on=("ASK-012",), source=_BREAKDOWN),

    _t("ASK-033", "Batas konteks (top-k ≤ 5) + peringkasan chunk panjang",
       "f3", priority="medium", estimate=1,
       labels=("agent", "quality"),
       description="Jaga konteks tetap ramping: batasi jumlah chunk dan potong/"
                   "ringkas chunk sangat panjang supaya LLM tidak bingung.",
       acceptance=("top_k efektif ≤ 5",
                   "Chunk panjang dipotong di batas aman + ditandai",
                   "Test: konteks tidak melebihi budget karakter"),
       depends_on=("ASK-030",), source=_BREAKDOWN),

    _t("ASK-034", "Agent loop: mode RAG & agent biasa berbagi tool yang sama",
       "f3", priority="medium", estimate=2,
       labels=("agent", "rag"),
       description="Mode RAG memakai loop yang sama dengan mode teks (tool, "
                   "interpreter, sitasi) sehingga retriever bisa dikombinasikan "
                   "dengan create_diagram/create_chart.",
       acceptance=("Mode RAG bisa memanggil tool visual",
                   "Trace tetap terurut dan bisa di-replay",
                   "Tidak ada jalur kode ganda untuk tool"),
       evidence=("backend/app/agent/rag_loop.py", "backend/app/agent/loop.py"),
       depends_on=("ASK-030",), source=_BREAKDOWN),

    _t("ASK-035", "Reranker (bge-reranker) — nice to have",
       "f3", priority="low", estimate=2,
       labels=("retrieval", "nice-to-have"),
       description="Setelah top-k awal, urutkan ulang hasil dengan cross-encoder "
                   "bila tersedia; fallback mulus bila model tidak ada.",
       acceptance=("Reranker opsional: tanpa model → hasil tetap wajar",
                   "Skor sebelum/sesudah rerank terekam di interpreter",
                   "Bisa dinyalakan lewat env/policy"),
       depends_on=("ASK-024",), source=_SUCCESS),

    # ---------------------------------------------------------------- Fase 4
    _t("ASK-036", "Tool create_chart → JSON terstruktur",
       "f4", priority="high", estimate=2,
       labels=("visual", "tools"),
       description="Tool create_chart mengembalikan JSON terstruktur "
                   "({type:'bar', data, x_key, y_key}) — bukan string gambar — "
                   "supaya frontend bisa merender komponen interaktif.",
       acceptance=("Skema argumen tervalidasi (data, type, x_key, y_key)",
                   "Dipakai model setelah retrieve tabel",
                   "Hasil terecord sebagai artifact/di chat"),
       depends_on=("ASK-030",), source=_BREAKDOWN),

    _t("ASK-037", "Tool create_table (sortable) → JSON",
       "f4", priority="medium", estimate=1.5,
       labels=("visual", "tools"),
       description="create_table mengembalikan {type:'table', columns, rows} yang "
                   "bisa disortir/difilter user, menggantikan tabel markdown statis.",
       acceptance=("Kolom & baris terstruktur (bukan string pipe)",
                   "Sel bisa memuat penanda sitasi [n]",
                   "Ada test skema output"),
       depends_on=("ASK-036",), source=_BREAKDOWN),

    _t("ASK-038", "Tool create_timeline → JSON",
       "f4", priority="low", estimate=1.5,
       labels=("visual", "tools"),
       description="create_timeline untuk data berurutan (SOP, jadwal, milestone) "
                   "dengan {type:'timeline', events:[{when, title, detail}]}.",
       acceptance=("Urutan event dipertahankan",
                   "Renderer menampilkan tanggal + judul + detail",
                   "Argumen tanggal lentur (ISO atau teks bebas)"),
       depends_on=("ASK-036",), source=_BREAKDOWN),

    _t("ASK-039", "visualRegistry: type → komponen React",
       "f4", priority="high", estimate=1,
       labels=("frontend", "visual"),
       description="Registry tunggal (lib/visualRegistry.ts) yang memetakan tipe "
                   "visual dari tool ke komponen React, sehingga menambah visual "
                   "baru tidak menyentuh chat/DiagramBlock.",
       acceptance=("Semua tipe visual terdaftar di satu tempat",
                   "Tipe tak dikenal punya fallback aman (JSON mentah)",
                   "Ada unit test registry"),
       depends_on=("ASK-036",), source=_BREAKDOWN),

    _t("ASK-040", "ChartRenderer.tsx (bar/line/pie) interaktif",
       "f4", priority="high", estimate=2,
       labels=("frontend", "visual"),
       description="Renderer chart berbasis DOM/SVG (tanpa dependensi baru): "
                   "hover menampilkan nilai, label sumbu, dan skala otomatis.",
       acceptance=("Bar/line/pie tampil dari JSON tool",
                   "Hover menampilkan nilai; label panjang dipotong rapi",
                   "Ada test render"),
       depends_on=("ASK-039",), source=_SUCCESS),

    _t("ASK-041", "TableRenderer.tsx (sortable + filter)",
       "f4", priority="medium", estimate=1.5,
       labels=("frontend", "visual"),
       description="Tabel interaktif: klik header untuk sortir, kotak pencarian, "
                   "dan penanda sel yang mengandung sitasi.",
       acceptance=("Sortir naik/turun per kolom",
                   "Pencarian memfilter baris",
                   "Sel dengan [n] bisa diklik ke sumber"),
       depends_on=("ASK-039",), source=_SUCCESS),

    _t("ASK-042", "TimelineRenderer.tsx",
       "f4", priority="low", estimate=1.5,
       labels=("frontend", "visual"),
       description="Komponen timeline vertikal untuk create_timeline dengan "
                   "penanda fase dan detail yang bisa dibuka.",
       acceptance=("Tampil rapi di mobile & desktop",
                   "Detail bisa dibuka/tutup",
                   "Ada test render"),
       depends_on=("ASK-039",), source=_BREAKDOWN),

    _t("ASK-043", "DiagramBlock extend: graph + mermaid + chart/table/timeline",
       "f4", priority="high", estimate=2,
       labels=("frontend", "visual"),
       description="DiagramBlock (yang sudah menangani mermaid & graph JSON) "
                   "diarahkan lewat visualRegistry sehingga semua tipe visual "
                   "memakai jalur render yang sama.",
       acceptance=("Mermaid lama tetap jalan (regresi aman)",
                   "Tipe chart/table/timeline dirender lewat registry",
                   "Fullscreen & tombol buka di tab baru tetap berfungsi"),
       evidence=("frontend/components/DiagramBlock.tsx",),
       depends_on=("ASK-039",), source=_BREAKDOWN),

    _t("ASK-044", "Export visual (PNG/SVG) + artefak diagram",
       "f4", priority="low", estimate=1.5,
       labels=("frontend", "visual"),
       description="Unduh visual sebagai gambar/SVG atau simpan sebagai artifact "
                   "supaya hasil agent bisa dibawa keluar aplikasi.",
       acceptance=("Tombol unduh menghasilkan berkas valid",
                   "Visual tersimpan sebagai artifact kind=diagram",
                   "Berfungsi untuk graph, chart, dan tabel"),
       depends_on=("ASK-043",), source=_SUCCESS),

    # ---------------------------------------------------------------- Fase 5
    _t("ASK-045", "Layout 3 kolom: dokumen | chat | visual",
       "f5", priority="medium", estimate=3,
       labels=("frontend", "integration"),
       description="Gabungkan uploader dokumen, chat, dan panel visual dalam satu "
                   "halaman kerja agar alur upload → tanya → visual terasa satu "
                   "kesatuan (dengan mode fokus di layar kecil).",
       acceptance=("Tiga kolom di desktop, satu kolom di mobile",
                   "Kolom dokumen & visual bisa dilipat",
                   "Tidak ada scroll ganda yang mengganggu"),
       depends_on=("ASK-043", "ASK-021"), source=_BREAKDOWN),

    _t("ASK-046", "Filter dokumen knowledge base per pertanyaan",
       "f5", priority="medium", estimate=1,
       labels=("frontend", "rag"),
       description="User memilih dokumen mana yang jadi knowledge base untuk "
                   "pertanyaan berikutnya; pilihan dikirim sebagai document_ids.",
       acceptance=("Multi-select dokumen di composer",
                   "Pilihan tampil di trace run",
                   "Kosong berarti semua dokumen"),
       evidence=("backend/app/api/routes.py",),
       depends_on=("ASK-025",), source=_BREAKDOWN),

    _t("ASK-047", "Sitasi klik → scroll & highlight chunk sumber",
       "f5", priority="medium", estimate=1.5,
       labels=("frontend", "citation"),
       description="Klik [n] pada jawaban membuka panel sumber, menggulir ke chunk "
                   "yang dipakai dan menyorotnya.",
       acceptance=("Klik sitasi membuka + menyorot potongan sumber",
                   "Sorotan menghilang setelah beberapa detik",
                   "Konsisten untuk jawaban text & RAG"),
       depends_on=("ASK-028",), source=_SUCCESS),

    _t("ASK-048", "Performance: batch embedding, cache, lazy load",
       "f5", priority="medium", estimate=2,
       labels=("performance",),
       description="Ingest besar tidak boleh memblokir UI: batch embedding, cache "
                   "hasil embedding per hash chunk, dan lazy load panel berat.",
       acceptance=("1000+ chunk ter-ingest tanpa UI membeku",
                   "Re-upload dokumen sama → memakai cache",
                   "Ada benchmark sederhana di test"),
       depends_on=("ASK-023",), source=_SUCCESS),

    _t("ASK-049", "Export hasil chat + visual → PDF/MD",
       "f5", priority="low", estimate=2,
       labels=("export",),
       description="Ekspor percakapan (termasuk visual & sitasi) ke Markdown atau "
                   "PDF supaya bisa dilampirkan ke laporan.",
       acceptance=("Markdown memuat jawaban, sitasi, dan blok visual",
                   "PDF rapi (visual tidak terpotong)",
                   "Nama berkas memuat judul percakapan + tanggal"),
       depends_on=("ASK-044",), source=_BREAKDOWN),

    _t("ASK-050", "Error handling & graceful degradation",
       "f5", priority="high", estimate=1.5,
       labels=("reliability",),
       description="Kegagalan tool/LLM/embedding menjadi data yang terlihat user "
                   "(pesan jelas + jejak di interpreter), bukan crash atau "
                   "jawaban kosong.",
       acceptance=("Tool gagal → pesan actionable di chat + event error",
                   "Provider mati → banner status, chat tidak menggantung",
                   "Tidak ada traceback bocor ke UI"),
       evidence=("backend/app/agent/loop.py", "frontend/components/ChatView.tsx"),
       source=_BREAKDOWN),

    _t("ASK-051", "Test otomatis: chunking, embedding, retrieval, API, UI",
       "f5", priority="high", estimate=3,
       labels=("testing",),
       description="Lapisan test untuk unit (chunking/embedding/retrieval), API "
                   "(policy, tasks, rag) dan komponen frontend (renderer visual, "
                   "board task) supaya refactor aman.",
       acceptance=("pytest hijau tanpa jaringan/model besar",
                   "vitest hijau untuk komponen visual & tasks",
                   "CI menjalankan keduanya"),
       evidence=("backend/tests/test_rag.py", "frontend/vitest.config.ts"),
       source=_SUCCESS),

    _t("ASK-052", "Demo scenario 5 skenario slide jadi checklist uji",
       "f5", priority="medium", estimate=1,
       labels=("demo", "qa"),
       description="Ubah 5 skenario demo slide (upload SOP, tanya cuti, flowchart "
                   "pengajuan, bar chart tabel cuti, pertanyaan di luar dokumen) "
                   "jadi checklist QA yang bisa dijalankan ulang.",
       acceptance=("Setiap skenario punya langkah + hasil yang diharapkan",
                   "Bisa dijalankan offline (--demo / provider mock)",
                   "Hasil tercatat di task ini sebagai komentar"),
       source=_SUCCESS),

    _t("ASK-053", "Dokumentasi: README, panduan developer, docs task management",
       "f5", priority="medium", estimate=2,
       labels=("docs",),
       description="Perbarui README + panduan developer untuk fitur RAG, artifact, "
                   "governance, dan halaman task management (termasuk konvensi "
                   "nama branch ASK-NNN).",
       acceptance=("Cara pakai + env baru terdokumentasi",
                   "Konvensi branch ↔ task id dijelaskan",
                   "Troubleshooting backend gagal start diperbarui"),
       evidence=("README.md", "docs/PANDUAN-DEVELOPER.md", "docs/TEKNIS.md"),
       source=_SUCCESS),

    _t("ASK-054", "OCR PDF scan (pytesseract) — bonus",
       "f5", priority="low", estimate=3,
       labels=("nice-to-have", "parser"),
       description="Dokumen hasil scan (tanpa text layer) diproses OCR bila "
                   "pytesseract tersedia, dengan peringatan bahwa akurasi "
                   "bergantung kualitas scan.",
       acceptance=("PDF tanpa text layer terdeteksi otomatis",
                   "Tanpa pytesseract → pesan jelas, tidak crash",
                   "Halaman hasil OCR ditandai di metadata chunk"),
       depends_on=("ASK-016",), source=_SUCCESS),
]


def summary() -> dict[str, Any]:
    """Ringkasan rencana (dipakai test & endpoint /api/tasks/plan)."""
    per_phase: dict[str, int] = {p["id"]: 0 for p in PHASES}
    per_priority: dict[str, int] = {p: 0 for p in PRIORITIES}
    hours = 0.0
    for t in TASKS:
        per_phase[t["phase"]] = per_phase.get(t["phase"], 0) + 1
        per_priority[t["priority"]] = per_priority.get(t["priority"], 0) + 1
        hours += float(t["estimate"] or 0)
    return {
        "phases": PHASES,
        "total": len(TASKS),
        "per_phase": per_phase,
        "per_priority": per_priority,
        "estimate_days": round(hours, 1),
    }
