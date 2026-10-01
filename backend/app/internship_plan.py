"""Rencana proyek internship — **Internal AI Assistant & RAG Agent (prototipe)**.

Papan ini terpisah dari rencana platform (`tasks_plan.py`, id `ASK-NNN`): id di
sini memakai prefix `INT-NNN` dan halaman-nya `/internship`.

Sumber kebenaran
----------------
Rencana ini mengikuti dokumen yang disepakati di repo prototipe
(`ai-assistant-prototype`) dan disalin ke `docs/internship/`:

* ``01-template-prd.md``     — PRD terbaru (bagian A masalah/persona/user story,
  B metrik & anggaran token, C arsitektur + 5 ADR, D rencana rilis),
* ``02-arsitektur-prototipe.md`` — ringkasan stack & alur 7 tahap,
* ``05-design-system.md``    — design system **beUI** (Light mode default,
  lucide-react, tanpa emoji, Clean Architecture di frontend).

Sasaran papan
-------------
Satu **prototipe asisten AI internal** yang menjawab pertanyaan dari dokumen
perusahaan (PDF, DOCX, Markdown) dengan sitasi, punya ingatan percakapan,
membuat visual interaktif (flowchart, korelasi antardokumen, bar chart), dan
tercatat token serta biayanya. Dipetakan ke lima epic: manajemen konteks &
memori, orkestrasi & tooling, guardrail, observability, dan performa.

Batasan arsitektur (terkunci di PRD bagian C, intern tidak perlu memilih)
-------------------------------------------------------------------------
* **Monorepo decoupled + Clean Architecture** (ADR-01): frontend **Next.js 14+**
  (App Router, TypeScript, Tailwind) dan backend **FastAPI** async, keduanya
  berlapis domain / application / infrastructure / presentation.
* **PostgreSQL on-premise** sebagai satu-satunya database (ADR-02) dengan
  ekstensi **pgvector** + indeks **HNSW** untuk vektor (ADR-03).
* **Tracing sendiri** ke tabel `traces` (ADR-04), bukan SaaS eksternal.
* **ILLMProvider** dengan provider nyata (OpenAI-compatible / vLLM /
  HuggingFace) **dan Mock Provider wajib** (ADR-05).
* **UI = beUI** (registri `@beui` via shadcn): ikon hanya `lucide-react`, motion
  `motion/react`, tema terang default, **tanpa emoji**.
* Non-goals (PRD A.4): tanpa suara, tanpa multi-tenant, tanpa fine-tuning,
  tanpa aplikasi mobile native, tanpa eksekusi shell/OS bebas, tanpa
  kolaborasi edit dokumen real-time.

Urutan kerja
------------
Papan dibagi menjadi **6 sprint** (satu sprint ≈ 1 minggu kerja). Sprint 0
(PRD & kerangka) sudah selesai: INT-001–004 dipertahankan apa adanya dan
INT-005 (boilerplate monorepo) sudah di-merge ke `develop`. Sprint berikutnya
duduk di `backlog` dan baru ditarik saat sprintnya dibuka — supaya kolom To do
tidak memanjang.

Tiap task ditulis agar bisa dikerjakan tanpa bertanya lagi:

  * ``description`` — konteks + keputusan teknis yang sudah ditetapkan,
  * ``workflow``    — alur kerja bernomor ``{actor, action, result}``,
  * ``wireframe``   — sketsa layout / bentuk data (ASCII),
  * ``acceptance``  — kriteria selesai yang **berangka** dan bisa diuji,
  * ``evidence``    — berkas yang harus ada (diperiksa ``POST /api/tasks/sync``),
  * ``depends_on``  — prasyarat, supaya urutan pengerjaan jelas.

Konvensi id dipakai apa adanya di nama branch git (``feat/INT-008-…``).

Papan ini **bisa disunting** dari UI (tambah, ubah, hapus). Task rencana yang
sudah disunting atau dihapus tidak ditimpa/dihidupkan lagi oleh pembaruan
rencana — lihat `tasks.refresh_plan_if_stale`.
"""
from __future__ import annotations

from typing import Any

from .tasks_plan import PRIORITIES, STATUSES, STATUS_LABELS  # noqa: F401  (re-export)

#: Penanda papan (dipakai filter `/api/tasks?track=internship`).
TRACK = "internship"

#: Versi rencana. Naikkan setiap kali daftar TASKS berubah supaya papan yang
#: sudah ter-seed di deployment lama ikut diperbarui (`tasks.refresh_plan_if_stale`)
#: tanpa menghapus progres atau suntingan tangan.
PLAN_REVISION = "2026-10-01-prd-nextjs-fastapi-3"

#: Repo yang dibangun intern (monorepo terpisah dari ask-anything).
PROJECT_DIR = "ai-assistant-prototype"

#: Awalan path bukti pada task Sprint 0 lama (INT-001–004), dibiarkan apa adanya.
LEGACY_P = "projects/ai-agent"

#: Sprint = kolom "fase" di papan. Id `i0..i5` dipertahankan (dipakai data lama
#: & nama branch), namanya yang berbicara sebagai sprint.
PHASES: list[dict[str, str]] = [
    {"id": "i0", "name": "Sprint 0 — PRD & Kerangka",
     "subtitle": "Gerbang: PRD disetujui. PRD A–C + boilerplate monorepo Next.js & FastAPI."},
    {"id": "i1", "name": "Sprint 1 — Chat, Sesi & Token",
     "subtitle": "Epic 1: chat streaming, auth & peran, sesi di PostgreSQL, token, memori multi-turn."},
    {"id": "i2", "name": "Sprint 2 — RAG, Tool & Router",
     "subtitle": "Epic 2: ingestion PDF/DOCX/MD, pgvector, sitasi, router, tool, GraphView & chart."},
    {"id": "i3", "name": "Sprint 3 — Guardrail",
     "subtitle": "Epic 3: guardrail input, redaksi PII, validator output, uji red-team."},
    {"id": "i4", "name": "Sprint 4 — Observability",
     "subtitle": "Epic 4: tracing, token & biaya, feedback, evaluasi 20 soal."},
    {"id": "i5", "name": "Sprint 5 — Performa & Rilis",
     "subtitle": "Epic 5: semantic cache, kuota, fallback provider, deploy persisten & demo."},
]

PHASE_IDS = tuple(p["id"] for p in PHASES)

#: Label sprint (dipakai filter label di UI, sejajar dengan `phase`).
SPRINT_LABELS: dict[str, str] = {
    "i0": "sprint-0", "i1": "sprint-1", "i2": "sprint-2",
    "i3": "sprint-3", "i4": "sprint-4", "i5": "sprint-5",
}

#: Label epic — persis lima epic yang diminta pembimbing (+ epic produk/PRD).
EPICS: list[dict[str, str]] = [
    {"label": "epic-konteks", "name": "Epic 1 — Manajemen Konteks & Memori"},
    {"label": "epic-tooling", "name": "Epic 2 — Orkestrasi & Tooling"},
    {"label": "epic-guardrail", "name": "Epic 3 — Keamanan & Guardrails"},
    {"label": "epic-observability", "name": "Epic 4 — Observability & LLMOps"},
    {"label": "epic-performa", "name": "Epic 5 — Skalabilitas & Performa"},
    {"label": "epic-prd", "name": "Epic 0 — Produk & PRD"},
]

#: Rujukan dokumen pendamping (dibaca halaman /internship dari `docs/internship`).
_DOC = "docs/internship"
_KERJA = f"{_DOC}/00-panduan-kerja.md"
_PRD = f"{_DOC}/01-template-prd.md"
_ARCH = f"{_DOC}/02-arsitektur-prototipe.md"
_SPRINT = f"{_DOC}/03-rencana-sprint.md"
_DOD = f"{_DOC}/04-definition-of-done.md"
_DS = f"{_DOC}/05-design-system.md"

#: Berkas referensi di **ask-anything** yang boleh dibaca sebagai contoh pola
#: (bukan untuk disalin: prototipe ditulis sendiri dengan Clean Architecture).
REF = {
    "agent": "ask-anything: backend/app/agent/loop.py",
    "tools": "ask-anything: backend/app/tools/__init__.py",
    "rag": "ask-anything: backend/app/rag.py",
    "memory": "ask-anything: backend/app/memory.py",
    "quota": "ask-anything: backend/app/quota.py",
    "feedback": "ask-anything: backend/app/feedback.py",
    "db": "ask-anything: backend/app/db.py",
}


def _w(actor: str, action: str, result: str = "") -> dict[str, str]:
    """Satu langkah workflow: siapa (actor) melakukan apa, hasilnya apa."""
    return {"actor": actor, "action": action, "result": result}


def _t(task_id: str, title: str, phase: str, *, priority: str = "medium",
       estimate: float = 1.0, labels: tuple[str, ...] = (),
       description: str = "", workflow: tuple[dict[str, str], ...] = (),
       wireframe: str = "", acceptance: tuple[str, ...] = (),
       evidence: tuple[str, ...] = (), depends_on: tuple[str, ...] = (),
       source: str = "", status: str = "", assignee: str = "",
       branch: str = "") -> dict[str, Any]:
    """Buat satu task.

    `status` kosong → otomatis: Sprint 0 = `todo`, sprint lain = `backlog`
    (belum dibuka). Task `done` dibuat dengan seluruh kriteria sudah tercentang.
    Label sprint ikut ditambahkan.
    """
    sprint_label = SPRINT_LABELS.get(phase, "")
    all_labels = list(labels)
    if sprint_label and sprint_label not in all_labels:
        all_labels.append(sprint_label)
    status = status or ("todo" if phase == "i0" else "backlog")
    task: dict[str, Any] = {
        "id": task_id, "title": title, "phase": phase, "priority": priority,
        "estimate": estimate, "labels": all_labels,
        "description": description.strip(),
        "workflow": [dict(step) for step in workflow],
        "wireframe": wireframe.strip("\n"),
        "acceptance": ([{"text": a, "done": True} for a in acceptance]
                       if status == "done" else list(acceptance)),
        "evidence": list(evidence), "depends_on": list(depends_on),
        "source": source,
        "status": status,
        "assignee": assignee,
    }
    if branch:
        task["branch"] = branch
    return task


def acceptance_text(task: dict[str, Any]) -> list[str]:
    """Teks kriteria selesai satu task rencana (apa pun bentuk simpannya)."""
    return [a["text"] if isinstance(a, dict) else str(a)
            for a in task.get("acceptance", [])]


_L = ("internship",)
B = (*_L, "backend")
F = (*_L, "ui")

#: Akun intern yang mengerjakan papan ini (username login).
INTERNS: tuple[str, ...] = ("verisimb",)

P = PROJECT_DIR
#: Jalan pintas path bukti di dalam monorepo prototipe (struktur final = PRD C.3).
BE = f"{P}/backend/app"
FE = f"{P}/frontend"
TESTS = f"{P}/backend/tests"

TASKS: list[dict[str, Any]] = [
    # ================================================================ Sprint 0
    _t("INT-001", "PRD bagian A: masalah, persona, user story, non-goals",
       "i0", status="done", priority="critical", estimate=1.5,
       labels=(*_L, "epic-prd", "docs"),
       description=(
           "Gerbang pertama internship: sebelum kode fitur ditulis, kunci APA "
           "yang dibangun. Produk = chatbot LLM internal yang menjawab "
           "pertanyaan berdasarkan dokumen perusahaan, punya ingatan "
           "percakapan, bisa memanggil tool, dan tercatat biayanya. Tulis "
           "bagian A dari PRD memakai template `docs/internship/01-template-prd.md`: "
           "1 paragraf pernyataan masalah, 3 persona (karyawan biasa, power "
           "user, admin) lengkap tujuan & titik nyeri, 10 user story berformat "
           "'Sebagai <persona> saya ingin <aksi> supaya <manfaat>' yang tiap "
           "storinya bisa diuji, dan daftar NON-goal eksplisit (tanpa suara, "
           "tanpa multi-tenant, tanpa fine-tuning, tanpa mobile app) supaya "
           "ruang lingkup tidak melar sampai akhir magang."),
       workflow=(
           _w("Intern", "Kumpulkan kebutuhan dari pembimbing + baca lima epic acuan",
              "Catatan kebutuhan mentah di dokumen kerja"),
           _w("Intern", "Rumuskan masalah, 3 persona, 10 user story, non-goals",
              "Draf PRD bagian A"),
           _w("Pembimbing", "Review draf, tandai story yang ambigu / di luar scope",
              "Komentar revisi di merge request"),
           _w("Intern", "Revisi sampai tiap story punya kriteria uji",
              "PRD bagian A siap digabung dengan bagian B & C"),
       ),
       wireframe="""
PRD — BAGIAN A
+-------------------------------------------------------------+
| A1. Pernyataan masalah            (<= 1 paragraf)            |
| A2. Persona                                                   |
|     +-------------+-------------+-------------+              |
|     | Karyawan    | Power user  | Admin       |              |
|     | tujuan      | tujuan      | tujuan      |              |
|     | titik nyeri | titik nyeri | titik nyeri |              |
|     +-------------+-------------+-------------+              |
| A3. User story (10)                                           |
|     US-01  Sebagai ... ingin ... supaya ...  | uji: ...      |
| A4. NON-GOALS (daftar tegas)                                  |
+-------------------------------------------------------------+
""",
       acceptance=(
           "Pernyataan masalah maksimal 1 paragraf dan menyebut pengguna nyata",
           "3 persona lengkap (tujuan + titik nyeri), bukan hanya nama",
           "Tepat 10 user story berformat baku, tiap story punya 1 baris cara uji",
           "Minimal 5 non-goal ditulis eksplisit",
           "Pembimbing menandai PRD bagian A 'approved' di merge request"),
       evidence=(f"{_DOC}/01-template-prd.md", f"{LEGACY_P}/docs/PRD.md"),
       source=_PRD),

    _t("INT-002", "PRD bagian B: metrik sukses, anggaran token & biaya",
       "i0", status="done", priority="critical", estimate=1,
       labels=(*_L, "epic-prd", "docs"),
       description=(
           "Bagian B mengubah 'bagus' menjadi angka. Tetapkan target yang akan "
           "diukur pada demo akhir: jawaban tergrounding (punya sitasi) >= 80% "
           "dari 20 pertanyaan uji, p95 Time To First Token <= 3 detik pada "
           "provider mock dan <= 6 detik pada provider nyata, rasio 👍 >= 70%, "
           "biaya rata-rata <= Rp500 per percakapan, dan cache hit-rate >= 20% "
           "pada pertanyaan berulang. Tulis juga anggaran token: batas context "
           "window yang dipakai (8k), maksimum token jawaban (1024), kuota "
           "harian per pengguna (50 pesan / 100k token), dan cara menghitung "
           "biaya per 1k token dari harga provider."),
       workflow=(
           _w("Intern", "Kumpulkan harga provider + ukur baseline latensi mock",
              "Tabel harga & latensi awal"),
           _w("Intern", "Tetapkan 5 metrik target + anggaran token/kuota",
              "PRD bagian B"),
           _w("Pembimbing", "Uji kewajaran angka (tidak terlalu longgar/ketat)",
              "Angka final disepakati"),
           _w("Intern", "Tulis cara mengukur tiap metrik (alat & rumusnya)",
              "Metrik bisa diverifikasi ulang siapa pun"),
       ),
       wireframe="""
PRD — BAGIAN B (semua BERANGKA)
+---------------------------+-----------+---------------------+
| Metrik                    | Target    | Cara ukur           |
+---------------------------+-----------+---------------------+
| Jawaban tergrounding      | >= 80%    | set eval 20 soal    |
| p95 TTFT (mock / nyata)   | <=3s/<=6s | tabel traces        |
| Rasio 👍                   | >= 70%    | tabel feedback      |
| Biaya per percakapan      | <= Rp500  | token x harga/1k    |
| Cache hit-rate            | >= 20%    | tabel cache         |
+---------------------------+-----------+---------------------+
ANGGARAN: context 8k | jawaban 1024 tok | kuota 50 pesan/hari
""",
       acceptance=(
           "5 metrik punya angka target DAN cara ukur yang menyebut sumber data",
           "Anggaran token & kuota harian tertulis sebagai angka",
           "Rumus biaya per 1k token ditulis dengan contoh perhitungan",
           "Tidak ada kata sifat tanpa angka ('cepat', 'akurat') di bagian ini"),
       evidence=(f"{LEGACY_P}/docs/PRD.md",), depends_on=("INT-001",), source=_PRD),

    _t("INT-003", "PRD bagian C: arsitektur prototipe + 5 ADR singkat",
       "i0", status="done", priority="critical", estimate=1,
       labels=(*_L, "epic-prd", "docs", "arsitektur"),
       description=(
           "Gambar alur data satu jawaban dari awal sampai akhir (UI → "
           "guardrail input → router → retrieval/tool → LLM → validator output "
           "→ trace + biaya → UI) dan tulis 5 ADR satu paragraf: (1) Streamlit "
           "sebagai UI prototipe, (2) SQLite satu berkas sebagai satu-satunya "
           "database, (3) embedding lokal + numpy cosine sebagai pengganti "
           "vector DB, (4) tracing sendiri ke tabel `traces` alih-alih SaaS, "
           "(5) mock provider wajib agar demo jalan tanpa kuota API. Tiap ADR "
           "memuat konteks, keputusan, dan konsekuensi — termasuk kapan "
           "keputusan itu perlu ditinjau ulang bila produk naik ke produksi."),
       workflow=(
           _w("Intern", "Gambar diagram alur satu request (ASCII/draw.io)",
              "Diagram di PRD bagian C"),
           _w("Intern", "Tulis 5 ADR: konteks, keputusan, konsekuensi",
              "Daftar ADR"),
           _w("Pembimbing", "Review: pastikan tidak ada komponen berlebih",
              "Stack final dikunci"),
           _w("Intern", "Kunci struktur folder projects/ai-agent",
              "Peta modul yang akan diisi sprint berikutnya"),
       ),
       wireframe="""
ALUR SATU JAWABAN
 UI(Streamlit) -> guardrail_input -> router -> [retrieval | tool | langsung]
     -> context_builder(token budget) -> LLM(provider) -> validator_output
     -> trace + biaya -> UI(jawaban + sitasi + tombol 👍/👎)

FOLDER
 projects/ai-agent/
   app.py            Streamlit (chat, riwayat, dasbor, trace)
   core/  llm.py providers.py session.py tokens.py memory.py
          rag.py tools.py router.py guardrail.py tracing.py
          cache.py quota.py
   data/  agent.db  index.npy  docs/
   tests/ test_*.py
""",
       acceptance=(
           "Diagram alur memuat 7 tahap dan bisa dibaca tanpa penjelasan lisan",
           "5 ADR ditulis dengan konteks/keputusan/konsekuensi",
           "Struktur folder final tertulis dan sama dengan repo nantinya",
           "Tidak ada komponen di luar stack terkunci pada dokumen 02 (cek satu per satu)"),
       evidence=(f"{LEGACY_P}/docs/PRD.md", f"{LEGACY_P}/docs/ADR.md"),
       depends_on=("INT-002",), source=_ARCH),

    _t("INT-004", "Kerangka proyek: repo, Streamlit 'hello chat', mock provider",
       "i0", status="done", priority="high", estimate=1.5, labels=(*B, "epic-prd"),
       description=(
           "Buat kerangka `projects/ai-agent` yang bisa dijalankan orang lain "
           "dalam < 5 menit: `requirements.txt` (streamlit, openai, tiktoken, "
           "numpy, pydantic, pytest), `README.md` berisi cara jalan, `app.py` "
           "Streamlit dengan kolom chat yang memantulkan jawaban dari **mock "
           "provider** (echo + delay kecil), `core/config.py` membaca env "
           "(AGENT_PROVIDER, AGENT_BASE_URL, AGENT_API_KEY, AGENT_MODEL, "
           "AGENT_DB_PATH), dan `core/db.py` yang membuat SQLite di "
           "`AGENT_DB_PATH` (default `data/agent.db`). Satu test smoke "
           "memastikan aplikasi bisa diimpor dan DB terbentuk."),
       workflow=(
           _w("Intern", "Inisialisasi folder + requirements + README",
              "Proyek bisa di-`pip install -r`"),
           _w("Intern", "Tulis app.py Streamlit minimal + mock provider",
              "`streamlit run app.py` menampilkan chat yang membalas"),
           _w("Intern", "Tulis core/db.py + test smoke",
              "`pytest` hijau, data/agent.db terbentuk"),
           _w("Pembimbing", "Jalankan dari nol mengikuti README",
              "Konfirmasi setup < 5 menit"),
       ),
       wireframe="""
+--------------------------------------------------------------+
| AI Agent (prototipe)                         [mock provider]  |
+--------------------------------------------------------------+
| riwayat:            |  Halo, saya asisten internal.           |
|  (kosong)           |  > pertanyaan pengguna                  |
|                     |  Jawaban echo dari mock...              |
+---------------------+----------------------------------------+
| [ ketik pertanyaan .......................... ] [ Kirim ]     |
+--------------------------------------------------------------+
""",
       acceptance=(
           "`pip install -r requirements.txt` lalu `streamlit run app.py` jalan di mesin bersih",
           "Chat membalas lewat mock provider tanpa API key sama sekali",
           "`AGENT_DB_PATH` dihormati; default membuat data/agent.db otomatis",
           "`pytest` berjalan dan minimal 1 test smoke hijau",
           "README memuat langkah setup, env, dan cara menjalankan test"),
       evidence=(f"{LEGACY_P}/README.md", f"{LEGACY_P}/requirements.txt", f"{LEGACY_P}/app.py",
                 f"{LEGACY_P}/core/db.py", f"{LEGACY_P}/tests/test_smoke.py"),
       depends_on=("INT-003",), source=_ARCH),

    _t("INT-005", "Repo boilerplate: monorepo Clean Architecture, DB, LLM & beUI",
       "i0", status="done", priority="critical", estimate=2.5,
       labels=(*B, "epic-prd", "arsitektur"),
       branch="feat/INT-005-repo-boilerplate",
       description=(
           "Sudah di-merge ke `develop`. Fondasi monorepo sesuai PRD bagian C "
           "(ADR-01..05): `backend/` FastAPI async berlapis domain / application / "
           "infrastructure / presentation, `frontend/` Next.js (App Router) dengan "
           "lapisan entities / application / interface-adapters / infrastructure, "
           "dan design system beUI native (komponen agents dari registri `@beui`, "
           "`lucide-react`, tema terang default). Backend sudah punya envelope "
           "respons standar `ApiResponse {success, data, error, meta}`, koneksi "
           "PostgreSQL async (SQLAlchemy + asyncpg, pool dari env), endpoint "
           "`/health` yang memeriksa database dan provider, empat provider LLM di "
           "belakang satu antarmuka `ILLMProvider` (mock, openai, vllm, "
           "huggingface), endpoint SSE `/api/v1/chat/stream`, dan endpoint sesi "
           "awal (repository masih in-memory — diganti di INT-008). Peluncuran: "
           "`python run.py` untuk lokal, `docker-compose.yml` 3 service "
           "(frontend, backend, postgres) dan `Dockerfile` tunggal untuk Coolify."),
       workflow=(
           _w("Intern", "Susun struktur monorepo 4 layer di backend dan frontend",
              "Folder domain/application/infrastructure/presentation terisi"),
           _w("Intern", "Bangun envelope respons, exception handler, koneksi PostgreSQL, dan 4 provider LLM",
              "Backend lulus test koneksi, provider, envelope, dan smoke"),
           _w("Intern", "Adopsi beUI native: komponen agents, tema terang, lucide-react",
              "Halaman chat awal memakai komponen beUI"),
           _w("Intern", "Tulis launcher run.py + Docker/Coolify + README",
              "Aplikasi jalan dengan satu perintah dan bisa dideploy"),
           _w("Pembimbing", "Review merge request dan merge ke develop",
              "INT-005 selesai"),
       ),
       wireframe="""
ai-assistant-prototype/
  backend/app/
    domain/          entities, errors
    application/     interfaces (ILLMProvider, ISessionRepository), use_cases/chat_stream.py
    infrastructure/  config, db/{models,repositories,session}, llm/{factory,mock,openai,vllm,huggingface}
    presentation/    api/v1/{routes,schemas}, exception_handlers
  frontend/
    src/             entities, application, interface-adapters, infrastructure(sseChatClient)
    src/components/  agents/* (beUI), motion/*, ui/*
    app/             layout.tsx, page.tsx (chat)
  docker-compose.yml  Dockerfile  run.py  .env.example

GET  /health               -> {database, llm}
POST /api/v1/chat/stream   -> SSE: data: {"token": "..."} ... data: [DONE]
""",
       acceptance=(
           "Struktur monorepo mengikuti 4 layer Clean Architecture di backend dan frontend",
           "`python run.py` menjalankan FastAPI (port 8000) dan Next.js (port 3000) dengan satu perintah",
           "Seluruh endpoint REST memakai envelope ApiResponse dan /health memeriksa database serta LLM",
           "4 provider LLM (mock, openai, vllm, huggingface) dipilih lewat env LLM_PROVIDER tanpa ubah kode",
           "Koneksi PostgreSQL async dengan pool yang dikonfigurasi lewat env (DB_POOL_SIZE, DB_MAX_OVERFLOW)",
           "Frontend memakai beUI native, lucide-react, dan tema terang default sesuai design system",
           "Deploy lewat docker-compose 3 service dan Dockerfile tunggal untuk Coolify terdokumentasi di README",
           "pytest backend/tests hijau (koneksi DB, provider LLM, envelope, smoke)"),
       evidence=(f"{P}/README.md", f"{P}/run.py", f"{P}/docker-compose.yml",
                 f"{BE}/main.py", f"{BE}/infrastructure/llm/factory.py",
                 f"{FE}/app/page.tsx"),
       depends_on=("INT-004",), source=_PRD),

    # ================================================================ Sprint 1
    _t("INT-006", "Protokol SSE v1 + UI chat streaming (beUI)",
       "i1", priority="critical", estimate=1.5, labels=(*F, "epic-konteks"),
       description=(
           "Matangkan jalur chat boilerplate menjadi pengalaman yang layak "
           "demo. Backend: kunci kontrak SSE `/api/v1/chat/stream` dengan event "
           "bertipe `status` (tahap pipeline: guardrail, router, retrieval, "
           "generasi), `token`, `citation`, `usage` (prompt/completion token), "
           "`error` (kode terstandar) dan penutup `[DONE]` — dokumentasikan "
           "skemanya di `schemas.py`. Frontend (Clean Architecture): "
           "`sseChatClient` (infrastructure) mem-parse event, `chatController` "
           "(interface-adapters) mengelola state stream, `ChatContainer` hanya "
           "presentasi. Komponen resmi beUI lewat `npx shadcn add @beui/<slug>`: "
           "`prompt-input`, `message-scroller`, `streaming-response`, `message`, "
           "`message-bubble`, `loading-states` (ThinkingShimmer) dan "
           "`agent-activity` untuk status tahap. Tombol Stop memakai "
           "AbortController; error provider tampil sebagai pesan ramah dengan "
           "tombol coba lagi, bukan traceback. Empty state memuat 3 pertanyaan "
           "contoh. Ikon hanya lucide-react, tanpa emoji, tema terang default."),
       workflow=(
           _w("Intern", "Definisikan skema 6 tipe event SSE di backend + test kontrak",
              "Kontrak SSE v1 terdokumentasi dan teruji"),
           _w("Intern", "Perluas sseChatClient dan chatController untuk event bertipe + AbortController",
              "State stream stabil, Stop bekerja"),
           _w("Intern", "Bangun ChatContainer dari komponen beUI sesuai design-system.md",
              "Chat dua arah dengan status tahap"),
           _w("Pembimbing", "Uji 5 skenario: normal, Stop, provider mati, input panjang, koneksi putus",
              "Semua skenario tertangani tanpa traceback"),
       ),
       wireframe="""
SSE v1 (satu event per baris 'data:')
  {"type":"status","stage":"retrieval","label":"Mencari dokumen"}
  {"type":"token","text":"Cuti tahunan "}
  {"type":"citation","n":1,"document":"sop-cuti.pdf","page":3}
  {"type":"usage","prompt_tokens":1200,"completion_tokens":300,"ttft_ms":640}
  {"type":"error","code":"LLM_PROVIDER_ERROR","message":"..."}
  [DONE]

+---------------------------------------------------------------+
| AI Assistant                                  [lucide: Sun]   |
+---------------------------------------------------------------+
|  user  : Berapa hari jatah cuti tahunan?                       |
|  agent : (ThinkingShimmer) Mencari dokumen ...                 |
|          Cuti tahunan 12 hari [1]                [ Stop ]      |
+---------------------------------------------------------------+
| empty state: [Cuti tahunan?] [Alur reimburse?] [Jam kerja?]    |
| [ prompt-input ....................................... ] [>]  |
+---------------------------------------------------------------+
""",
       acceptance=(
           "Jawaban mock tiba bertahap: >= 5 event token diterima sebelum [DONE]",
           "Tombol Stop menghentikan stream dalam <= 1 detik dan menutup koneksi SSE",
           "Provider error menampilkan pesan ramah + tombol coba lagi, tanpa stack trace di layar maupun respons",
           "Test kontrak SSE hijau untuk 6 tipe event (status, token, citation, usage, error, done)",
           "Empty state memuat 3 pertanyaan contoh yang bisa diklik",
           "Tidak ada emoji dan tidak ada ikon di luar lucide-react (dicek lewat grep di src/ dan app/)"),
       evidence=(f"{TESTS}/test_sse_contract.py",
                 f"{FE}/src/interface-adapters/presenters/chatPresenter.ts",
                 f"{FE}/src/components/ChatContainer.tsx"),
       depends_on=("INT-005",), source=_DS),

    _t("INT-007", "Autentikasi sesi + peran (karyawan, power user, admin)",
       "i1", priority="critical", estimate=1, labels=(*B, "epic-guardrail"),
       description=(
           "Tahap 2 pipeline PRD meminta otentikasi sesi pengguna sebelum "
           "request masuk ke domain. Bangun autentikasi on-premise sederhana "
           "tanpa layanan eksternal: tabel `users(id, username, password_hash, "
           "role, created_at)` di PostgreSQL, hash password argon2/bcrypt, "
           "login menghasilkan JWT berumur 8 jam di cookie httpOnly, dependency "
           "FastAPI `current_user` dan `require_role(...)`. Tiga peran memetakan "
           "persona PRD: `employee` (tanya jawab dan sitasi), `power_user` "
           "(+ unggah dokumen, filter dokumen, visualisasi), `admin` (+ hapus "
           "dokumen, lihat biaya dan trace). Frontend: halaman `/login` (beUI), "
           "guard di middleware App Router, menu yang menyesuaikan peran. "
           "Single organization — tanpa multi-tenant (non-goal #2) dan tanpa "
           "registrasi publik; akun awal dibuat lewat skrip seed."),
       workflow=(
           _w("Intern", "Buat tabel users + hashing password + skrip seed 3 akun",
              "Akun awal per peran tersedia"),
           _w("Intern", "Implementasi login/logout + JWT cookie httpOnly + dependency require_role",
              "Endpoint terlindungi"),
           _w("Intern", "Bangun halaman /login dan guard middleware Next.js",
              "Alur masuk-keluar jalan"),
           _w("Intern", "Uji matriks 3 peran x 6 aksi",
              "Aksi terlarang selalu 403"),
       ),
       wireframe="""
users(id, username, password_hash, role[employee|power_user|admin], created_at)

MATRIKS AKSI
                 employee  power_user  admin
 chat + sitasi      ya        ya         ya
 unggah dokumen     -         ya         ya
 filter dokumen     -         ya         ya
 hapus dokumen      -         -          ya
 lihat biaya        -         -          ya
 lihat trace        -         -          ya

POST /api/v1/auth/login -> Set-Cookie: session=<jwt>; HttpOnly; SameSite=Lax
""",
       acceptance=(
           "Semua rute selain /health dan /auth/login mengembalikan 401 tanpa token (diuji otomatis)",
           "Matriks 3 peran x 6 aksi ditegakkan dan diuji; aksi terlarang menghasilkan 403",
           "Password tersimpan sebagai hash (tidak ada kolom plaintext); 5 login gagal beruntun mengunci akun 15 menit",
           "Token kedaluwarsa setelah 8 jam dan logout menghapus cookie",
           "Skrip seed membuat 3 akun contoh (satu per peran) dan tidak ada registrasi publik"),
       evidence=(f"{BE}/application/use_cases/authenticate.py",
                 f"{BE}/presentation/middlewares/auth.py",
                 f"{TESTS}/test_auth.py", f"{FE}/app/login/page.tsx"),
       depends_on=("INT-005",), source=_PRD),

    _t("INT-008", "Sesi percakapan persisten di PostgreSQL + sidebar",
       "i1", priority="critical", estimate=1.5, labels=(*B, *F, "epic-konteks"),
       description=(
           "Ganti `InMemorySessionRepository` (hilang tiap restart) dengan "
           "repository SQLAlchemy async ke PostgreSQL. Tabel `chat_sessions` "
           "(tambah `user_id`, `summary`) dan `chat_messages` sudah ada di "
           "`models.py`; tambahkan migrasi **Alembic** (bukan `create_all`) agar "
           "skema berversi. Endpoint: `GET/POST /api/v1/sessions`, "
           "`PATCH /api/v1/sessions/{id}` (ganti nama), `DELETE "
           "/api/v1/sessions/{id}` (cascade pesan), seluruhnya dibatasi ke "
           "pemilik sesi. Judul otomatis dari 6 kata pertama pertanyaan. "
           "Sidebar memakai beUI `ai-sidebar` (ganti nama inline, hapus dengan "
           "konfirmasi). Membuka sesi lama memuat ulang seluruh riwayat sehingga "
           "percakapan bisa dilanjutkan setelah restart (dasar US-04). Karena "
           "state tidak lagi in-memory, worker uvicorn boleh lebih dari 1."),
       workflow=(
           _w("Intern", "Tambah migrasi Alembic untuk kolom user_id dan summary",
              "Skema berversi"),
           _w("Intern", "Implementasi SqlSessionRepository + endpoint CRUD berpemilik",
              "Sesi tersimpan di PostgreSQL"),
           _w("Intern", "Sambungkan ai-sidebar ke API lewat sessionController",
              "Buat, buka, ganti nama, hapus dari UI"),
           _w("Intern", "Uji restart backend dan isolasi antar pengguna",
              "Persistensi dan privasi terbukti"),
       ),
       wireframe="""
chat_sessions(id, user_id, title, summary, created_at, updated_at)
chat_messages(id, session_id FK CASCADE, role, content, tokens, provider, model, created_at)

SIDEBAR (beUI ai-sidebar)
  [+ Percakapan baru]
  > Kebijakan cuti tahunan        [pencil] [trash]
  > Alur klaim reimburse          [pencil] [trash]
""",
       acceptance=(
           "Restart backend: seluruh sesi dan pesan tetap ada (test membuat ulang aplikasi)",
           "Judul otomatis maksimal 6 kata dari pertanyaan pertama",
           "Pengguna A tidak bisa membaca, mengubah, atau menghapus sesi pengguna B (403/404 diuji)",
           "Hapus sesi ikut menghapus pesannya (0 baris yatim di chat_messages)",
           "Alembic upgrade head dan downgrade -1 berjalan bersih di database kosong",
           "Minimal 8 test repository dan API hijau"),
       evidence=(f"{BE}/infrastructure/db/repositories/session_repository.py",
                 f"{P}/backend/alembic.ini", f"{TESTS}/test_sessions_api.py",
                 f"{FE}/src/interface-adapters/controllers/sessionController.ts"),
       depends_on=("INT-005", "INT-007"), source=_ARCH),

    _t("INT-009", "Hitung token + anggaran konteks 8k + indikator pemakaian",
       "i1", priority="high", estimate=1, labels=(*B, *F, "epic-konteks", "llm"),
       description=(
           "`TokenCounter` (interface di application, implementasi tiktoken "
           "`cl100k_base` di infrastructure, fallback `len(teks)/4` bila "
           "offline) menghitung token system prompt, riwayat, konteks RAG, dan "
           "draf pertanyaan. Anggaran dari PRD bagian B: context window 8.192 "
           "token dan jawaban maksimum 1.024 token (dikirim sebagai "
           "`max_tokens` ke provider). Endpoint `POST /api/v1/tokens/estimate` "
           "melayani indikator real-time di UI: bar `X / 8.192 token` dengan "
           "warna netral di bawah 70%, peringatan 70-90%, destructive di atas "
           "90% memakai token warna design system (`--muted`, `--accent`, "
           "`--destructive`). Kolom `tokens` tiap pesan terisi, dan tabel "
           "`token_usage_logs(id, session_id, message_id, prompt_tokens, "
           "completion_tokens, provider, model, created_at)` mencatat pemakaian "
           "per pemanggilan model — dasar US-09 dan perhitungan biaya di INT-024."),
       workflow=(
           _w("Intern", "Bungkus tiktoken + fallback di infrastructure/tokenizer",
              "TokenCounter siap pakai"),
           _w("Intern", "Hitung breakdown token per bagian prompt + endpoint estimate",
              "Angka tersedia untuk UI"),
           _w("Intern", "Tampilkan TokenMeter beUI di atas prompt-input",
              "Pengguna melihat sisa ruang konteks"),
           _w("Intern", "Catat token_usage_logs tiap pemanggilan model",
              "Data siap untuk dasbor biaya"),
       ),
       wireframe="""
count_tokens(text) -> int
breakdown(session) -> {system, history, context, draft, total, limit=8192, reserve=1024}

TokenMeter (di atas prompt-input)
  [======----]  3.120 / 8.192 token   sisa ~4.072   (warna: muted < 70% < accent < 90% < destructive)

token_usage_logs(id, session_id, message_id, prompt_tokens, completion_tokens, provider, model, created_at)
""",
       acceptance=(
           "Selisih hitungan terhadap usage provider <= 5% pada 10 contoh uji",
           "Fallback jalan tanpa internet (tiktoken gagal diunduh) tanpa crash",
           "Indikator berganti warna tepat pada ambang 70% dan 90%",
           "Kolom tokens terisi untuk 100% pesan tersimpan dan token_usage_logs punya 1 baris per pemanggilan model",
           "Parameter max_tokens=1024 terbukti dikirim ke provider (test menangkap payload)"),
       evidence=(f"{BE}/infrastructure/tokenizer/tiktoken_counter.py",
                 f"{TESTS}/test_token_counter.py",
                 f"{FE}/src/components/TokenMeter.tsx"),
       depends_on=("INT-008",), source=_PRD),

    _t("INT-010", "Memori multi-turn: sliding window + ringkasan otomatis",
       "i1", priority="critical", estimate=1.5, labels=(*B, "epic-konteks", "llm"),
       description=(
           "US-04: asisten mengingat riwayat dalam satu sesi. `BuildContextUseCase` "
           "menyusun prompt akhir dengan anggaran tetap: system prompt + "
           "ringkasan + N pesan terbaru + chunk dokumen <= 8.192 token, "
           "menyisakan 1.024 token untuk jawaban. Saat riwayat melewati 70% "
           "anggaran, pesan terlama dipangkas dan diringkas satu kali oleh LLM "
           "(maks 200 token) ke `chat_sessions.summary`; ringkasan lama digabung "
           "dengan yang baru, bukan ditumpuk. Pesan yang dipangkas tetap "
           "tersimpan di PostgreSQL dan tampil di UI, hanya tidak dikirim ke "
           "model. Skenario uji dari PRD: 'Siapa penanggung jawab persetujuan "
           "cuti?' lalu 'Berapa lama dia harus meresponnya?' — kata 'dia' harus "
           "terselesaikan. UI memberi penanda (ikon lucide, tanpa emoji) bahwa "
           "riwayat lama diringkas."),
       workflow=(
           _w("Intern", "Tulis algoritma anggaran token + pemilihan pesan di BuildContextUseCase",
              "Prompt tidak pernah melebihi anggaran"),
           _w("Intern", "Tambah peringkas otomatis saat ambang 70% tercapai",
              "sessions.summary terisi dan digabung"),
           _w("Intern", "Tandai di UI bahwa riwayat lama sudah diringkas",
              "Pengguna paham konteks dipangkas"),
           _w("Intern", "Uji percakapan 40 pesan dan skenario rujukan 'dia'",
              "Test panjang dan US-04 hijau"),
       ),
       wireframe="""
ANGGARAN 8.192 token
 [system ~300][ringkasan <=200][konteks RAG <=2.500][riwayat sisa][jawaban 1.024]

 riwayat > 70% ?  -> ambil pesan terlama -> LLM ringkas (<=200 tok)
                  -> gabung ke chat_sessions.summary -> keluarkan dari prompt
UI: [lucide: History] 12 pesan lama diringkas untuk menghemat konteks
""",
       acceptance=(
           "Percakapan 40 pesan tidak pernah mengirim prompt > 8.192 token",
           "Ringkasan terbentuk otomatis saat ambang 70% terlampaui dan panjangnya <= 200 token",
           "Ringkasan baru menggabungkan ringkasan lama (tetap 1 ringkasan per sesi)",
           "Pesan yang dipangkas tetap ada di database dan tetap tampil di UI",
           "Skenario US-04 ('dia' merujuk penanggung jawab cuti) lulus dengan mock deterministik",
           "UI menampilkan penanda riwayat diringkas"),
       evidence=(f"{BE}/application/use_cases/build_context.py",
                 f"{TESTS}/test_context_builder.py"),
       depends_on=("INT-009", "INT-008"), source=_PRD),

    # ================================================================ Sprint 2
    _t("INT-011", "Ingestion dokumen PDF, DOCX, dan Markdown + chunking",
       "i2", status="todo", priority="critical", estimate=1.5, labels=(*B, *F, "epic-tooling", "rag"),
       description=(
           "US-05 — power user mengunggah dokumen pedoman berformat PDF, DOCX, "
           "dan Markdown. `DocumentUploader` (drag-and-drop, beUI) mengirim "
           "multipart ke `POST /api/v1/documents` (maks 10 MB; hanya peran "
           "power_user dan admin). Parser berada di infrastructure/parsers: "
           "PyMuPDF (PDF, per halaman), python-docx (DOCX, paragraf dan tabel "
           "dipertahankan sebagai teks terstruktur), markdown-it-py (MD). "
           "`IngestDocumentUseCase` membuang header/footer berulang, memotong "
           "teks menjadi chunk ~500 token dengan overlap 50 token yang tidak "
           "memutus kalimat, dan menyimpan metadata `{document_id, nama_file, "
           "halaman, urutan}` ke `document_chunks`. Status pemrosesan "
           "(queued, parsing, chunking, embedding, ready, failed) tersimpan di "
           "`documents.status` dan di-polling UI tiap 2 detik; PDF hasil scan "
           "tanpa teks ditandai failed dengan pesan jelas. Pemrosesan berjalan "
           "di background task FastAPI supaya request upload kembali cepat."),
       workflow=(
           _w("Intern", "Bangun DocumentUploader + endpoint upload dengan validasi tipe dan ukuran",
              "Berkas masuk ke penyimpanan dokumen"),
           _w("Intern", "Implementasi 3 parser (PDF, DOCX, MD) di infrastructure/parsers",
              "Teks bersih per halaman/bagian"),
           _w("Intern", "Implementasi chunking 500/50 sadar kalimat + simpan metadata",
              "Tabel document_chunks terisi"),
           _w("Intern", "Tampilkan status dan error per dokumen di UI",
              "Pengguna tahu dokumen siap atau gagal"),
       ),
       wireframe="""
POST /api/v1/documents (multipart) -> 202 {id, status:"queued"}

documents(id, name, doc_type[pdf|docx|md], pages, status, file_path, uploaded_by, created_at)
document_chunks(id, document_id FK CASCADE, content, page_number, chunk_index)

+-------------------------------------------------------------+
| [ drag & drop PDF / DOCX / MD ]            maks 10 MB        |
+---------------------+-------+--------+----------------------+
| Dokumen             | Hal.  | Chunk  | Status               |
| sop-cuti.pdf        |  12   |   41   | ready                |
| kebijakan-hr.docx   |   8   |   27   | embedding            |
| scan-lama.pdf       |   5   |    0   | failed: tanpa teks   |
+---------------------+-------+--------+----------------------+
""",
       acceptance=(
           "3 format (PDF, DOCX, MD) berhasil diunggah dan tercatat di daftar dokumen",
           "Tipe lain ditolak 415 dan berkas > 10 MB ditolak 413, keduanya dengan pesan jelas",
           "Chunk rata-rata 400-600 token dengan overlap 50 token (diukur pada 3 dokumen contoh)",
           "Setiap chunk menyimpan document_id, nama file, halaman, dan urutan",
           "PDF scan tanpa teks berstatus failed, bukan menghasilkan chunk kosong",
           "Request upload berkas 5 MB kembali < 1 detik (pemrosesan di background)"),
       evidence=(f"{BE}/infrastructure/parsers/pdf_parser.py",
                 f"{BE}/infrastructure/parsers/docx_parser.py",
                 f"{BE}/infrastructure/parsers/markdown_parser.py",
                 f"{BE}/application/use_cases/ingest_doc.py",
                 f"{TESTS}/test_ingest.py",
                 f"{FE}/src/components/DocumentUploader.tsx"),
       depends_on=("INT-007", "INT-005"), source=_PRD),

    _t("INT-012", "Embedding lokal + pgvector (HNSW) + retrieval ambang 0.7",
       "i2", status="todo", priority="critical", estimate=1.5, labels=(*B, "epic-tooling", "rag"),
       description=(
           "ADR-03: vektor tinggal di PostgreSQL. Aktifkan ekstensi `pgvector` "
           "(image `pgvector/pgvector:pg16` di docker-compose), tambahkan kolom "
           "`document_chunks.embedding vector(384)` dan indeks HNSW "
           "(`vector_cosine_ops`, m=16, ef_construction=64) lewat migrasi "
           "Alembic. `EmbedderService` memakai sentence-transformers "
           "`all-MiniLM-L6-v2` (diunduh sekali, jalan offline, vektor "
           "dinormalisasi). `PgVectorRepository.search(query_vec, k=5, "
           "min_score=0.7, document_ids=None)` menjalankan pencarian cosine "
           "berindeks dan membuang hasil dengan similarity di bawah 0.7 "
           "(Tahap 4 pipeline). Chunk baru di-embed per batch 32; dokumen yang "
           "tidak berubah tidak di-embed ulang. `RetrieveRagUseCase` "
           "mengembalikan chunk beserta metadata sitasi. Test CI memakai "
           "embedder stub deterministik supaya tidak perlu mengunduh model."),
       workflow=(
           _w("Intern", "Aktifkan pgvector + migrasi kolom embedding dan indeks HNSW",
              "Skema vektor berversi"),
           _w("Intern", "Implementasi EmbedderService MiniLM + stub deterministik untuk test",
              "Embedding bisa dipakai offline dan di CI"),
           _w("Intern", "Implementasi PgVectorRepository.search dengan ambang 0.7 dan filter document_ids",
              "Retrieval berindeks"),
           _w("Intern", "Ukur latensi pada 1.000 chunk dan cek EXPLAIN",
              "Angka latensi tercatat di README"),
       ),
       wireframe="""
ALTER TABLE document_chunks ADD COLUMN embedding vector(384);
CREATE INDEX idx_chunks_hnsw ON document_chunks
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

search(query_vec, k=5, min_score=0.7, document_ids=None):
   SELECT c.id, c.content, c.page_number, d.name,
          1 - (c.embedding <=> :q) AS score
   FROM document_chunks c JOIN documents d ON d.id = c.document_id
   WHERE (:ids IS NULL OR d.id = ANY(:ids))
   ORDER BY c.embedding <=> :q LIMIT :k    -- lalu buang score < 0.7
""",
       acceptance=(
           "Pencarian pada 1.000 chunk selesai p95 < 200 ms dengan indeks HNSW (dicatat di README)",
           "Hasil dengan similarity < 0.7 tidak pernah dikembalikan ke prompt",
           "Dokumen relevan masuk 3 besar untuk 5 query uji",
           "Menambah 1 dokumen tidak meng-embed ulang chunk dokumen lain (dibuktikan counter pada stub embedder)",
           "EXPLAIN menunjukkan indeks HNSW dipakai, bukan sequential scan",
           "Test CI hijau tanpa mengunduh model embedding (embedder stub)"),
       evidence=(f"{BE}/infrastructure/embeddings/minilm_embedder.py",
                 f"{BE}/infrastructure/db/repositories/pgvector_repository.py",
                 f"{BE}/application/use_cases/retrieve_rag.py",
                 f"{TESTS}/test_retrieval.py"),
       depends_on=("INT-011",), source=_PRD),

    _t("INT-013", "Jawaban tergrounding + sitasi CitationBadge",
       "i2", status="todo", priority="critical", estimate=1.5, labels=(*B, *F, "epic-tooling", "rag"),
       description=(
           "US-01, US-02, US-03. Prompt ter-grounding menyusun konteks bernomor "
           "`[1] nama_file - hal. X: kutipan` (maks 2.500 token), mewajibkan "
           "sitasi `[n]` pada tiap klaim faktual, dan menetapkan jawaban baku "
           "'Informasi tidak ditemukan dalam dokumen internal' bila konteks "
           "kosong atau similarity < 0.7. Backend memancarkan event SSE "
           "`citation` berisi `{n, document_id, nama_file, halaman, kutipan}`. "
           "Frontend: `CitationBadge` (beUI `citations`: `<Citation />`, "
           "`<CitationList />`) mengubah `[n]` inline menjadi badge yang bisa "
           "diklik dan membuka rujukan nama file, halaman, dan kutipan asli. "
           "Pertanyaan di luar dokumen (mis. 'Aturan perjalanan dinas ke luar "
           "angkasa') harus dijawab tidak ditemukan, bukan dikarang."),
       workflow=(
           _w("Intern", "Susun template prompt grounded + aturan sitasi di application/prompts",
              "Prompt tersimpan di satu modul"),
           _w("Intern", "Pancarkan event citation dan render CitationBadge",
              "Sitasi bisa diklik"),
           _w("Intern", "Tangani konteks kosong: jawaban baku tanpa memanggil model",
              "Anti-halusinasi"),
           _w("Intern", "Uji 10 pertanyaan (7 di dokumen, 3 di luar dokumen)",
              "Angka tergrounding tercatat untuk metrik PRD"),
       ),
       wireframe="""
KONTEKS -> PROMPT
 [1] sop-cuti.pdf - hal. 3 : "Cuti tahunan diberikan 12 hari kerja ..."
 [2] sop-cuti.pdf - hal. 5 : "Persetujuan oleh atasan langsung ..."

JAWABAN
 Cuti tahunan 12 hari kerja per tahun [1]. Disetujui atasan langsung [2].

 klik [1] -> +--------------------------------------+
             | sop-cuti.pdf  hal. 3                 |
             | "Cuti tahunan diberikan 12 hari ..." |
             +--------------------------------------+
""",
       acceptance=(
           ">= 8 dari 10 pertanyaan uji dijawab dengan minimal satu sitasi valid",
           "3 dari 3 pertanyaan di luar dokumen dijawab 'tidak ditemukan', bukan dikarang",
           "Klik badge menampilkan nama file dan halaman yang benar (test komponen)",
           "Nomor sitasi yang tidak ada di konteks tidak dirender sebagai badge",
           "Konteks RAG tidak pernah melebihi 2.500 token"),
       evidence=(f"{BE}/application/prompts.py",
                 f"{FE}/src/components/CitationBadge.tsx",
                 f"{TESTS}/test_grounding.py"),
       depends_on=("INT-012", "INT-010"), source=_PRD),

    _t("INT-014", "Kelola dokumen: filter saat bertanya + hapus bersih dari vector DB",
       "i2", priority="high", estimate=1.5, labels=(*B, *F, "epic-tooling", "rag"),
       description=(
           "US-08 dan US-10. Halaman `/documents` (App Router) menampilkan "
           "daftar dokumen (nama, tipe, halaman, jumlah chunk, status, tanggal) "
           "dengan aksi hapus khusus admin. `DELETE /api/v1/documents/{id}` "
           "menghapus dokumen, chunk, vektor (cascade), dan berkas mentah dalam "
           "satu transaksi, lalu membatalkan cache terkait. Pada chat, power "
           "user memilih dokumen acuan lewat selector multi-pilih (beUI "
           "`select`/`popover-morph`); id terpilih dikirim sebagai "
           "`document_ids` ke `/chat/stream` dan diteruskan ke "
           "`PgVectorRepository.search(document_ids=...)` sehingga chunk "
           "konteks hanya berasal dari berkas itu. Setelah dokumen dihapus, "
           "pertanyaan terkait tidak boleh lagi mengambil referensi darinya "
           "(residu vektor = jawaban usang, titik nyeri persona Admin)."),
       workflow=(
           _w("Intern", "Bangun halaman /documents: daftar, status, aksi hapus",
              "Admin mengelola dokumen dari UI"),
           _w("Intern", "Implementasi DeleteDocumentUseCase transaksional + hapus berkas",
              "Tidak ada residu data"),
           _w("Intern", "Tambah selector dokumen di chat dan teruskan document_ids",
              "Retrieval terfokus"),
           _w("Intern", "Uji hapus lalu tanya ulang",
              "Tidak ada sitasi dari dokumen terhapus"),
       ),
       wireframe="""
CHAT: [ Dokumen acuan: sop-keuangan.pdf x  +tambah ]  -> document_ids=["d_17"]

/documents
+---------------------+------+-------+--------+--------+---------+
| Nama                | Tipe | Hal.  | Chunk  | Status | Aksi    |
| sop-keuangan.pdf    | pdf  |  14   |  52    | ready  | [trash] |
| kebijakan-hr.docx   | docx |   8   |  27    | ready  | [trash] |
+---------------------+------+-------+--------+--------+---------+
DELETE /api/v1/documents/{id}  -> 0 baris tersisa di documents, document_chunks, berkas disk
""",
       acceptance=(
           "Dengan filter satu dokumen, 100% chunk konteks berasal dari dokumen itu (10 query uji)",
           "Hapus dokumen menyisakan 0 baris di documents dan document_chunks serta 0 berkas di disk",
           "Setelah dihapus, pertanyaan terkait tidak lagi mensitasi dokumen tersebut (test e2e)",
           "Hanya admin yang bisa menghapus (peran lain mendapat 403)",
           "Daftar dokumen menampilkan perubahan status tanpa refresh manual (polling 2 detik)"),
       evidence=(f"{BE}/application/use_cases/delete_document.py",
                 f"{TESTS}/test_document_management.py",
                 f"{FE}/app/documents/page.tsx"),
       depends_on=("INT-013",), source=_PRD),

    _t("INT-015", "Tool registry (function calling) + agent loop berbatas",
       "i2", priority="critical", estimate=2, labels=(*B, "epic-tooling", "llm"),
       description=(
           "Kemampuan agent dibatasi pada tool terdaftar (non-goal #5: tanpa "
           "shell/OS bebas dan tanpa web-scraping bebas). `ToolRegistry` "
           "(application layer) mendaftarkan tool dengan nama, deskripsi, dan "
           "JSON schema parameter dari model pydantic v2, lalu mengekspornya ke "
           "format `tools=[...]` OpenAI-compatible; `ILLMProvider` diperluas "
           "agar menerima daftar pesan dan tools. Tool awal: "
           "`search_documents(query, document_ids?, k)` yang membungkus "
           "`RetrieveRagUseCase`; tool visual ditambahkan di INT-017 dan INT-018. "
           "`AgentLoop` menjalankan maksimal 3 iterasi tool, memvalidasi "
           "argumen terhadap schema, menolak nama tool di luar registry, dan "
           "memancarkan event SSE `tool_call` / `tool_result`. Frontend "
           "menampilkan jejak eksekusi dengan beUI `agent-activity` dan "
           "`tool-result` (collapsible, durasi per tool)."),
       workflow=(
           _w("Intern", "Bangun ToolRegistry + generator JSON schema dari pydantic",
              "Registry mengekspor tools=[...]"),
           _w("Intern", "Perluas ILLMProvider untuk messages + tools; mock bisa memicu tool_call",
              "Tool call bisa diuji deterministik"),
           _w("Intern", "Implementasi AgentLoop maks 3 iterasi + validasi argumen",
              "Panggilan liar gagal rapi"),
           _w("Intern", "Tampilkan jejak tool di UI (agent-activity + tool-result)",
              "Pengguna melihat tool yang dipakai"),
       ),
       wireframe="""
@tool(name="search_documents", args=SearchArgs)   # SearchArgs = model pydantic v2
registry.schemas() -> [{"type":"function","function":{"name":..., "parameters":{...json schema...}}}]

AGENT LOOP (maks 3 iterasi)
  model -> tool_call(name, args) -> validasi schema -> jalankan -> role=tool -> model lanjut
  nama tool tak dikenal / argumen salah -> pesan error ke model (bukan crash)
  iterasi ke-4 -> berhenti, jawab dengan informasi yang ada

UI (agent-activity)
  search_documents("cuti tahunan")   240 ms   [collapsible hasil]
""",
       acceptance=(
           "Minimal 1 tool terdaftar dan schema-nya lolos validasi JSON schema",
           "Argumen yang tidak sesuai schema ditolak dengan pesan ke model, tanpa crash",
           "Nama tool di luar registry selalu ditolak (0 eksekusi, diuji)",
           "Loop berhenti di iterasi ke-3 dan tetap menghasilkan jawaban",
           "UI menampilkan urutan tool yang dipanggil beserta durasi (ms)",
           "Mock provider dapat memicu tool_call deterministik untuk test"),
       evidence=(f"{BE}/application/tools/registry.py",
                 f"{BE}/application/use_cases/agent_loop.py",
                 f"{TESTS}/test_tool_registry.py",
                 f"{FE}/src/components/AgentTrace.tsx"),
       depends_on=("INT-013",), source=_PRD),

    _t("INT-016", "Router intent: Q&A dokumen, visualisasi, atau percakapan umum",
       "i2", priority="high", estimate=1.5, labels=(*B, "epic-tooling", "llm"),
       description=(
           "Tahap 3 pipeline. `RouterUseCase` mengklasifikasikan intensi: "
           "`grounded_qa` (-> RetrieveKnowledgeUseCase), `visual` "
           "(flowchart, bar chart, atau graph antardokumen -> "
           "GenerateVisualUseCase), dan `general` (percakapan umum/klarifikasi "
           "-> AgentStreamUseCase langsung tanpa retrieval). Tahap pertama "
           "memakai aturan murah (sapaan; kata kunci 'gambarkan', 'flowchart', "
           "'grafik', 'korelasi'); bila ragu (keyakinan < 0.6), panggil LLM "
           "kecil sekali dengan output JSON `{route, reason, confidence}` "
           "tervalidasi pydantic (retry 2x lalu default `grounded_qa`). "
           "Sapaan tidak boleh memicu embedding dan retrieval. Rute dipancarkan "
           "sebagai event SSE `status` dan dicatat ke trace (INT-023); "
           "parameter override disediakan untuk pengujian."),
       workflow=(
           _w("Intern", "Kumpulkan 30 contoh pertanyaan berlabel 3 rute",
              "Berkas data uji router"),
           _w("Intern", "Implementasi aturan murah + fallback klasifikasi LLM berskema pydantic",
              "RouterUseCase"),
           _w("Intern", "Ukur akurasi terhadap 30 contoh dan sambungkan ke pipeline",
              "Angka akurasi tercatat"),
           _w("Intern", "Pancarkan rute ke SSE status dan catat alasan",
              "Rute terlihat di UI dan trace"),
       ),
       wireframe="""
route(q) -> {"route": "grounded_qa|visual|general", "reason": "...", "confidence": 0.0-1.0}

 aturan murah : "halo", "terima kasih"                      -> general
                "gambarkan", "flowchart", "grafik batang"   -> visual
                kata domain (cuti, SOP, regulasi)           -> grounded_qa
 ragu (< 0.6) : 1x panggilan LLM (JSON), retry maks 2, default grounded_qa

 grounded_qa -> RetrieveKnowledgeUseCase
 visual      -> GenerateVisualUseCase
 general     -> AgentStreamUseCase (tanpa retrieval)
""",
       acceptance=(
           "Akurasi router >= 80% pada 30 contoh berlabel",
           ">= 90% pesan sapaan tidak memicu embedding maupun retrieval",
           "Rute, alasan, dan keyakinan tercatat untuk setiap request",
           "JSON klasifikasi rusak memicu retry maksimal 2 kali lalu default aman tanpa exception",
           "Override rute lewat parameter bekerja untuk pengujian"),
       evidence=(f"{BE}/application/use_cases/route_intent.py",
                 f"{TESTS}/test_router.py",
                 f"{TESTS}/data/router_30.json"),
       depends_on=("INT-015",), source=_PRD),

    _t("INT-017", "Visual interaktif: GraphView flowchart & korelasi antardokumen",
       "i2", priority="high", estimate=2, labels=(*B, *F, "epic-tooling", "llm"),
       description=(
           "US-06. `GenerateVisualUseCase` menghasilkan payload visual "
           "terstruktur tervalidasi pydantic (`VisualPayload`, tipe "
           "`flowchart` atau `doc_graph`): `nodes[{id, label, kind}]` dan "
           "`edges[{source, target, label}]`. Flowchart diekstrak dari teks "
           "prosedur dokumen (tiap langkah = 1 node). Doc graph memetakan "
           "korelasi antardokumen — **1 node per dokumen**, edge = rujukan atau "
           "korelasi regulasi, mis. SOP Ketenagakerjaan PT. XYZ dengan SK "
           "Menteri Ketenagakerjaan — memanfaatkan JOIN `document_chunks` dan "
           "`documents` di PostgreSQL. Payload dikirim sebagai event SSE "
           "`visual` dan tool `create_flowchart` / `create_doc_graph` "
           "didaftarkan ke ToolRegistry. Frontend: `GraphView.tsx` (node "
           "DOM interaktif: drag, zoom/pan, klik node membuka sumber) memakai "
           "token warna design system dan ikon lucide-react; pustaka grafik "
           "tambahan (mis. `@xyflow/react`) hanya setelah ADR disetujui."),
       workflow=(
           _w("Intern", "Definisikan VisualPayload (flowchart, doc_graph) + validator",
              "Skema visual tervalidasi"),
           _w("Intern", "Implementasi GenerateVisualUseCase + tool create_flowchart dan create_doc_graph",
              "Agent bisa menghasilkan payload"),
           _w("Intern", "Bangun GraphView interaktif (drag, zoom, klik node)",
              "Diagram bisa dijelajahi"),
           _w("Pembimbing", "Uji prompt contoh PRD US-06 end-to-end dengan mock",
              "Skenario US-06 lulus"),
       ),
       wireframe="""
VisualPayload
  {"type":"flowchart","nodes":[{"id":"n1","label":"Ajukan cuti","kind":"start"}, ...],
   "edges":[{"source":"n1","target":"n2","label":"kirim"}]}
  {"type":"doc_graph","nodes":[{"id":"d_1","label":"SOP Ketenagakerjaan"},
                               {"id":"d_2","label":"SK Menaker"}],
   "edges":[{"source":"d_1","target":"d_2","label":"merujuk Pasal 79"}]}

GraphView (drag / zoom / klik node -> buka sumber)
   [Ajukan cuti] --> [Atasan setuju?] --> [HR proses] --> [Selesai]
""",
       acceptance=(
           "Prompt contoh PRD US-06 memicu tool create_flowchart dan GraphView ter-render (test komponen + e2e mock)",
           "Node bisa di-drag dan di-zoom (test interaksi)",
           "Doc graph memiliki tepat 1 node per dokumen terkait",
           "Payload tidak valid (edge menunjuk node yang tidak ada) ditolak sebelum render",
           "Render 50 node selesai < 1 detik"),
       evidence=(f"{BE}/application/use_cases/generate_visual.py",
                 f"{TESTS}/test_generate_visual.py",
                 f"{FE}/src/components/GraphView.tsx"),
       depends_on=("INT-016", "INT-014"), source=_PRD),

    _t("INT-018", "Visual interaktif: ChartRenderer bar chart dari tabel dokumen",
       "i2", priority="high", estimate=1.5, labels=(*B, *F, "epic-tooling", "llm"),
       description=(
           "US-07 — ringkasan tabel dokumen menjadi grafik batang. Tool "
           "`create_chart(title, x_label, y_label, series[{label, value}])` "
           "dipanggil agent setelah mengekstrak baris tabel dari konteks "
           "retrieval (tabel DOCX/PDF sudah dipertahankan terstruktur oleh "
           "INT-011). Payload `ChartPayload` divalidasi: angka finit, maksimum "
           "30 titik, label unik. Frontend `ChartRenderer.tsx` merender bar "
           "chart interaktif (tooltip hover, urut naik/turun, filter seri) dengan "
           "SVG sendiri atau pustaka grafik yang disetujui lewat ADR, dilengkapi "
           "tabel yang dapat diurutkan dan difilter. Aksesibilitas: "
           "`role=\"img\"` dengan aria-label ringkasan data, dan "
           "`prefers-reduced-motion` dihormati."),
       workflow=(
           _w("Intern", "Definisikan ChartPayload + validator + tool create_chart",
              "Payload chart tervalidasi"),
           _w("Intern", "Ekstraksi baris tabel dari konteks retrieval ke series",
              "Data tabel menjadi data chart"),
           _w("Intern", "Bangun ChartRenderer + tabel interaktif",
              "Chart dan tabel tampil"),
           _w("Intern", "Uji 3 tabel contoh dari dokumen DOCX/PDF",
              "Nilai chart sama dengan tabel sumber"),
       ),
       wireframe="""
create_chart(title="Evaluasi Kinerja Q1", x_label="Divisi", y_label="Skor",
             series=[{"label":"Finance","value":82},{"label":"HR","value":77}, ...])

ChartRenderer
   Skor
    90 |        ##
    80 |  ##    ##    ##
    70 |  ##    ##    ##
       +--Finance--HR--Ops--   [urut: naik | turun]  [tooltip saat hover]
 tabel sumber (sortable/filterable) di bawah chart
""",
       acceptance=(
           "Prompt PRD US-07 ('Visualkan tabel evaluasi kinerja dalam bentuk grafik batang') menghasilkan chart",
           "Nilai chart identik dengan tabel sumber pada 3 tabel uji (selisih 0)",
           "Payload dengan NaN atau lebih dari 30 titik ditolak",
           "Tabel dapat diurutkan dan difilter; tooltip dan urutan bekerja (test komponen)",
           "prefers-reduced-motion menonaktifkan animasi (diuji)"),
       evidence=(f"{BE}/application/use_cases/generate_chart.py",
                 f"{TESTS}/test_chart_payload.py",
                 f"{FE}/src/components/ChartRenderer.tsx"),
       depends_on=("INT-016", "INT-011"), source=_PRD),

    _t("INT-033", "Pipeline RAG end-to-end: kontrak antar tahap, integrasi, dan uji golden set",
       "i2", status="todo", priority="critical", estimate=2,
       labels=(*B, "epic-tooling", "rag", "arsitektur"),
       description=(
           "Task payung untuk seluruh pipeline RAG: dokumen masuk -> teks -> "
           "chunk -> vektor -> pencarian -> prompt ter-grounding -> jawaban "
           "bersitasi (US-01, US-02, US-03, US-05). INT-011 (ingestion + "
           "chunking), INT-012 (embedding + pgvector + retrieval) dan INT-013 "
           "(grounding + sitasi) mengerjakan potongannya; INT-033 memastikan "
           "potongan itu SATU pipeline yang jalan dari ujung ke ujung dan "
           "terbukti dengan angka. Dua jalur: (A) OFFLINE saat unggah — "
           "validasi, parse per halaman, bersihkan header/footer, chunk ~500 "
           "token overlap 50, embed per batch 32, simpan ke `document_chunks`; "
           "(B) ONLINE saat bertanya — embed pertanyaan, cari pgvector HNSW "
           "(k=5, similarity >= 0.7, filter `document_ids`), bangun konteks "
           "bernomor maks 2.500 token, kirim ke LLM, validasi nomor sitasi, "
           "alirkan lewat SSE. Aturan yang berlaku untuk semua tahap: (1) tiap "
           "tahap bicara lewat kontrak tipe di `domain/` dan interface di "
           "`application/interfaces/` — use case tidak boleh meng-import "
           "`infrastructure/`, (2) semua angka (500, 50, 5, 0.7, 2.500) dibaca "
           "dari `config.py`/env, tidak ditulis mati di kode, (3) setiap tahap "
           "bisa diuji sendirian dengan stub (embedder stub deterministik + "
           "mock provider) tanpa internet, API key, atau unduhan model, (4) "
           "kegagalan satu tahap menjadi status/error yang jelas, bukan "
           "traceback dan bukan chunk kosong. Cara kerja task ini: dibuka "
           "bersamaan dengan INT-011 dan baru DITUTUP setelah INT-011/012/013 "
           "selesai (itulah arti depends_on-nya). Langkah 1 "
           "(hari pertama) mengunci kontrak, fixture, dan kerangka test e2e "
           "yang masih merah supaya pemilik INT-011/012/013 menulis kode ke "
           "kontrak yang sama; langkah terakhir menghijaukan test e2e, mengukur "
           "latensi tiap tahap, dan menulis `docs/RAG-PIPELINE.md` sebagai "
           "rujukan tim. Di luar lingkup: guardrail input/PII (INT-019/020), "
           "router intent (INT-016), tool visual (INT-017/018), semantic cache "
           "(INT-027), reranker, dan OCR PDF scan."),
       workflow=(
           _w("Intern", "Tulis kontrak di `domain/rag.py` (ParsedPage, Chunk, "
                        "RetrievedChunk, Citation) dan interface IDocumentParser, "
                        "IEmbedder, IChunkRepository di `application/interfaces/`",
              "Tipe & interface merge lebih dulu; INT-011/012/013 mengikutinya"),
           _w("Intern", "Siapkan 3 dokumen contoh (PDF, DOCX, MD) dan `golden.json` "
                        "12 pertanyaan (9 ada di dokumen, 3 di luar) beserta "
                        "dokumen+halaman jawaban yang benar",
              "Fixture di `tests/fixtures/rag/` dipakai semua orang"),
           _w("Intern", "Tulis kerangka `test_rag_pipeline_e2e.py` (unggah -> tanya "
                        "-> baca SSE) dengan embedder stub + mock provider; biarkan "
                        "merah sampai INT-011/012/013 selesai",
              "Target 'hijau' yang jelas bagi seluruh tim"),
           _w("Intern", "Tambahkan parameter RAG ke `config.py` (RAG_CHUNK_TOKENS, "
                        "RAG_CHUNK_OVERLAP, RAG_TOP_K, RAG_MIN_SCORE, "
                        "RAG_CONTEXT_TOKENS) + `.env.example`",
              "Tidak ada angka RAG yang tertulis mati di use case"),
           _w("Intern", "Setelah INT-011/012/013 masuk, sambungkan jalur ONLINE ke "
                        "`/api/v1/chat/stream`: retrieval -> konteks -> LLM -> "
                        "validasi sitasi -> event SSE status/citation/token/usage",
              "Satu request menghasilkan jawaban bersitasi dari dokumen yang diunggah"),
           _w("Intern", "Tangani 6 kegagalan di tabel kegagalan (PDF scan, berkas "
                        "rusak, embedding gagal, konteks kosong, dokumen terhapus "
                        "saat query, provider mati)",
              "Tiap kegagalan punya status/pesan terdefinisi + test"),
           _w("Intern", "Ukur latensi per tahap lewat `scripts/rag_smoke.py` "
                        "(1.000 chunk) dan hitung hasil golden set",
              "Angka nyata tercatat, bukan perkiraan"),
           _w("Intern", "Tulis `docs/RAG-PIPELINE.md`: diagram, kontrak, parameter, "
                        "cara debug per tahap, hasil ukur",
              "Anggota tim baru bisa menelusuri satu jawaban sampai chunk asalnya"),
           _w("Pembimbing", "Jalankan `scripts/rag_smoke.py` dari nol dan review "
                             "laporan golden set",
              "INT-033 disetujui; INT-014/015 boleh mulai"),
       ),
       wireframe="""
JALUR A — OFFLINE (unggah)                       tabel: documents.status
 upload --> validasi --> parse --> bersihkan --> chunk --> embed --> simpan
 (10 MB,    tipe PDF/    per       header/       500 tok   batch    document_chunks
  peran)    DOCX/MD      halaman   footer ulang  ov. 50    32       + embedding(384)
   |          |           |           |            |        |           |
 queued     parsing     parsing    chunking    chunking embedding     ready
                                                                  (gagal di mana pun -> failed + alasan)

JALUR B — ONLINE (bertanya)
 pertanyaan --> embed(query) --> pgvector HNSW --> bangun konteks --> prompt grounded
 + document_ids    384-dim       k=5, skor>=0.7    maks 2.500 tok     [1] nama - hal. X: kutipan
                                      |
                       kosong? --> jawaban baku "Informasi tidak ditemukan
                                   dalam dokumen internal" (LLM TIDAK dipanggil)
 --> LLM stream (maks 1.024 tok) --> validasi nomor [n] --> SSE:
     status(retrieval) -> status(generation) -> citation* -> token+ -> usage -> [DONE]

KONTRAK ANTAR TAHAP (domain/rag.py)
 ParsedPage     {page_number:int, text:str}
 Chunk          {document_id, chunk_index:int, page_number:int, content:str, token_count:int}
 RetrievedChunk {chunk_id, document_id, document_name, page_number, content, score:float}
 Citation       {n:int, document_id, document_name, page:int, quote:str}

 IDocumentParser.parse(data:bytes, filename:str) -> list[ParsedPage]
 IEmbedder.embed(texts:list[str]) -> list[list[float]]     # 384-dim, dinormalisasi
 PgVectorRepository.search(query_vec, k, min_score, document_ids|None) -> list[RetrievedChunk]
 RetrieveRagUseCase.execute(query, document_ids|None) -> list[RetrievedChunk]
 build_grounded_prompt(question, chunks, history) -> (messages, list[Citation])

PARAMETER (config.py / env)           PEMBAGIAN KERJA
 RAG_CHUNK_TOKENS=500                  INT-011  jalur A sampai tabel document_chunks
 RAG_CHUNK_OVERLAP=50                  INT-012  embed + pgvector + RetrieveRagUseCase
 RAG_TOP_K=5                           INT-013  prompt grounded + CitationBadge
 RAG_MIN_SCORE=0.7                     INT-033  kontrak, fixture, integrasi, e2e, docs
 RAG_CONTEXT_TOKENS=2500

KEGAGALAN -> PERILAKU
 PDF scan tanpa teks   -> documents.status=failed, alasan 'tanpa teks', 0 chunk
 berkas rusak/terenkripsi -> failed + alasan, upload tetap 202
 embedding gagal       -> failed + bisa diulang tanpa unggah ulang
 konteks kosong/<0.7   -> jawaban baku, 0 pemanggilan LLM
 dokumen dihapus saat query -> chunk itu dibuang, tidak ada sitasi ke dokumen terhapus
 provider mati         -> event error terstandar, bukan traceback

GOLDEN SET (tests/fixtures/rag/golden.json): 12 soal = 9 di dokumen + 3 di luar dokumen
""",
       acceptance=(
           "Kontrak (Chunk, RetrievedChunk, Citation, ParsedPage) dan 3 interface ada di domain/ dan application/interfaces/, serta tidak ada import dari infrastructure/ atau presentation/ di dua folder itu (dicek test)",
           "3 dokumen contoh (PDF, DOCX, MD) berstatus ready setelah unggah dan masing-masing menghasilkan > 0 chunk dengan metadata document_id, halaman, dan urutan lengkap",
           "Golden set 12 soal: >= 8 dari 9 soal dalam dokumen terjawab dengan sitasi yang menunjuk dokumen dan halaman yang benar",
           "Pada golden set, dokumen sumber masuk 3 besar hasil retrieval untuk >= 8 dari 9 soal dalam dokumen",
           "3 dari 3 soal di luar dokumen dijawab 'Informasi tidak ditemukan dalam dokumen internal' dengan 0 pemanggilan LLM (counter pada mock provider)",
           "Konteks RAG tidak pernah melebihi 2.500 token dan total prompt tidak melebihi 8.192 token, diuji pada dokumen panjang",
           "Urutan SSE satu jawaban: status(retrieval) lebih dulu, event citation sebelum [DONE], tepat 1 event usage lalu [DONE]",
           "Mengunggah ulang berkas identik tidak menambah chunk dan tidak memicu embed ulang (dibuktikan counter pada embedder stub)",
           "6 kegagalan di tabel kegagalan masing-masing punya test dan tidak ada yang menampilkan stack trace di respons",
           "RAG_CHUNK_TOKENS, RAG_CHUNK_OVERLAP, RAG_TOP_K, RAG_MIN_SCORE, RAG_CONTEXT_TOKENS terbaca dari env dan mengubah perilaku (test dengan nilai berbeda)",
           "pytest tests/test_rag_pipeline_e2e.py hijau tanpa internet, API key, maupun unduhan model, dan selesai < 60 detik",
           "scripts/rag_smoke.py mencetak durasi tiap tahap; retrieval p95 < 200 ms pada 1.000 chunk dan TTFT mock p95 <= 3 detik (10 run), dicatat di docs/RAG-PIPELINE.md",
           "docs/RAG-PIPELINE.md memuat diagram dua jalur, kontrak, tabel parameter, tabel kegagalan, cara debug per tahap, dan hasil ukur"),
       evidence=(f"{BE}/domain/rag.py",
                 f"{BE}/application/interfaces/rag.py",
                 f"{TESTS}/test_rag_pipeline_e2e.py",
                 f"{TESTS}/fixtures/rag/golden.json",
                 f"{P}/scripts/rag_smoke.py",
                 f"{P}/docs/RAG-PIPELINE.md"),
       depends_on=("INT-011", "INT-012", "INT-013"), source=_PRD),

    # ================================================================ Sprint 3
    _t("INT-019", "Guardrail input: panjang, prompt injection, jailbreak, topik terlarang",
       "i3", priority="critical", estimate=1.5, labels=(*B, "epic-guardrail"),
       description=(
           "Tahap 2 pipeline. Satukan validasi input yang kini tersebar di "
           "route menjadi `InputGuardrail`: panjang 1-2.000 karakter, deteksi "
           "prompt injection ('abaikan instruksi sebelumnya', 'tampilkan system "
           "prompt', 'kamu sekarang adalah...') dan jailbreak (role-play "
           "pelepas aturan), serta daftar topik terlarang yang bisa disunting "
           "admin tanpa deploy (tabel `guardrail_rules`). Pesan yang diblokir "
           "mendapat penolakan sopan beserta alasan lewat event SSE `error` "
           "berkode `GUARDRAIL_BLOCKED`, dan kejadiannya dicatat ke "
           "`guardrail_events(id, user_id, session_id, category, snippet, "
           "created_at)`. Teks chunk hasil retrieval diperlakukan sebagai data "
           "tidak tepercaya: instruksi di dalam dokumen tidak boleh dituruti "
           "(diuji dengan dokumen jebakan). Guardrail berjalan sebelum pesan "
           "menyentuh domain layer."),
       workflow=(
           _w("Intern", "Kumpulkan 20 contoh serangan + 20 pesan normal",
              "Set uji guardrail"),
           _w("Intern", "Implementasi InputGuardrail + tabel guardrail_rules + pencatatan guardrail_events",
              "Pesan berbahaya terblokir dan tercatat"),
           _w("Intern", "Tambah uji dokumen jebakan (injection lewat RAG) dan pembatas konteks tak tepercaya",
              "Instruksi di dokumen tidak dituruti"),
           _w("Intern", "Sediakan penyuntingan daftar terlarang oleh admin",
              "Aturan berubah tanpa deploy"),
       ),
       wireframe="""
check_input(text) -> {ok, category, reason}
  category: too_long | injection | jailbreak | forbidden_topic | ok

DITOLAK  (SSE error GUARDRAIL_BLOCKED)
  "Permintaan ini tidak dapat diproses (terdeteksi upaya mengabaikan aturan).
   Silakan ajukan pertanyaan tentang dokumen tanpa meminta saya mengubah instruksi."

guardrail_rules(id, kind, pattern, active)         <- disunting admin
guardrail_events(id, user_id, session_id, category, snippet, created_at)
""",
       acceptance=(
           ">= 18 dari 20 contoh serangan terblokir (recall >= 90%)",
           "<= 1 dari 20 pesan normal ikut terblokir (false positive <= 5%)",
           "Dokumen jebakan berisi instruksi tidak mengubah perilaku model (uji otomatis)",
           "Setiap blokir tercatat di guardrail_events dengan kategori dan cuplikan",
           "Daftar topik terlarang bisa disunting admin tanpa mengubah kode; input > 2.000 karakter ditolak 422"),
       evidence=(f"{BE}/application/guardrails/input_guardrail.py",
                 f"{TESTS}/test_input_guardrail.py",
                 f"{TESTS}/data/attacks_20.json"),
       depends_on=("INT-016",), source=_PRD),

    _t("INT-020", "Redaksi PII sebelum konteks dikirim ke provider",
       "i3", priority="critical", estimate=1.5, labels=(*B, "epic-guardrail"),
       description=(
           "Penyaringan PII di Tahap 2 pipeline. `PiiRedactor` menyensor data "
           "sensitif Indonesia sebelum teks meninggalkan aplikasi: NIK 16 "
           "digit, nomor kartu kredit (validasi Luhn agar angka biasa tidak "
           "ikut tersensor), email, nomor telepon (+62/08...), dan NPWP. Tiap "
           "temuan diganti token stabil `[NIK_1]`, `[EMAIL_1]` dan dipetakan di "
           "memori proses per request, sehingga jawaban model bisa dipulihkan "
           "saat ditampilkan; peta itu tidak pernah ditulis ke disk, database, "
           "maupun log. Redaksi berlaku untuk pesan pengguna DAN chunk hasil "
           "retrieval (dokumen internal bisa memuat data karyawan). Jenis PII "
           "dapat diaktifkan per jenis lewat konfigurasi; payload ke provider "
           "eksternal (OpenAI) selalu tersensor, sedangkan vLLM on-premise "
           "boleh dikecualikan lewat flag."),
       workflow=(
           _w("Intern", "Tulis detektor + validasi Luhn untuk 5 jenis PII",
              "PiiRedactor"),
           _w("Intern", "Terapkan di jalur prompt (pesan + chunk retrieval)",
              "Provider eksternal tidak menerima PII mentah"),
           _w("Intern", "Implementasi pemulihan token saat menampilkan jawaban",
              "Pengguna tetap melihat nilai asli"),
           _w("Intern", "Uji 30 contoh positif + 30 negatif",
              "Angka recall dan false positive tercatat"),
       ),
       wireframe="""
redact("NIK saya 3201234567890123, email a@b.com")
  -> "NIK saya [NIK_1], email [EMAIL_1]"   + peta {NIK_1: ..., EMAIL_1: ...}   (memori proses saja)

restore(jawaban, peta) -> jawaban dengan nilai asli (hanya untuk layar pengguna)

DILINDUNGI : pesan pengguna, chunk retrieval, ringkasan sesi
FLAG       : PII_REDACT_PROVIDERS=openai   (vllm on-premise: dikecualikan)
""",
       acceptance=(
           "Recall >= 95% pada 30 contoh PII dan false positive <= 5% pada 30 teks biasa",
           "Kartu kredit hanya tersensor bila lolos Luhn",
           "Payload yang diterima provider terbukti bebas PII (test menangkap payload)",
           "Peta pemulihan tidak pernah ditulis ke disk, tabel, atau log (test inspeksi)",
           "Redaksi juga berlaku pada chunk hasil retrieval"),
       evidence=(f"{BE}/application/guardrails/pii.py",
                 f"{TESTS}/test_pii.py", f"{TESTS}/data/pii_cases.json"),
       depends_on=("INT-019",), source=_PRD),

    _t("INT-021", "Validator output: grounding, ambang 0.7, dan skema visual",
       "i3", priority="high", estimate=1.5, labels=(*B, "epic-guardrail", "llm"),
       description=(
           "Tahap 6 pipeline: `GroundingValidator` dan `VisualSchemaValidator`. "
           "(1) Verifikasi setiap nomor sitasi `[n]` ada di konteks; sitasi "
           "halusinasi dibuang dan dicatat. (2) Threshold: bila tidak ada chunk "
           "dengan similarity >= 0.7, paksa jawaban fallback 'informasi tidak "
           "ditemukan' tanpa memanggil model. (3) Validasi JSON schema payload "
           "visual (GraphView / bar chart) dengan pydantic; payload rusak "
           "dikirim ulang ke LLM maksimal 2 kali dengan pesan error parser "
           "yang spesifik, lalu fallback aman (teks/tabel biasa) — pipeline "
           "tidak boleh mati karena model salah format. (4) Hitung penanda "
           "`grounded` (punya sitasi valid) per respons untuk metrik di INT-026 "
           "dan dasbor."),
       workflow=(
           _w("Intern", "Implementasi GroundingValidator: cek sitasi terhadap konteks",
              "Sitasi halusinasi dibuang"),
           _w("Intern", "Implementasi ambang 0.7: tanpa konteks memadai jawab fallback tanpa panggil model",
              "Anti-halusinasi tegas"),
           _w("Intern", "Implementasi retry berpesan error untuk payload visual rusak",
              "Pipeline tidak mati"),
           _w("Intern", "Simpan flag grounded per pesan",
              "Metrik tergrounding bisa dihitung"),
       ),
       wireframe="""
validate_grounding(answer, context) -> {answer_bersih, sitasi_valid[], dibuang[], grounded: bool}
  ada [3] padahal konteks hanya [1][2]  -> [3] dibuang, dicatat

similarity_max < 0.7  -> "Informasi tidak ditemukan dalam dokumen internal"  (0 panggilan model)

validate_visual(payload, VisualPayload | ChartPayload)
  gagal -> kirim ulang ke LLM dengan pesan parser (maks 2x) -> fallback teks/tabel
""",
       acceptance=(
           "Sitasi yang tidak ada di konteks dibuang 100% (10 kasus uji)",
           "Tanpa chunk berskor >= 0.7 jawaban fallback keluar dengan 0 panggilan provider (test)",
           "Payload visual rusak memicu retry <= 2 kali lalu fallback aman tanpa exception ke UI",
           "Flag grounded tersimpan per pesan assistant",
           "Semua jalur memakai skema pydantic, tanpa parsing JSON manual"),
       evidence=(f"{P}/backend/app/domain/grounding.py",
                 f"{BE}/application/validators/visual_schema.py",
                 f"{TESTS}/test_validators.py"),
       depends_on=("INT-018", "INT-017", "INT-013"), source=_PRD),

    _t("INT-022", "Uji red-team otomatis + laporan guardrail",
       "i3", priority="high", estimate=1, labels=(*B, "epic-guardrail"),
       description=(
           "Guardrail yang tidak diuji hanya klaim. Susun set 80 skenario "
           "(40 serangan + 40 pesan normal): injection langsung, injection lewat "
           "dokumen, jailbreak role-play, upaya mengekstrak system prompt, "
           "upaya membaca data lintas peran, dan permintaan menjalankan perintah "
           "shell di luar scope tool (non-goal #5). Skrip `scripts/redteam.py` "
           "menjalankannya lewat pipeline penuh (mock provider, tanpa API key) "
           "dan menulis `docs/GUARDRAIL-REPORT.md`: recall dan false positive "
           "per kategori, kasus yang lolos, dan perbaikan aturannya. Skrip "
           "dijalankan di CI sehingga regresi guardrail langsung terlihat."),
       workflow=(
           _w("Intern", "Susun 40 serangan + 40 pesan normal berlabel kategori",
              "redteam_80.json"),
           _w("Intern", "Tulis scripts/redteam.py yang menjalankan pipeline dan menghitung metrik",
              "Laporan per kategori"),
           _w("Intern", "Perbaiki aturan guardrail untuk kasus yang lolos lalu ulangi",
              "Target terpenuhi"),
           _w("Intern", "Pasang di CI",
              "Regresi guardrail terdeteksi otomatis"),
       ),
       wireframe="""
python scripts/redteam.py
 +---------------------------+--------+--------+
 | Kategori                  | Recall | FP     |
 | injection langsung        | 10/10  | 0/10   |
 | injection lewat dokumen   |  9/10  | 1/10   |
 | jailbreak                 |  9/10  |  -     |
 | ekstraksi system prompt   | 10/10  |  -     |
 | perintah shell            | 10/10 (0 eksekusi) |
 +---------------------------+--------+--------+
 laporan -> docs/GUARDRAIL-REPORT.md (bertanggal)
""",
       acceptance=(
           "Set berisi tepat 40 serangan dan 40 pesan normal",
           "Recall keseluruhan >= 90% dan false positive <= 5%",
           "`python scripts/redteam.py` selesai < 60 detik tanpa API key",
           "0 skenario perintah shell yang benar-benar dieksekusi (non-goal #5)",
           "Laporan per kategori tersimpan di docs/GUARDRAIL-REPORT.md dan dijalankan di CI"),
       evidence=(f"{P}/scripts/redteam.py", f"{TESTS}/data/redteam_80.json",
                 f"{P}/docs/GUARDRAIL-REPORT.md"),
       depends_on=("INT-021", "INT-020"), source=_PRD),

    # ================================================================ Sprint 4
    _t("INT-023", "Tracing mandiri: span 7 tahap ke tabel PostgreSQL + halaman trace",
       "i4", priority="critical", estimate=2, labels=(*B, *F, "epic-observability"),
       description=(
           "ADR-04. `TracerService` (infrastructure) mencatat span bertingkat "
           "ke tabel PostgreSQL `traces(trace_id, parent_id, session_id, "
           "user_id, name, started_at, duration_ms, meta jsonb, status)` secara "
           "asinkron (tidak memblokir stream) untuk 7 tahap pipeline: "
           "guardrail, router, retrieval, build_context, llm_stream "
           "(termasuk TTFT), tool, dan validate_output. `trace_id` dikirim "
           "lewat event SSE `usage` dan header respons. Halaman admin "
           "`/admin/traces` menampilkan daftar request terbaru dan waterfall "
           "satu request (beUI `agent-activity`) beserta tombol salin trace_id. "
           "Overhead pencatatan harus < 5% dari durasi total (batch insert "
           "lewat antrean). Indeks pada `started_at` dan `trace_id`."),
       workflow=(
           _w("Intern", "Buat context manager span + tabel traces + migrasi",
              "TracerService"),
           _w("Intern", "Pasang span di 7 tahap pipeline",
              "Satu jawaban menghasilkan pohon span lengkap"),
           _w("Intern", "Bangun halaman /admin/traces (daftar + waterfall)",
              "Durasi tiap tahap terlihat"),
           _w("Intern", "Ukur overhead tracing",
              "Angka overhead tercatat"),
       ),
       wireframe="""
TRACE a1b2c3   total 2.410 ms   [salin trace_id]
 guardrail_input     | 12 ms
 router              | 140 ms
 retrieval           | 310 ms   (k=5, skor 0.81 / 0.77 / 0.72)
 build_context       | 18 ms    (3.120 token)
 llm_stream          | 1.870 ms (TTFT 640 ms, 412 token)
 validate_output     | 9 ms
 persist + trace     | 51 ms

traces(trace_id, parent_id, session_id, user_id, name, started_at, duration_ms, meta jsonb, status)
""",
       acceptance=(
           "Satu jawaban menghasilkan minimal 7 span dengan durasi terisi",
           "trace_id tampil di UI dan bisa disalin",
           "Halaman waterfall menampilkan urutan dan durasi tiap span",
           "Overhead tracing < 5% dari durasi total (diukur dan dicatat)",
           "Span gagal ditandai status=error beserta pesannya; hanya admin yang membuka halaman (403 lainnya)"),
       evidence=(f"{BE}/infrastructure/tracing/tracer.py",
                 f"{TESTS}/test_tracing.py",
                 f"{FE}/app/admin/traces/page.tsx"),
       depends_on=("INT-016", "INT-007"), source=_PRD),

    _t("INT-024", "Biaya & token: kalkulator Rupiah, inspektur respons, dasbor admin",
       "i4", priority="high", estimate=1.5, labels=(*B, *F, "epic-observability"),
       description=(
           "US-09 dan metrik biaya per percakapan (<= Rp500) di PRD bagian B. "
           "`CostCalculator` memakai tarif dari konfigurasi "
           "(`PRICE_INPUT_PER_1K_IDR=2.4`, `PRICE_OUTPUT_PER_1K_IDR=9.6`, acuan "
           "gpt-4o-mini kurs Rp16.000) dengan rumus Biaya = (token_masuk/1000 x "
           "tarif_masuk) + (token_keluar/1000 x tarif_keluar), dan menyimpan "
           "hasilnya ke `token_usage_logs.cost_idr` (kolom baru lewat migrasi). "
           "Panel inspektur per respons (beUI disclosure) menampilkan prompt "
           "tokens, completion tokens, biaya Rupiah, TTFT, dan trace_id. Dasbor "
           "admin `/admin/usage` (hari ini / 7 hari / 30 hari): total token, "
           "biaya, jumlah sesi, biaya rata-rata per percakapan, TTFT p50 dan "
           "p95, 5 sesi termahal, dan ekspor CSV."),
       workflow=(
           _w("Intern", "Implementasi CostCalculator + tarif dari konfigurasi + kolom cost_idr",
              "Biaya tercatat per pemanggilan"),
           _w("Intern", "Bangun panel inspektur respons",
              "Metrik tampil per pesan"),
           _w("Intern", "Tulis query agregasi + halaman /admin/usage + ekspor CSV",
              "Angka per rentang waktu"),
           _w("Pembimbing", "Cocokkan satu sesi secara manual dengan angka dasbor",
              "Selisih 0 token"),
       ),
       wireframe="""
Biaya (Rp) = (token_masuk / 1000 x 2,4) + (token_keluar / 1000 x 9,6)
  1.200 masuk + 300 keluar   = 2,88 + 2,88   = Rp5,76
  8.000 masuk + 1.024 keluar = 19,20 + 9,83  = Rp29,03

/admin/usage  [ hari ini | 7 hari | 30 hari ]                [ekspor CSV]
+--------------+--------------+------------+-----------+
| Token masuk  | Token keluar | Biaya (Rp) | Sesi      |
+--------------+--------------+------------+-----------+
| TTFT p50     | TTFT p95     | Rp / sesi  | Rasio suka|
+--------------+--------------+------------+-----------+
5 sesi termahal ...
""",
       acceptance=(
           "Dua contoh PRD (1.200+300 token = Rp5,76; 8.000+1.024 token = Rp29,03) lulus sebagai test numerik",
           "Angka token dasbor sama persis dengan penjumlahan manual satu sesi (selisih 0)",
           "TTFT p50 dan p95 dihitung dari span llm_stream, bukan perkiraan",
           "Filter 3 rentang waktu mengubah seluruh kartu angka; ekspor CSV memuat tanggal, sesi, token, biaya, TTFT",
           "Tarif per 1k token diambil dari konfigurasi, bukan hardcode"),
       evidence=(f"{BE}/application/services/cost_calculator.py",
                 f"{TESTS}/test_cost_calculator.py",
                 f"{FE}/app/admin/usage/page.tsx"),
       depends_on=("INT-023", "INT-009"), source=_PRD),

    _t("INT-025", "Feedback suka/tidak suka dengan alasan terstruktur + trace_id",
       "i4", priority="high", estimate=1, labels=(*B, *F, "epic-observability"),
       description=(
           "Metrik rasio kepuasan >= 70% (PRD bagian B). Tiap bubble asisten "
           "punya tombol Suka dan Tidak suka (ikon lucide `ThumbsUp` / "
           "`ThumbsDown`, tanpa emoji). Tidak suka membuka pilihan alasan "
           "terstruktur: tidak akurat, tidak menjawab, sitasi salah, terlalu "
           "panjang, bahasa kurang jelas — plus komentar opsional. Tabel "
           "`feedback(id, trace_id, session_id, message_id, user_id, value, "
           "reason, comment, created_at)` dengan UNIQUE(message_id, user_id) "
           "sehingga penilaian bisa diubah tanpa baris ganda dan tiap penilaian "
           "bisa ditelusuri ke trace lengkapnya. Dasbor `/admin/usage` "
           "menampilkan rasio = suka / (suka + tidak suka) dan 5 alasan teratas."),
       workflow=(
           _w("Intern", "Buat tabel feedback + use case simpan/ubah",
              "SubmitFeedbackUseCase"),
           _w("Intern", "Tambah tombol dan dialog alasan di UI beUI",
              "Feedback terkirim 1 klik"),
           _w("Intern", "Tampilkan rasio dan alasan teratas di dasbor",
              "Kualitas terukur"),
           _w("Intern", "Pastikan trace_id tersimpan",
              "Jawaban buruk bisa ditelusuri"),
       ),
       wireframe="""
 agent: Cuti tahunan 12 hari [1].             [ThumbsUp] [ThumbsDown]
        Tidak suka dipilih:
        ( ) tidak akurat  ( ) tidak menjawab  ( ) sitasi salah
        ( ) terlalu panjang ( ) bahasa kurang jelas
        [ komentar (opsional) ............... ] [Kirim]

feedback(id, trace_id, session_id, message_id, user_id, value[1|-1], reason, comment, created_at)
  UNIQUE(message_id, user_id)
DASBOR: rasio suka 74% (37/50)   alasan teratas: sitasi salah (6)
""",
       acceptance=(
           "Suka tersimpan dengan satu klik tanpa dialog tambahan",
           "Tidak suka mewajibkan satu alasan dari 5 opsi sebelum tersimpan",
           "Setiap baris feedback memuat trace_id valid yang bisa dibuka di halaman trace",
           "Dasbor menampilkan rasio suka dan 5 alasan terbanyak",
           "Penilaian yang sama bisa diubah tanpa menghasilkan baris ganda (UNIQUE message_id + user_id)"),
       evidence=(f"{BE}/application/use_cases/submit_feedback.py",
                 f"{TESTS}/test_feedback.py",
                 f"{FE}/src/components/FeedbackButtons.tsx"),
       depends_on=("INT-023",), source=_PRD),

    _t("INT-026", "Set evaluasi 20 soal + skrip eval offline (metrik tergrounding)",
       "i4", priority="high", estimate=1.5, labels=(*B, "epic-observability", "llm"),
       description=(
           "Metrik utama 'jawaban tergrounding >= 80%' dari 20 soal uji "
           "(`data/eval/grounding_20.json`). Susun 20 pertanyaan dari dokumen "
           "demo: 12 yang jawabannya ada di dokumen (kunci jawaban + file dan "
           "halaman sitasi yang benar), 5 di luar dokumen (harus dijawab "
           "tidak ditemukan), dan 3 yang butuh visual (flowchart, chart, "
           "graph). `scripts/eval.py` menjalankan semuanya lewat pipeline "
           "asli (provider dari env, default mock) dan mencetak: persen "
           "tergrounding (rumus PRD: jawaban bersitasi valid / 20), akurasi "
           "sitasi, ketepatan 'tidak ditemukan', rata-rata token, p95 TTFT, "
           "dan biaya total satu putaran. Hasil disimpan bertanggal untuk "
           "membandingkan sebelum dan sesudah perbaikan prompt."),
       workflow=(
           _w("Intern", "Susun 20 soal + kunci jawaban + sumber yang benar",
              "grounding_20.json"),
           _w("Intern", "Tulis scripts/eval.py yang menjalankan pipeline dan menilai",
              "Laporan evaluasi tercetak"),
           _w("Intern", "Jalankan baseline dan simpan hasilnya",
              "Angka awal tercatat"),
           _w("Intern", "Ulangi setelah perbaikan prompt",
              "Perbandingan sebelum/sesudah"),
       ),
       wireframe="""
data/eval/grounding_20.json
 - {"id":"E01","question":"Berapa hari jatah cuti tahunan?","answer_key":"12 hari",
    "source":"sop-cuti.pdf#3","type":"in_doc"}

python scripts/eval.py --run baseline
 +--------------------------+--------+
 | tergrounding (>= 80%)    | 17/20  |
 | sitasi benar (in_doc)    | 10/12  |
 | 'tidak ditemukan' benar  |  5/5   |
 | visual benar             |  2/3   |
 | rata-rata token          | 1.840  |
 | p95 TTFT / biaya total   | 2,4 s / Rp0,98 |
 +--------------------------+--------+
""",
       acceptance=(
           "Set berisi tepat 20 soal dengan komposisi 12 dalam dokumen, 5 luar dokumen, 3 visual",
           "`python scripts/eval.py` berjalan end-to-end memakai mock provider tanpa API key",
           "Persen tergrounding dihitung dengan rumus yang sama persis dengan PRD bagian B",
           "Laporan memuat 6 metrik dan disimpan ke berkas hasil bertanggal; baseline tersimpan di repo",
           "Satu perbaikan prompt didokumentasikan dengan angka sebelum/sesudah"),
       evidence=(f"{P}/data/eval/grounding_20.json", f"{P}/scripts/eval.py",
                 f"{P}/docs/EVAL.md"),
       depends_on=("INT-025", "INT-021"), source=_PRD),

    # ================================================================ Sprint 5
    _t("INT-027", "Semantic cache di PostgreSQL: jawab pertanyaan berulang tanpa LLM",
       "i5", priority="high", estimate=1.5, labels=(*B, "epic-performa"),
       description=(
           "Metrik cache hit-rate >= 20% pada pertanyaan berulang (PRD bagian B). "
           "Tabel PostgreSQL `cache(id, question, embedding vector(384), answer, "
           "citations jsonb, prompt_version, document_scope, created_at, hits)` "
           "dan tabel telemetri hit/miss. Sebelum memanggil LLM: embed "
           "pertanyaan, cari cosine >= 0.92 dengan umur < 24 jam, cakupan "
           "dokumen (`document_ids`) dan `prompt_version` yang sama; bila hit, "
           "kembalikan jawaban beserta sitasinya dan tandai di UI 'dari cache' "
           "(ikon lucide `Zap`). Cache dibatalkan otomatis saat dokumen sumber "
           "dihapus atau diunggah ulang (INT-014) atau `prompt_version` naik, "
           "dan tidak dipakai untuk jawaban yang memicu tool visual. Respons "
           "cache tetap melewati guardrail input dan kuota."),
       workflow=(
           _w("Intern", "Buat tabel cache + telemetri hit/miss + migrasi",
              "Cache terisi"),
           _w("Intern", "Implementasi lookup cosine >= 0.92, TTL 24 jam, scope dokumen",
              "Hit terdeteksi"),
           _w("Intern", "Tambah invalidasi saat dokumen berubah/dihapus atau prompt_version naik",
              "Jawaban basi tidak disajikan"),
           _w("Intern", "Ukur hit-rate dan token yang dihemat",
              "Angka tampil di /admin/usage"),
       ),
       wireframe="""
lookup(q, document_ids):
  qv = embed(q)
  cari di cache WHERE prompt_version = aktif AND umur < 24 jam AND document_scope sama
  skor >= 0.92 ? -> HIT  (hits += 1, 0 token LLM)
               : -> MISS (jalankan pipeline, simpan hasil)

UI: jawaban ...   [lucide: Zap] dari cache (hemat ~1.800 token)
INVALIDASI: dokumen dihapus/diunggah ulang | prompt_version naik | tool visual dipakai
hit_rate = hit / (hit + miss) pada pertanyaan berulang
""",
       acceptance=(
           "Pertanyaan yang diulang persis menghasilkan cache hit dan 0 token LLM baru di token_usage_logs",
           "Parafrase dekat (cosine >= 0.92) hit dan parafrase jauh miss (10 pasang uji)",
           "Hapus dokumen atau naik prompt_version membatalkan entri terkait",
           "Jawaban yang memicu tool visual tidak pernah di-cache",
           "Hit-rate >= 20% pada simulasi 50 pertanyaan dengan 40% berulang, tampil di /admin/usage"),
       evidence=(f"{BE}/infrastructure/cache/semantic_cache.py",
                 f"{TESTS}/test_semantic_cache.py"),
       depends_on=("INT-024", "INT-014"), source=_PRD),

    _t("INT-028", "Kuota harian 50 pesan / 100.000 token + rate limit per pengguna",
       "i5", priority="high", estimate=1.5, labels=(*B, *F, "epic-performa"),
       description=(
           "Anggaran PRD bagian B: kuota harian 50 pesan atau 100.000 token per "
           "pengguna (mana yang tercapai dulu). `QuotaService` (Tahap 2 "
           "pipeline) membaca pemakaian dari `token_usage_logs` dan hitungan "
           "pesan hari ini (zona waktu Asia/Jakarta, reset tengah malam), "
           "ditambah pembatas burst 10 pesan per menit (token bucket) dan "
           "maksimum 2 stream bersamaan per pengguna (`asyncio.Semaphore`) agar "
           "provider tidak terkena lonjakan. Respons 429 membawa `Retry-After` "
           "dan sisa kuota; UI menampilkan banner jelas dengan sisa waktu (ikon "
           "lucide `Clock`), bukan error mentah. Angka batas dibaca dari "
           "konfigurasi (`QUOTA_DAILY_MESSAGES`, `QUOTA_DAILY_TOKENS`, "
           "`QUOTA_BURST_PER_MIN`) sehingga bisa diubah tanpa mengubah kode."),
       workflow=(
           _w("Intern", "Implementasi QuotaService harian (pesan + token) dan token bucket burst",
              "Batas dihitung dari data nyata"),
           _w("Intern", "Sambungkan ke pipeline: 429 + Retry-After + sisa kuota",
              "Batas terasa wajar, bukan error"),
           _w("Intern", "Tambah semaphore 2 stream per pengguna",
              "Burst tidak menembus provider"),
           _w("Intern", "Bangun QuotaBanner di UI dan uji 20 permintaan beruntun",
              "Perilaku sesuai batas"),
       ),
       wireframe="""
BATAS (konfigurasi, bukan hardcode)
  50 pesan / hari | 100.000 token / hari | 10 pesan / menit | 2 stream bersamaan

429  Retry-After: 24   {"code":"QUOTA_EXCEEDED","remaining":{"messages":18,"tokens":42100}}

UI banner:
  [lucide: Clock] Kuota per menit habis. Coba lagi dalam 24 detik.
                  Sisa hari ini: 18 pesan, 42.100 token
""",
       acceptance=(
           "Pesan ke-51 pada hari yang sama ditolak 429",
           "Pengguna yang mencapai 100.000 token ditolak walau pesannya < 50",
           "Permintaan ke-11 dalam satu menit ditolak dengan Retry-After yang benar",
           "Kuota harian reset lewat tengah malam WIB (test dengan clock palsu)",
           "20 permintaan beruntun tidak menghasilkan error 429 dari provider",
           "Angka batas dibaca dari konfigurasi dan penolakan tercatat di trace"),
       evidence=(f"{BE}/application/services/quota.py",
                 f"{TESTS}/test_quota.py",
                 f"{FE}/src/components/QuotaBanner.tsx"),
       depends_on=("INT-027", "INT-009"), source=_PRD),

    _t("INT-029", "Rantai provider LLM + fallback dan timeout (mock selalu cadangan)",
       "i5", priority="high", estimate=1, labels=(*B, "epic-performa", "llm"),
       description=(
           "ADR-05: provider nyata dan Mock Provider wajib. `ProviderChain` "
           "membaca `LLM_PROVIDERS=openai,vllm,mock` (urutan prioritas) dan "
           "mencoba berikutnya bila terjadi error 5xx, timeout 30 detik, atau "
           "tidak ada token pertama dalam 10 detik; error 429 dan 5xx "
           "di-retry 2 kali dengan backoff eksponensial sebelum pindah provider. "
           "Mock selalu cadangan terakhir sehingga demo tidak pernah gagal total. "
           "UI menandai model yang akhirnya menjawab bila bukan yang utama "
           "(badge kecil, ikon lucide `RefreshCw`), setiap peralihan dicatat ke "
           "trace beserta alasannya, dan `/health` menampilkan status tiap "
           "provider."),
       workflow=(
           _w("Intern", "Implementasi ProviderChain + daftar prioritas dari env",
              "Peralihan otomatis"),
           _w("Intern", "Tambah timeout, retry backoff, dan deteksi TTFT > 10 detik",
              "Gangguan sementara tidak menjatuhkan layanan"),
           _w("Intern", "Uji dengan provider palsu yang melempar 500 dan timeout",
              "Fallback terbukti"),
           _w("Pembimbing", "Matikan provider utama saat demo",
              "Jawaban tetap keluar"),
       ),
       wireframe="""
LLM_PROVIDERS = "openai, vllm, mock"

 openai -> 5xx | timeout 30 s | TTFT > 10 s | 429 (retry 2x: 1 s, 2 s) -> vllm
 vllm   -> gagal                                                       -> mock (selalu berhasil)

UI: jawaban ...   [lucide: RefreshCw] dijawab oleh vllm (openai timeout)
/health -> llm: [{openai: down}, {vllm: up}, {mock: up}]
""",
       acceptance=(
           "Provider utama yang dimatikan memicu fallback dalam < 31 detik",
           "Dengan mock sebagai cadangan terakhir, 10 skenario kegagalan tidak menghasilkan kegagalan total",
           "UI menampilkan model yang menjawab bila bukan provider utama",
           "Setiap peralihan tercatat di trace beserta alasannya",
           "Test memakai provider palsu yang melempar 500 dan timeout; retry 2x pada 429 terbukti"),
       evidence=(f"{BE}/infrastructure/llm/provider_chain.py",
                 f"{TESTS}/test_provider_chain.py"),
       depends_on=("INT-028",), source=_PRD),

    _t("INT-030", "Deploy persisten: Docker Compose + volume PostgreSQL/pgvector + Coolify",
       "i5", priority="critical", estimate=1, labels=(*B, "epic-performa", "docs"),
       description=(
           "Boilerplate INT-005 sudah punya `docker-compose.yml` (frontend, "
           "backend, postgres) dan `Dockerfile` tunggal. Task ini menjamin "
           "**persistensi dan rilis**: image postgres `pgvector/pgvector:pg16` "
           "dengan named volume `pgdata`, volume `uploads` untuk berkas dokumen "
           "mentah, volume `hf_cache` untuk model embedding, migrasi Alembic "
           "berjalan otomatis saat start (`alembic upgrade head` sebelum "
           "uvicorn), HEALTHCHECK untuk 3 service, dan variabel lingkungan "
           "terdokumentasi di `.env.example`. Bukti uji: redeploy (down lalu up "
           "--build) dan percakapan, dokumen, vektor, serta feedback lama tetap "
           "ada. Panduan deploy Coolify (compose dan Dockerfile tunggal) "
           "diverifikasi di server nyata, termasuk prosedur backup dan restore "
           "`pg_dump`."),
       workflow=(
           _w("Intern", "Ganti image postgres ke pgvector, tambah volume pgdata, uploads, hf_cache",
              "Semua state berada di volume"),
           _w("Intern", "Jalankan migrasi otomatis saat start + HEALTHCHECK 3 service",
              "Start idempoten"),
           _w("Intern", "Uji redeploy dan simpan buktinya di docs/DEPLOY.md",
              "Bukti persistensi"),
           _w("Intern", "Tulis dan uji skrip backup/restore pg_dump",
              "Pemulihan terbukti"),
       ),
       wireframe="""
services:
  postgres : pgvector/pgvector:pg16   volumes: [pgdata:/var/lib/postgresql/data]
  backend  : FastAPI                  volumes: [uploads:/app/uploads, hf_cache:/root/.cache/huggingface]
             command: alembic upgrade head && uvicorn ...
  frontend : Next.js standalone (port 3000)

redeploy: docker compose up -d --build   (BUKAN down -v)
cek     : sesi, dokumen, vektor, feedback lama masih ada
backup  : scripts/backup.sh  -> pg_dump -Fc -> backups/ai_assistant_YYYYMMDD.dump
""",
       acceptance=(
           "`docker compose up -d --build` membuat 3 service healthy dalam < 90 detik",
           "Setelah redeploy, sesi, dokumen, vektor, dan feedback lama tetap ada",
           "`docker compose down` lalu `up` tidak menghapus data (tanpa -v)",
           "0 state di layer image: seluruh path data berada di volume (diperiksa docker inspect)",
           "Migrasi otomatis berjalan idempoten pada start ke-2 dan backup/restore pg_dump teruji 1 kali"),
       evidence=(f"{P}/docker-compose.yml", f"{P}/docs/DEPLOY.md",
                 f"{P}/scripts/backup.sh"),
       depends_on=("INT-029", "INT-012"), source=_PRD),

    _t("INT-031", "Uji menyeluruh: unit, integrasi pipeline, dan e2e smoke",
       "i5", priority="high", estimate=1.5, labels=(*B, "epic-performa"),
       description=(
           "Kumpulkan pengujian menjadi satu perintah hijau per sisi, tanpa "
           "API key: backend `pytest backend/tests` (mock provider + embedder "
           "stub, PostgreSQL pgvector lewat service container) dan frontend "
           "`npm test` (vitest + React Testing Library). Minimal: unit test "
           "token counter, chunking, retrieval, guardrail, PII, validator, "
           "quota, cache, dan cost calculator; satu test integrasi pipeline "
           "penuh (pertanyaan -> guardrail -> router -> retrieval -> LLM mock "
           "-> validator -> trace + token_usage_logs -> SSE) yang memeriksa "
           "sitasi, trace, dan biaya; serta satu e2e smoke Playwright (login, "
           "unggah dokumen, tanya, klik sitasi, hapus dokumen). CI GitLab "
           "menjalankan keduanya di tiap merge request."),
       workflow=(
           _w("Intern", "Rapikan test yang sudah ada + tambah unit test yang kurang",
              "Satu perintah per sisi"),
           _w("Intern", "Tulis test integrasi pipeline penuh",
              "Jalur utama terlindungi"),
           _w("Intern", "Tulis e2e smoke Playwright dan pasang di CI GitLab",
              "Regresi UI terdeteksi"),
           _w("Pembimbing", "Jalankan di mesin bersih tanpa API key",
              "Hijau tanpa konfigurasi tambahan"),
       ),
       wireframe="""
pytest backend/tests -q
  test_token_counter ... test_ingest ... test_retrieval ... test_input_guardrail ...
  test_pii ... test_validators ... test_quota ... test_semantic_cache ... test_cost_calculator
  test_pipeline_integration.py::test_full_answer_has_citation_trace_and_cost
  120 passed in 74s    coverage application+domain: 78%

npm test            (vitest)        -> komponen: GraphView, ChartRenderer, CitationBadge, ...
npx playwright test (smoke e2e)     -> login, upload, tanya, klik sitasi, hapus dokumen
""",
       acceptance=(
           "`pytest backend/tests` hijau di mesin bersih tanpa API key apa pun",
           "Cakupan application + domain >= 70% (laporan pytest-cov dilampirkan)",
           "1 test integrasi pipeline penuh memeriksa sitasi, baris trace, dan biaya",
           "Seluruh test backend selesai < 120 detik",
           "E2E smoke Playwright (5 langkah) hijau dan dijalankan di CI GitLab pada tiap merge request"),
       evidence=(f"{TESTS}/test_pipeline_integration.py",
                 f"{FE}/e2e/smoke.spec.ts", f"{P}/.gitlab-ci.yml",
                 f"{P}/docs/TESTING.md"),
       depends_on=("INT-030",), source=_DOD),

    _t("INT-032", "Dokumentasi, runbook, demo 10 menit, dan metrik nyata vs target PRD",
       "i5", priority="critical", estimate=1.5, labels=(*_L, "docs", "epic-performa"),
       description=(
           "Penutup magang. Lengkapi README (arsitektur 7 tahap, cara jalan, "
           "env, batasan yang diketahui), tulis runbook singkat (menambah "
           "dokumen, mengganti provider, membaca trace, mengatasi 5 masalah "
           "tersering, backup dan restore PostgreSQL), dan susun skrip demo 10 "
           "menit yang menunjukkan kelima epic serta 10 user story PRD secara "
           "berurutan. Tutup dengan tabel 5 metrik PRD bagian B (tergrounding, "
           "p95 TTFT, rasio suka, biaya per percakapan, cache hit-rate) berisi "
           "angka nyata vs target — diisi apa adanya, termasuk yang meleset, "
           "beserta penyebab dan rencana perbaikannya. Finalisasi PRD: status "
           "Approved dan bagian D (rencana rilis) diperbarui."),
       workflow=(
           _w("Intern", "Lengkapi README + runbook",
              "Orang baru bisa melanjutkan proyek"),
           _w("Intern", "Susun skrip demo 10 menit per epic dan per user story",
              "docs/DEMO.md"),
           _w("Intern", "Ukur ulang 5 metrik PRD dan isi tabel nyata vs target",
              "Hasil jujur tercatat di docs/METRICS.md"),
           _w("Pembimbing", "Tonton demo, review dokumen, dan setujui PRD final",
              "Serah terima selesai"),
       ),
       wireframe="""
SKRIP DEMO (10 menit)
 0:00 masalah & produk (PRD A)                      1 mnt
 1:00 login, chat, sesi lama dilanjutkan             1,5 mnt  (Epic 1)  US-04
 2:30 unggah PDF/DOCX/MD, tanya + sitasi             2 mnt    (Epic 2)  US-01,02,03,05,08
 4:30 flowchart, GraphView, bar chart                1,5 mnt  (Epic 2)  US-06,07
 6:00 injection + PII ditolak/disensor               1 mnt    (Epic 3)
 7:00 trace waterfall + dasbor biaya + feedback      1,5 mnt  (Epic 4)  US-09
 8:30 cache hit, matikan provider utama, hapus doc   1 mnt    (Epic 5)  US-10
 9:30 metrik nyata vs target                         0,5 mnt

METRIK  | target        | nyata | catatan
""",
       acceptance=(
           "README memuat arsitektur 7 tahap, setup, env, dan batasan yang diketahui",
           "Runbook memuat 5 masalah tersering beserta langkah penanganannya",
           "Skrip demo mencakup 5 epic dan 10 user story dan selesai <= 10 menit saat dilatih",
           "Tabel 5 metrik PRD bagian B terisi angka nyata vs target, termasuk yang meleset",
           "PRD berstatus Approved dan semua task papan berstatus akhir yang benar saat serah terima"),
       evidence=(f"{P}/README.md", f"{P}/docs/RUNBOOK.md", f"{P}/docs/DEMO.md",
                 f"{P}/docs/METRICS.md"),
       depends_on=("INT-031", "INT-026"), source=_DOD),
]


def _assign_default_owner() -> None:
    """Isi `assignee` yang belum di-set dengan intern pertama."""
    for index, task in enumerate(TASKS):
        if not task.get("assignee"):
            task["assignee"] = INTERNS[index % len(INTERNS)]


_assign_default_owner()


def for_assignee(assignee: str) -> list[dict[str, Any]]:
    """Task milik satu orang (dipakai halaman /internship untuk member)."""
    name = (assignee or "").strip().lower()
    return [t for t in TASKS if (t.get("assignee") or "").lower() == name]


def by_phase(phase: str) -> list[dict[str, Any]]:
    """Task satu sprint (dipakai panduan & test)."""
    return [t for t in TASKS if t["phase"] == phase]


def summary() -> dict[str, Any]:
    """Ringkasan rencana intern (dipakai test, API, dan halaman /internship)."""
    per_phase: dict[str, int] = {p["id"]: 0 for p in PHASES}
    per_priority: dict[str, int] = {p: 0 for p in PRIORITIES}
    per_assignee: dict[str, int] = {}
    per_label: dict[str, int] = {}
    per_status: dict[str, int] = {s: 0 for s in STATUSES}
    days = 0.0
    for t in TASKS:
        per_phase[t["phase"]] = per_phase.get(t["phase"], 0) + 1
        per_priority[t["priority"]] = per_priority.get(t["priority"], 0) + 1
        per_status[t["status"]] = per_status.get(t["status"], 0) + 1
        days += float(t["estimate"] or 0)
        if t.get("assignee"):
            per_assignee[t["assignee"]] = per_assignee.get(t["assignee"], 0) + 1
        for label in t.get("labels", []):
            per_label[label] = per_label.get(label, 0) + 1
    return {
        "track": TRACK,
        "project_dir": PROJECT_DIR,
        "revision": PLAN_REVISION,
        "phases": PHASES,
        "epics": EPICS,
        "total": len(TASKS),
        "per_phase": per_phase,
        "per_priority": per_priority,
        "per_assignee": per_assignee,
        "per_label": per_label,
        "per_status": per_status,
        "estimate_days": round(days, 1),
        "statuses": list(STATUSES),
        "status_labels": dict(STATUS_LABELS),
    }
