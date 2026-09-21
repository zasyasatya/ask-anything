"""Rencana proyek internship — **Chatbot LLM (AI agent) prototipe, fokus LLM**.

Papan ini terpisah dari rencana platform (`tasks_plan.py`, id `ASK-NNN`): id di
sini memakai prefix `INT-NNN` dan halaman-nya `/internship`.

Sasaran papan
-------------
Satu **prototipe chatbot LLM** yang bisa dipakai dan didemokan, dengan lima
kemampuan inti (dipetakan dari lima epic): manajemen konteks & memori,
orkestrasi & tooling, guardrail, observability, dan performa. Yang dinilai
adalah kualitas lapisan LLM-nya — bukan kerumitan infrastruktur.

Batasan arsitektur (sudah dikunci, intern tidak perlu memilih)
--------------------------------------------------------------
* **Python saja**: UI prototipe pakai **Streamlit** (`app.py`), logika di modul
  `core/*.py`. Tidak ada Next.js/React, tidak ada microservice.
* **SQLite** (stdlib `sqlite3`) untuk sesi, pesan, memori, trace, cache, kuota.
  Tidak ada PostgreSQL/Redis/Milvus/Qdrant/Kafka/RabbitMQ.
* **Vector store = file numpy + cosine similarity**, bukan vector DB.
* **Tracing sendiri** (tabel `traces` + halaman Streamlit), bukan LangSmith /
  Datadog / Phoenix.
* Provider LLM = satu endpoint OpenAI-compatible + **mock provider offline**
  supaya semua fitur tetap bisa diuji tanpa kuota API.

Urutan kerja
------------
Papan dibagi menjadi **6 sprint** (satu sprint ≈ 1 minggu kerja). Hanya task
**Sprint 0** yang berstatus `todo`; sprint berikutnya duduk di `backlog` dan
baru ditarik saat sprintnya dibuka — supaya kolom To do tidak memanjang.
Gerbang Sprint 0: **PRD rampung dan disetujui pembimbing** sebelum satu baris
kode fitur ditulis.

Tiap task ditulis agar bisa dikerjakan tanpa bertanya lagi:

  * ``description`` — konteks + keputusan teknis yang sudah ditetapkan,
  * ``workflow``    — alur kerja bernomor ``{actor, action, result}``,
  * ``wireframe``   — sketsa layout / bentuk data (ASCII),
  * ``acceptance``  — kriteria selesai yang **berangka** dan bisa diuji,
  * ``evidence``    — berkas yang harus ada (diperiksa ``POST /api/tasks/sync``),
  * ``depends_on``  — prasyarat, supaya urutan pengerjaan jelas.

Konvensi id dipakai apa adanya di nama branch git (``feat/INT-007-…``).
"""
from __future__ import annotations

from typing import Any

from .tasks_plan import PRIORITIES, STATUSES, STATUS_LABELS  # noqa: F401  (re-export)

#: Penanda papan (dipakai filter `/api/tasks?track=internship`).
TRACK = "internship"

#: Versi rencana. Naikkan setiap kali daftar TASKS berubah supaya papan yang
#: sudah ter-seed di deployment lama ikut diperbarui (`tasks.sync_plan_revision`)
#: tanpa menghapus progres (status/assignee/checklist dibawa pindah).
PLAN_REVISION = "2026-09-21-sprint-llm-1"

#: Folder proyek yang dibangun intern di dalam repo ini.
PROJECT_DIR = "projects/ai-agent"

#: Sprint = kolom "fase" di papan. Id `i0..i5` dipertahankan (dipakai data lama
#: & nama branch), namanya yang berbicara sebagai sprint.
PHASES: list[dict[str, str]] = [
    {"id": "i0", "name": "Sprint 0 — PRD & Kerangka",
     "subtitle": "Gerbang: PRD disetujui. Repo, skeleton Streamlit, mock LLM."},
    {"id": "i1", "name": "Sprint 1 — Chat, Sesi & Token",
     "subtitle": "Epic 1: sesi percakapan, hitung token, sliding window, ringkasan."},
    {"id": "i2", "name": "Sprint 2 — RAG, Tool & Router",
     "subtitle": "Epic 2: retrieval, function calling, router hemat biaya, memori panjang."},
    {"id": "i3", "name": "Sprint 3 — Guardrail",
     "subtitle": "Epic 3: moderasi input, redaksi PII, validasi output terstruktur."},
    {"id": "i4", "name": "Sprint 4 — Observability",
     "subtitle": "Epic 4: tracing, dasbor biaya & latensi, feedback loop, evaluasi."},
    {"id": "i5", "name": "Sprint 5 — Performa & Rilis",
     "subtitle": "Epic 5: semantic cache, rate limit, fallback model, deploy & demo."},
]

PHASE_IDS = tuple(p["id"] for p in PHASES)

#: Label sprint (dipakai filter label di UI, sejajar dengan `phase`).
SPRINT_LABELS: dict[str, str] = {
    "i0": "sprint-0", "i1": "sprint-1", "i2": "sprint-2",
    "i3": "sprint-3", "i4": "sprint-4", "i5": "sprint-5",
}

#: Label epic — persis lima epic yang diminta pembimbing.
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

#: Berkas referensi di **ask-anything** yang boleh dibaca sebagai contoh pola
#: (bukan untuk disalin: proyek intern ditulis sendiri, jauh lebih sederhana).
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
       source: str = "", status: str = "", assignee: str = "") -> dict[str, Any]:
    """Buat satu task.

    `status` kosong → otomatis: Sprint 0 = `todo` (dikerjakan sekarang),
    sprint lain = `backlog` (belum dibuka). Label sprint ikut ditambahkan.
    """
    sprint_label = SPRINT_LABELS.get(phase, "")
    all_labels = list(labels)
    if sprint_label and sprint_label not in all_labels:
        all_labels.append(sprint_label)
    return {
        "id": task_id, "title": title, "phase": phase, "priority": priority,
        "estimate": estimate, "labels": all_labels,
        "description": description.strip(),
        "workflow": [dict(step) for step in workflow],
        "wireframe": wireframe.strip("\n"),
        "acceptance": list(acceptance),
        "evidence": list(evidence), "depends_on": list(depends_on),
        "source": source,
        "status": status or ("todo" if phase == "i0" else "backlog"),
        "assignee": assignee,
    }


_L = ("internship",)
B = (*_L, "backend")
F = (*_L, "ui")

#: Akun intern yang mengerjakan papan ini (username login).
INTERNS: tuple[str, ...] = ("verisimb",)

P = PROJECT_DIR

TASKS: list[dict[str, Any]] = [
    # ================================================================ Sprint 0
    _t("INT-001", "PRD bagian A: masalah, persona, user story, non-goals",
       "i0", priority="critical", estimate=1.5,
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
       evidence=(f"{_DOC}/01-template-prd.md", f"{P}/docs/PRD.md"),
       source=_PRD),

    _t("INT-002", "PRD bagian B: metrik sukses, anggaran token & biaya",
       "i0", priority="critical", estimate=1,
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
       evidence=(f"{P}/docs/PRD.md",), depends_on=("INT-001",), source=_PRD),

    _t("INT-003", "PRD bagian C: arsitektur prototipe + 5 ADR singkat",
       "i0", priority="critical", estimate=1,
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
       evidence=(f"{P}/docs/PRD.md", f"{P}/docs/ADR.md"),
       depends_on=("INT-002",), source=_ARCH),

    _t("INT-004", "Kerangka proyek: repo, Streamlit 'hello chat', mock provider",
       "i0", priority="high", estimate=1.5, labels=(*B, "epic-prd"),
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
       evidence=(f"{P}/README.md", f"{P}/requirements.txt", f"{P}/app.py",
                 f"{P}/core/db.py", f"{P}/tests/test_smoke.py"),
       depends_on=("INT-003",), source=_ARCH),

    # ================================================================ Sprint 1
    _t("INT-005", "Provider LLM: OpenAI-compatible + mock, streaming & retry",
       "i1", priority="critical", estimate=1.5, labels=(*B, "epic-konteks", "llm"),
       description=(
           "Satu antarmuka `LLMProvider.stream(messages, **params) -> Iterator[str]` "
           "dengan dua implementasi: `OpenAICompatProvider` (SDK openai, "
           "base_url bisa diarahkan ke gateway atau server lokal) dan "
           "`MockProvider` (jawaban deterministik untuk test & demo offline). "
           "Provider menangani timeout (30 detik), retry 2x dengan backoff "
           "eksponensial pada error 429/5xx, dan mengembalikan metadata "
           "pemakaian token (prompt, completion) supaya biaya bisa dihitung di "
           "task INT-021. Pemilihan provider lewat env, bukan hardcode."),
       workflow=(
           _w("Intern", "Definisikan protokol LLMProvider + dataclass hasil",
              "core/providers.py"),
           _w("Intern", "Implementasi mock + OpenAI-compatible streaming",
              "Dua provider lulus test yang sama"),
           _w("Intern", "Tambahkan timeout, retry, dan pengukuran TTFT",
              "Error sementara tidak menjatuhkan UI"),
           _w("Pembimbing", "Uji dengan API key nyata dan tanpa key",
              "Keduanya jalan"),
       ),
       wireframe="""
LLMProvider
  .stream(messages, temperature, max_tokens) -> yields token
  .last_usage -> {prompt_tokens, completion_tokens, ttft_ms, model}

env: AGENT_PROVIDER=mock|openai
     AGENT_BASE_URL, AGENT_API_KEY, AGENT_MODEL
retry: 429/5xx -> tunggu 1s, 2s (maks 2x) -> error rapi ke UI
""",
       acceptance=(
           "Kedua provider lulus satu set test kontrak yang sama",
           "Streaming mengeluarkan token bertahap (bukan sekali kirim di akhir)",
           "Timeout 30s dan retry 2x terbukti lewat test yang memalsukan error 429",
           "`last_usage` mengisi prompt_tokens, completion_tokens, dan ttft_ms",
           "Ganti provider cukup lewat env tanpa ubah kode"),
       evidence=(f"{P}/core/providers.py", f"{P}/tests/test_providers.py"),
       depends_on=("INT-004",), source=_ARCH),

    _t("INT-006", "UI chat streaming: bubble, status, dan penanganan error",
       "i1", priority="high", estimate=1.5, labels=(*F, "epic-konteks"),
       description=(
           "Halaman chat Streamlit yang layak dipakai: `st.chat_message` untuk "
           "bubble pengguna/asisten, `st.write_stream` supaya jawaban muncul "
           "bertahap, indikator status ('mengambil dokumen…', 'memanggil "
           "tool…') yang dibaca dari event pipeline, tombol Stop untuk "
           "menghentikan generasi, dan pesan error yang ramah (bukan "
           "traceback) saat provider gagal. Sertakan tampilan kosong (empty "
           "state) berisi 3 contoh pertanyaan yang bisa diklik."),
       workflow=(
           _w("Intern", "Bangun layout chat + state percakapan di st.session_state",
              "Chat dua arah berjalan"),
           _w("Intern", "Sambungkan streaming provider ke st.write_stream",
              "Token muncul bertahap"),
           _w("Intern", "Tambah status pipeline, tombol Stop, dan error handling",
              "UI tidak pernah menampilkan traceback"),
           _w("Pembimbing", "Coba 5 skenario termasuk provider mati",
              "Semua skenario tertangani"),
       ),
       wireframe="""
+--------------------------------------------------------------+
| [sidebar]            |  👤 Apa kebijakan cuti tahunan?         |
|  + Percakapan baru   |  🤖 ▌(streaming...)                     |
|  - Cuti tahunan      |     status: mengambil dokumen (2)      |
|  - Reimburse         |                                        |
|                      |  [ Stop ]                              |
+----------------------+----------------------------------------+
| empty state: [Cuti?] [Reimburse?] [Jam kerja?]                |
| [ ketik ............................................ ] [Kirim]|
+--------------------------------------------------------------+
""",
       acceptance=(
           "Jawaban tampil bertahap, bukan sekali muncul di akhir",
           "Tombol Stop menghentikan generasi dalam <= 1 detik",
           "Provider error menampilkan pesan ramah + tombol coba lagi, tanpa traceback",
           "Empty state punya 3 contoh pertanyaan yang bisa diklik",
           "Status pipeline berubah sesuai tahap (retrieval/tool/generasi)"),
       evidence=(f"{P}/app.py", f"{P}/core/ui_chat.py"),
       depends_on=("INT-005",), source=_ARCH),

    _t("INT-007", "Sesi percakapan: CRUD thread di SQLite + lanjut percakapan",
       "i1", priority="critical", estimate=1.5, labels=(*B, "epic-konteks"),
       description=(
           "Epic 1 — Session Management. Tabel `sessions(id, user, title, "
           "created_at, updated_at)` dan `messages(id, session_id, role, "
           "content, tokens, created_at)` di SQLite, plus fungsi "
           "`create/list/get/rename/delete` di `core/session.py`. Judul thread "
           "dibuat otomatis dari 6 kata pertama pertanyaan pertama. Sidebar UI "
           "menampilkan daftar thread terbaru, tombol ganti nama & hapus "
           "(dengan konfirmasi), dan membuka thread lama akan memuat kembali "
           "seluruh riwayatnya sehingga percakapan benar-benar bisa dilanjutkan "
           "setelah aplikasi ditutup."),
       workflow=(
           _w("Intern", "Buat skema tabel + migrasi ringan (CREATE IF NOT EXISTS)",
              "core/db.py berisi skema"),
           _w("Intern", "Implementasi CRUD sesi & pesan + judul otomatis",
              "core/session.py + test"),
           _w("Intern", "Sambungkan sidebar Streamlit ke CRUD",
              "Thread bisa dibuat/dibuka/ganti nama/dihapus"),
           _w("Intern", "Uji restart aplikasi: riwayat harus kembali utuh",
              "Persistensi terbukti"),
       ),
       wireframe="""
sessions(id TEXT PK, user TEXT, title TEXT, created_at, updated_at)
messages(id TEXT PK, session_id TEXT, role TEXT, content TEXT,
         tokens INT, created_at)

SIDEBAR
 [+ Percakapan baru]
 • Kebijakan cuti tahunan      ...  [✎] [🗑]
 • Klaim reimburse             ...  [✎] [🗑]
""",
       acceptance=(
           "Buat, buka, ganti nama, dan hapus thread bekerja dari UI",
           "Judul otomatis terisi dari pertanyaan pertama (maks 6 kata)",
           "Tutup lalu buka aplikasi: seluruh riwayat thread kembali utuh",
           "Hapus thread meminta konfirmasi dan ikut menghapus pesannya",
           "Test CRUD sesi hijau (minimal 5 kasus)"),
       evidence=(f"{P}/core/session.py", f"{P}/tests/test_session.py"),
       depends_on=("INT-004",), source=_ARCH),

    _t("INT-008", "Hitung token real-time + indikator pemakaian context window",
       "i1", priority="high", estimate=1, labels=(*B, "epic-konteks", "llm"),
       description=(
           "Epic 1 — Token Limiter. Modul `core/tokens.py` memakai `tiktoken` "
           "(encoding `cl100k_base`) untuk menghitung token pesan, dengan "
           "fallback perkiraan `len(teks)/4` bila encoding tidak tersedia "
           "offline. Hitung token system prompt, riwayat, konteks RAG, dan "
           "draf pertanyaan yang sedang diketik; tampilkan di UI sebagai "
           "'3.120 / 8.000 token' dengan bar warna (hijau <70%, kuning 70-90%, "
           "merah >90%). Setiap pesan yang disimpan mencatat jumlah tokennya "
           "supaya analitik biaya di Sprint 4 tidak perlu menghitung ulang."),
       workflow=(
           _w("Intern", "Bungkus tiktoken + fallback perkiraan",
              "core/tokens.py"),
           _w("Intern", "Hitung token per bagian prompt (system/riwayat/konteks)",
              "Fungsi breakdown token"),
           _w("Intern", "Tampilkan indikator + bar di UI",
              "Pengguna tahu sisa ruang konteks"),
           _w("Intern", "Simpan kolom tokens tiap pesan",
              "Data siap dipakai dasbor biaya"),
       ),
       wireframe="""
count_tokens(text, model) -> int
breakdown(session) -> {system, history, context, draft, total, limit}

UI (di atas composer)
  [■■■■■■□□□□] 3.120 / 8.000 token  •  sisa ~4.880
""",
       acceptance=(
           "Selisih hitungan terhadap usage provider <= 5% pada 10 contoh uji",
           "Fallback jalan tanpa internet (tiktoken gagal diunduh) tanpa crash",
           "Indikator berubah warna pada ambang 70% dan 90%",
           "Kolom `tokens` terisi untuk setiap pesan tersimpan",
           "Test hitung token hijau untuk teks ASCII dan non-ASCII"),
       evidence=(f"{P}/core/tokens.py", f"{P}/tests/test_tokens.py"),
       depends_on=("INT-007",), source=_ARCH),

    _t("INT-009", "Sliding window + ringkasan otomatis riwayat lama",
       "i1", priority="critical", estimate=1.5, labels=(*B, "epic-konteks", "llm"),
       description=(
           "Epic 1 — Truncation. `core/context.py` menyusun prompt akhir dengan "
           "anggaran tetap: system prompt + ringkasan + N pesan terbaru + "
           "konteks RAG <= 8.000 token, menyisakan 1.024 token untuk jawaban. "
           "Saat riwayat melewati 70% anggaran, pesan terlama dipangkas dan "
           "diringkas satu kali oleh LLM (maks 200 token) menjadi memori "
           "jangka menengah yang disimpan di kolom `sessions.summary`; "
           "ringkasan lama digabung dengan ringkasan baru, bukan ditumpuk. "
           "Pesan yang dipangkas tetap tersimpan di DB (hanya tidak dikirim)."),
       workflow=(
           _w("Intern", "Tulis algoritma anggaran token + pemilihan pesan",
              "core/context.py"),
           _w("Intern", "Tambah peringkas otomatis saat ambang 70% tercapai",
              "sessions.summary terisi"),
           _w("Intern", "Tandai di UI bahwa riwayat lama sudah diringkas",
              "Pengguna paham konteks dipangkas"),
           _w("Intern", "Uji percakapan 40 pesan: tidak pernah melebihi batas",
              "Test panjang hijau"),
       ),
       wireframe="""
ANGGARAN 8.000 token
 [system 300][ringkasan <=200][konteks RAG <=2.500][riwayat sisa][jawaban 1.024]

 riwayat > 70%?  -> ambil 6 pesan terlama -> LLM ringkas (<=200 tok)
                 -> gabung ke sessions.summary -> buang dari prompt
UI: "ℹ️ 12 pesan lama diringkas untuk menghemat konteks"
""",
       acceptance=(
           "Percakapan 40 pesan tidak pernah mengirim prompt > 8.000 token",
           "Ringkasan terbentuk otomatis saat ambang 70% terlampaui",
           "Ringkasan baru menggabungkan ringkasan lama (tidak beranak-pinak)",
           "Pesan yang dipangkas tetap ada di DB dan tetap tampil di UI",
           "UI memberi tahu bahwa riwayat lama telah diringkas"),
       evidence=(f"{P}/core/context.py", f"{P}/tests/test_context.py"),
       depends_on=("INT-008",), source=_ARCH),

    # ================================================================ Sprint 2
    _t("INT-010", "Ingest dokumen: loader + chunking + status pemrosesan",
       "i2", priority="critical", estimate=1.5, labels=(*B, "epic-tooling", "rag"),
       description=(
           "Epic 2 — RAG bagian 1. Halaman 'Pengetahuan' untuk mengunggah PDF, "
           "TXT, dan Markdown (maks 10 MB per berkas). `core/ingest.py` "
           "mengekstrak teks (pypdf untuk PDF), membersihkan header/footer "
           "berulang, lalu memotong menjadi chunk ~500 token dengan overlap 50 "
           "token yang tidak memutus kalimat. Tiap chunk menyimpan metadata "
           "`{doc_id, judul, halaman, urutan}` supaya sitasi bisa menunjuk "
           "halaman. Status pemrosesan (antre → ekstraksi → chunking → "
           "embedding → siap) tampil per dokumen, termasuk pesan gagal yang "
           "jelas bila PDF berupa hasil scan tanpa teks."),
       workflow=(
           _w("Intern", "Buat halaman upload + validasi tipe/ukuran berkas",
              "Dokumen masuk folder data/docs"),
           _w("Intern", "Implementasi ekstraksi teks + pembersihan",
              "Teks bersih per halaman"),
           _w("Intern", "Implementasi chunking 500/50 sadar kalimat",
              "Tabel chunks terisi"),
           _w("Intern", "Tampilkan status & error per dokumen",
              "Pengguna tahu dokumen siap atau gagal"),
       ),
       wireframe="""
HALAMAN PENGETAHUAN
+--------------------------------------------------------------+
| [ Unggah PDF/TXT/MD ]   maks 10 MB                            |
+---------------------+----------+----------+------------------+
| Dokumen             | Halaman  | Chunk    | Status           |
+---------------------+----------+----------+------------------+
| kebijakan-cuti.pdf  |    12    |    41    | ✅ siap           |
| sop-reimburse.pdf   |     8    |     0    | ⏳ embedding      |
| scan-lama.pdf       |     5    |     0    | ❌ tanpa teks     |
+---------------------+----------+----------+------------------+
""",
       acceptance=(
           "PDF, TXT, dan MD bisa diunggah; tipe lain ditolak dengan pesan jelas",
           "Chunk rata-rata 400-600 token dengan overlap 50 token",
           "Setiap chunk menyimpan doc_id, judul, halaman, dan urutan",
           "PDF hasil scan tanpa teks ditandai gagal, bukan menghasilkan chunk kosong",
           "Status per dokumen berubah sampai 'siap' tanpa perlu refresh manual"),
       evidence=(f"{P}/core/ingest.py", f"{P}/tests/test_ingest.py"),
       depends_on=("INT-004",), source=_ARCH),

    _t("INT-011", "Embedding + indeks numpy + retrieval top-k berambang",
       "i2", priority="critical", estimate=1.5, labels=(*B, "epic-tooling", "rag"),
       description=(
           "Epic 2 — RAG bagian 2 (pengganti vector DB, cukup numpy). "
           "`core/embed.py` membuat vektor dengan `sentence-transformers "
           "all-MiniLM-L6-v2` (unduh sekali, jalan offline) dan menyimpannya "
           "sebagai `data/index.npy` + peta id di SQLite; bila model tidak bisa "
           "dimuat, fallback ke TF-IDF scikit-learn agar demo tetap jalan. "
           "`search(query, k=5, min_score=0.35)` memakai cosine similarity "
           "ternormalisasi dan membuang hasil di bawah ambang supaya jawaban "
           "tidak mengarang dari potongan tak relevan. Re-embed ulang hanya "
           "untuk dokumen baru/berubah, bukan seluruh indeks."),
       workflow=(
           _w("Intern", "Muat model embedding + simpan vektor ke index.npy",
              "Indeks terbentuk"),
           _w("Intern", "Implementasi cosine search + ambang skor",
              "core/rag.py search()"),
           _w("Intern", "Tambah fallback TF-IDF bila model gagal dimuat",
              "Demo tetap jalan offline"),
           _w("Intern", "Ukur waktu pencarian pada 1.000 chunk",
              "Angka latensi tercatat di README"),
       ),
       wireframe="""
index.npy  -> matrix (n_chunk, 384) float32, sudah dinormalisasi
chunk_map  -> SQLite: row_id <-> chunk_id

search(q, k=5, min_score=0.35):
   qv = embed(q)           # (384,)
   skor = index @ qv       # cosine karena sudah dinormalisasi
   ambil k tertinggi, buang skor < 0.35
   -> [{chunk_id, skor, judul, halaman, teks}]
""",
       acceptance=(
           "Pencarian pada 1.000 chunk selesai < 200 ms (dicatat di README)",
           "Hasil di bawah skor 0.35 tidak pernah ikut ke prompt",
           "Fallback TF-IDF terbukti jalan saat model embedding dinonaktifkan",
           "Menambah 1 dokumen tidak memicu re-embed seluruh indeks",
           "Test retrieval memastikan dokumen relevan masuk 3 besar untuk 5 query uji"),
       evidence=(f"{P}/core/embed.py", f"{P}/core/rag.py",
                 f"{P}/tests/test_rag.py"),
       depends_on=("INT-010",), source=_ARCH),

    _t("INT-012", "Jawaban tergrounding + sitasi yang bisa diklik",
       "i2", priority="critical", estimate=1.5, labels=(*B, *F, "epic-tooling", "rag"),
       description=(
           "Epic 2 — RAG bagian 3. Prompt RAG menyusun konteks sebagai daftar "
           "bernomor `[1] judul — hal. X` (maks 2.500 token) dan mewajibkan "
           "model menulis sitasi `[n]` pada tiap klaim faktual serta menjawab "
           "'informasi tidak ada di dokumen' bila konteks tidak memuat "
           "jawabannya. Setelah jawaban selesai, verifikasi bahwa setiap nomor "
           "sitasi benar-benar ada di konteks (sitasi halu dibuang) dan "
           "tampilkan panel sumber yang bisa diklik untuk membuka kutipan "
           "aslinya di UI."),
       workflow=(
           _w("Intern", "Susun template prompt RAG + aturan sitasi",
              "core/prompts.py"),
           _w("Intern", "Verifikasi nomor sitasi terhadap konteks",
              "Sitasi halu dibuang"),
           _w("Intern", "Bangun panel sumber yang bisa dibuka",
              "Pengguna bisa cek kutipan asli"),
           _w("Intern", "Uji 10 pertanyaan: 8 harus tergrounding",
              "Angka tercatat untuk metrik PRD"),
       ),
       wireframe="""
KONTEKS -> PROMPT
 [1] kebijakan-cuti.pdf — hal. 3 : "Cuti tahunan 12 hari..."
 [2] sop-reimburse.pdf  — hal. 1 : "Klaim maksimal 30 hari..."

JAWABAN
 Cuti tahunan 12 hari kerja per tahun [1]. Klaim ... [2].
 ┌ Sumber ───────────────────────────────┐
 │ [1] kebijakan-cuti.pdf hal.3  (buka)  │
 │ [2] sop-reimburse.pdf hal.1   (buka)  │
 └───────────────────────────────────────┘
""",
       acceptance=(
           ">= 8 dari 10 pertanyaan uji dijawab dengan minimal satu sitasi valid",
           "Pertanyaan di luar dokumen dijawab 'tidak ada di dokumen', bukan dikarang",
           "Nomor sitasi yang tidak ada di konteks dibuang sebelum tampil",
           "Panel sumber menampilkan judul + halaman dan bisa dibuka",
           "Konteks RAG tidak pernah melebihi 2.500 token"),
       evidence=(f"{P}/core/prompts.py", f"{P}/tests/test_grounding.py"),
       depends_on=("INT-011", "INT-009"), source=_ARCH),

    _t("INT-013", "Tool registry (function calling) + eksekusi aman",
       "i2", priority="critical", estimate=2, labels=(*B, "epic-tooling", "llm"),
       description=(
           "Epic 2 — Function Calling Registry. `core/tools.py` menyediakan "
           "dekorator `@tool` yang mendaftarkan nama, deskripsi, dan JSON "
           "schema parameter (dibangun dari model pydantic) ke satu registry, "
           "lalu mengekspornya ke format `tools=[...]` milik API "
           "OpenAI-compatible. Sediakan 3 tool: `cari_dokumen(query, k)` "
           "(membungkus retrieval), `kalkulator(ekspresi)` (parser aman lewat "
           "`ast`, bukan `eval`), dan `waktu_sekarang(zona)`. Loop agent "
           "menjalankan maksimal 3 iterasi tool, memvalidasi argumen terhadap "
           "schema, dan menolak nama tool di luar registry."),
       workflow=(
           _w("Intern", "Bangun dekorator @tool + generator JSON schema",
              "Registry berisi 3 tool"),
           _w("Intern", "Implementasi loop panggil-tool maks 3 iterasi",
              "core/agent.py"),
           _w("Intern", "Validasi argumen + tolak tool tak dikenal",
              "Panggilan liar gagal rapi"),
           _w("Intern", "Tampilkan jejak pemanggilan tool di UI",
              "Pengguna melihat tool apa yang dipakai"),
       ),
       wireframe="""
@tool("kalkulator", "Hitung ekspresi aritmatika")
def kalkulator(ekspresi: str) -> str: ...

registry.schemas() -> [{"type":"function","function":{...json schema...}}]

LOOP (maks 3 iterasi)
 model -> tool_call(nama, args) -> validasi schema -> jalankan
        -> hasil dikembalikan sebagai pesan role=tool -> model lanjut
 iterasi ke-4 -> berhenti, jawab dengan info seadanya
""",
       acceptance=(
           "3 tool terdaftar dan schema-nya lolos validasi JSON schema",
           "Kalkulator memakai parser ast; `__import__` atau kode arbitrer ditolak",
           "Argumen tidak sesuai schema ditolak dengan pesan ke model, bukan crash",
           "Loop berhenti di iterasi ke-3 dan tetap memberi jawaban",
           "UI menampilkan urutan tool yang dipanggil beserta durasinya"),
       evidence=(f"{P}/core/tools.py", f"{P}/core/agent.py",
                 f"{P}/tests/test_tools.py"),
       depends_on=("INT-011",), source=_ARCH),

    _t("INT-014", "Router / intent classifier: langsung, RAG, atau tool",
       "i2", priority="high", estimate=1.5, labels=(*B, "epic-tooling", "llm"),
       description=(
           "Epic 2 — Router. `core/router.py` memutuskan rute tiap pertanyaan: "
           "`smalltalk` (jawab langsung tanpa retrieval), `dokumen` (jalankan "
           "RAG), atau `tool` (butuh hitung/waktu). Tahap pertama aturan murah "
           "(sapaan, pertanyaan aritmatika, kata kunci domain); bila ragu, "
           "panggil LLM kecil sekali dengan output JSON `{rute, alasan, "
           "keyakinan}`. Tujuannya menghemat biaya: pertanyaan sapaan tidak "
           "boleh memicu embedding + retrieval. Catat rute terpilih ke trace "
           "supaya bisa dievaluasi, dan sediakan mode paksa (override) di UI "
           "untuk pengujian."),
       workflow=(
           _w("Intern", "Kumpulkan 30 contoh pertanyaan berlabel rute",
              "Berkas data uji router"),
           _w("Intern", "Implementasi aturan murah + fallback LLM klasifikasi",
              "core/router.py"),
           _w("Intern", "Ukur akurasi terhadap 30 contoh",
              "Angka akurasi tercatat"),
           _w("Intern", "Sambungkan ke pipeline + catat rute di trace",
              "Rute terlihat di trace viewer"),
       ),
       wireframe="""
route(q) -> {"rute": "smalltalk|dokumen|tool", "alasan": "...", "keyakinan": 0.0-1.0}

 aturan murah  : "halo/terima kasih"        -> smalltalk
                 regex angka+operator       -> tool
                 kata domain (cuti, sop...) -> dokumen
 ragu (<0.6)   : 1x panggilan LLM klasifikasi (JSON)

UI: [rute: dokumen ▾ (paksa: langsung / dokumen / tool)]
""",
       acceptance=(
           "Akurasi router >= 80% pada 30 contoh berlabel",
           ">= 90% pertanyaan smalltalk tidak memicu retrieval sama sekali",
           "Rute, alasan, dan keyakinan tercatat di trace tiap permintaan",
           "Override rute dari UI bekerja untuk pengujian",
           "Biaya rata-rata per pertanyaan smalltalk turun terhadap baseline (angka dicatat)"),
       evidence=(f"{P}/core/router.py", f"{P}/tests/test_router.py"),
       depends_on=("INT-013", "INT-012"), source=_ARCH),

    _t("INT-015", "Memori jangka panjang: fakta & preferensi pengguna",
       "i2", priority="high", estimate=1.5, labels=(*B, "epic-konteks", "llm"),
       description=(
           "Epic 1 — Semantic Memory, versi sederhana tanpa vector DB terpisah. "
           "Setelah percakapan selesai (atau tiap 10 pesan), LLM mengekstrak "
           "maksimal 5 fakta stabil tentang pengguna (jabatan, divisi, "
           "preferensi bahasa/format jawaban) ke tabel `memories(id, user, "
           "kind, text, embedding, created_at)`. Saat percakapan baru dimulai, "
           "ambil 3 memori paling mirip dengan pertanyaan (cosine, ambang "
           "0.35) dan sisipkan ke system prompt maksimal 300 token. Memori "
           "bisa dilihat, diedit, dan dihapus pengguna di halaman Memori — "
           "ingatan yang tidak bisa dihapus adalah cacat privasi, bukan fitur."),
       workflow=(
           _w("Intern", "Buat tabel memories + ekstraksi fakta via LLM",
              "Memori terisi otomatis"),
           _w("Intern", "Ambil memori relevan secara semantik saat menyusun prompt",
              "Prompt memuat memori terpilih"),
           _w("Intern", "Bangun halaman Memori (lihat/edit/hapus)",
              "Pengguna mengendalikan ingatannya"),
           _w("Intern", "Uji percakapan baru: preferensi lama masih diingat",
              "Demo memori berhasil"),
       ),
       wireframe="""
memories(id, user, kind[fakta|preferensi], text, embedding BLOB, created_at)

percakapan baru -> ambil 3 memori termirip (>=0.35) -> system prompt
  "Yang diketahui tentang pengguna: divisi Finance; jawaban ringkas."

HALAMAN MEMORI
 • [fakta] Divisi Finance                 [edit] [hapus]
 • [pref ] Suka jawaban poin-poin singkat [edit] [hapus]
""",
       acceptance=(
           "Maksimal 5 fakta baru per ekstraksi dan tidak ada duplikat mirip (>0.9)",
           "Percakapan baru terbukti memakai memori lama pada skenario demo",
           "Blok memori di prompt tidak pernah melebihi 300 token",
           "Pengguna bisa melihat, mengedit, dan menghapus tiap memori",
           "Hapus memori langsung berpengaruh pada percakapan berikutnya"),
       evidence=(f"{P}/core/memory.py", f"{P}/tests/test_memory.py"),
       depends_on=("INT-011", "INT-009"), source=_ARCH),

    # ================================================================ Sprint 3
    _t("INT-016", "Guardrail input: prompt injection, jailbreak, dan toksisitas",
       "i3", priority="critical", estimate=1.5, labels=(*B, "epic-guardrail"),
       description=(
           "Epic 3 — Input Guardrails. `core/guardrail.py` memeriksa setiap "
           "pesan sebelum mencapai LLM utama: (1) pola prompt injection "
           "('abaikan instruksi sebelumnya', 'tampilkan system prompt', "
           "'kamu sekarang adalah…'), (2) kata/topik terlarang dari daftar "
           "yang bisa disunting admin, (3) panjang wajar (maks 4.000 karakter). "
           "Pesan yang diblokir mendapat jawaban penolakan yang sopan berisi "
           "alasan, dan kejadiannya dicatat ke tabel `guardrail_events` untuk "
           "ditinjau. Teks dokumen hasil retrieval juga diperlakukan sebagai "
           "data tidak tepercaya: instruksi di dalam dokumen tidak boleh "
           "dituruti (uji dengan dokumen jebakan)."),
       workflow=(
           _w("Intern", "Kumpulkan 20 contoh serangan + 20 pesan normal",
              "Set uji guardrail"),
           _w("Intern", "Implementasi aturan deteksi + daftar terlarang",
              "core/guardrail.py"),
           _w("Intern", "Tambah uji dokumen jebakan (injection lewat RAG)",
              "Instruksi di dokumen tidak dituruti"),
           _w("Intern", "Catat kejadian + tampilkan di halaman admin",
              "Kejadian bisa ditinjau"),
       ),
       wireframe="""
check_input(text) -> {ok, kategori, alasan}
  kategori: injection | terlarang | terlalu_panjang | ok

DITOLAK
 🤖 Maaf, permintaan ini saya tolak (terdeteksi prompt injection).
    Coba tanyakan ulang tanpa meminta saya mengabaikan aturan.

guardrail_events(id, session_id, kategori, cuplikan, created_at)
""",
       acceptance=(
           ">= 18 dari 20 contoh serangan terblokir (recall >= 90%)",
           "<= 1 dari 20 pesan normal ikut terblokir (false positive <= 5%)",
           "Dokumen jebakan berisi instruksi tidak mengubah perilaku model (uji otomatis)",
           "Setiap blokir tercatat di guardrail_events dengan kategori & cuplikan",
           "Daftar kata terlarang bisa disunting tanpa mengubah kode"),
       evidence=(f"{P}/core/guardrail.py", f"{P}/tests/test_guardrail.py"),
       depends_on=("INT-013",), source=_ARCH),

    _t("INT-017", "Redaksi PII sebelum konteks dikirim ke provider",
       "i3", priority="critical", estimate=1.5, labels=(*B, "epic-guardrail"),
       description=(
           "Epic 3 — PII Redaction. `core/pii.py` menyensor data sensitif "
           "Indonesia sebelum teks meninggalkan aplikasi: NIK 16 digit, nomor "
           "kartu kredit (dengan validasi Luhn agar angka biasa tidak ikut "
           "tersensor), email, nomor telepon (+62/08…), dan NPWP. Setiap "
           "temuan diganti token stabil `[NIK_1]`, `[EMAIL_1]` dan dipetakan "
           "di memori proses, sehingga jawaban model bisa dipulihkan kembali "
           "ke nilai asli saat ditampilkan ke pengguna (tanpa pernah "
           "menyimpan peta itu ke disk). Redaksi berlaku untuk pesan pengguna "
           "DAN potongan dokumen hasil retrieval."),
       workflow=(
           _w("Intern", "Tulis regex + validasi Luhn untuk 5 jenis PII",
              "core/pii.py"),
           _w("Intern", "Terapkan redaksi di jalur prompt (pesan + konteks RAG)",
              "Provider tidak pernah menerima PII mentah"),
           _w("Intern", "Implementasi pemulihan token saat menampilkan jawaban",
              "Pengguna tetap melihat data aslinya"),
           _w("Intern", "Uji 30 contoh positif + 30 negatif",
              "Angka presisi/recall tercatat"),
       ),
       wireframe="""
redact("NIK saya 3201234567890123, email a@b.com")
 -> "NIK saya [NIK_1], email [EMAIL_1]"  + peta {NIK_1: ..., EMAIL_1: ...}

restore(jawaban, peta) -> jawaban dengan nilai asli (hanya di layar)

DILINDUNGI: pesan pengguna, konteks RAG, memori jangka panjang
""",
       acceptance=(
           "Recall >= 95% pada 30 contoh PII; false positive <= 5% pada 30 teks biasa",
           "Kartu kredit hanya tersensor bila lolos Luhn",
           "Payload yang dikirim provider terbukti bebas PII (uji menangkap payload)",
           "Peta pemulihan tidak pernah ditulis ke disk atau ke tabel mana pun",
           "Redaksi juga berlaku pada potongan dokumen hasil retrieval"),
       evidence=(f"{P}/core/pii.py", f"{P}/tests/test_pii.py"),
       depends_on=("INT-016",), source=_ARCH),

    _t("INT-018", "Validator output terstruktur + retry otomatis",
       "i3", priority="high", estimate=1.5, labels=(*B, "epic-guardrail", "llm"),
       description=(
           "Epic 3 — Structured Output Validator. Untuk jalur yang butuh JSON "
           "(router, ekstraksi memori, alasan feedback, ringkasan), definisikan "
           "model pydantic dan minta model menjawab JSON saja. `core/structured.py` "
           "mem-parse hasil; bila gagal, kirim ulang ke LLM maksimal 2 kali "
           "dengan pesan error parser yang spesifik ('field `rute` wajib, nilai "
           "harus salah satu dari …'). Bila tetap gagal, pakai nilai default "
           "yang aman dan catat kejadian — pipeline tidak boleh mati karena "
           "model salah format."),
       workflow=(
           _w("Intern", "Definisikan skema pydantic untuk 4 jalur JSON",
              "core/schemas.py"),
           _w("Intern", "Implementasi parse + retry berpesan error",
              "core/structured.py"),
           _w("Intern", "Tambah default aman + pencatatan kegagalan",
              "Pipeline tidak pernah crash"),
           _w("Intern", "Uji dengan mock yang sengaja mengembalikan JSON rusak",
              "Retry & fallback terbukti"),
       ),
       wireframe="""
ask_json(prompt, schema=RouteDecision, retries=2)
  attempt 1 -> "{rute: dokumen}"        (bukan JSON valid)
  attempt 2 <- "JSON tidak valid: expecting property name in double quotes"
            -> {"rute":"dokumen","alasan":"...","keyakinan":0.8}  ✅
  gagal 3x  -> default {"rute":"dokumen","keyakinan":0.0} + catat
""",
       acceptance=(
           "JSON rusak memicu retry maksimal 2 kali dengan pesan error spesifik",
           "Kegagalan ketiga memakai default aman dan tercatat, tanpa exception ke UI",
           "4 jalur JSON memakai skema pydantic, tidak ada parsing manual",
           "Test memakai mock yang mengembalikan JSON rusak lalu benar",
           "Jumlah retry tercatat di trace permintaan"),
       evidence=(f"{P}/core/structured.py", f"{P}/core/schemas.py",
                 f"{P}/tests/test_structured.py"),
       depends_on=("INT-014",), source=_ARCH),

    _t("INT-019", "System prompt terkelola + parameter generasi",
       "i3", priority="medium", estimate=1, labels=(*B, *F, "epic-guardrail"),
       description=(
           "Satu tempat untuk mengatur perilaku model: halaman Pengaturan "
           "menyimpan system prompt (dengan versi dan catatan perubahan), "
           "temperature, max_tokens, top_p, dan daftar tool yang diaktifkan. "
           "Nilai tersimpan di SQLite sehingga bertahan setelah restart, "
           "dengan tombol 'kembalikan ke bawaan'. Setiap jawaban mencatat "
           "versi system prompt yang dipakai, supaya saat evaluasi kualitas "
           "turun bisa dilacak prompt mana penyebabnya."),
       workflow=(
           _w("Intern", "Buat tabel settings + nilai bawaan",
              "Pengaturan tersimpan"),
           _w("Intern", "Bangun halaman Pengaturan + validasi rentang nilai",
              "Parameter bisa diubah aman"),
           _w("Intern", "Catat versi prompt pada tiap jawaban",
              "Trace memuat prompt_version"),
           _w("Pembimbing", "Uji ubah prompt lalu restart aplikasi",
              "Nilai tetap tersimpan"),
       ),
       wireframe="""
HALAMAN PENGATURAN
 System prompt (v4)   [ textarea ........................ ]
 temperature  [0.2]  max_tokens [1024]  top_p [1.0]
 Tool aktif: [x] cari_dokumen  [x] kalkulator  [ ] waktu_sekarang
 [ Simpan ]  [ Kembalikan ke bawaan ]   riwayat versi: v1 v2 v3 v4
""",
       acceptance=(
           "Perubahan bertahan setelah aplikasi direstart",
           "Rentang nilai divalidasi (temperature 0-1, max_tokens 128-4096)",
           "Versi system prompt naik tiap disimpan dan tercatat di trace jawaban",
           "Tombol kembalikan ke bawaan mengembalikan seluruh nilai awal",
           "Menonaktifkan tool membuat tool itu tidak dikirim ke model"),
       evidence=(f"{P}/core/settings_store.py", f"{P}/tests/test_settings.py"),
       depends_on=("INT-018",), source=_ARCH),

    # ================================================================ Sprint 4
    _t("INT-020", "Tracing per permintaan: span DB, retrieval, LLM, tool",
       "i4", priority="critical", estimate=2, labels=(*B, "epic-observability"),
       description=(
           "Epic 4 — Request Tracing, dibuat sendiri (tanpa LangSmith/Datadog). "
           "`core/tracing.py` membuat `trace_id` per permintaan dan mencatat "
           "span bertingkat ke tabel `traces(trace_id, parent_id, nama, mulai, "
           "durasi_ms, meta_json, status)` untuk tahap: guardrail, router, "
           "retrieval, penyusunan konteks, panggilan LLM (termasuk TTFT), tiap "
           "tool, dan validator output. Halaman 'Trace' menampilkan daftar "
           "permintaan terbaru dan tampilan waterfall satu permintaan, plus "
           "tombol salin trace_id. Overhead pencatatan harus < 5% dari total "
           "durasi."),
       workflow=(
           _w("Intern", "Buat context manager span + tabel traces",
              "core/tracing.py"),
           _w("Intern", "Pasang span di 7 tahap pipeline",
              "Satu jawaban menghasilkan pohon span lengkap"),
           _w("Intern", "Bangun halaman Trace (daftar + waterfall)",
              "Durasi tiap tahap terlihat"),
           _w("Intern", "Ukur overhead tracing",
              "Angka overhead tercatat"),
       ),
       wireframe="""
TRACE  a1b2c3  total 2.410 ms
 guardrail_input      ▌ 12 ms
 router               ▌▌ 140 ms
 retrieval            ▌▌▌▌ 310 ms   (k=5, skor 0.71/0.66/…)
 build_context        ▌ 18 ms       (3.120 token)
 llm_stream           ▌▌▌▌▌▌▌ 1.870 ms (TTFT 640 ms, 412 tok)
 validate_output      ▌ 9 ms
""",
       acceptance=(
           "Satu jawaban menghasilkan minimal 6 span dengan durasi terisi",
           "trace_id tampil di UI dan bisa disalin",
           "Halaman waterfall menampilkan urutan dan durasi tiap span",
           "Overhead tracing < 5% dari total durasi (diukur dan dicatat)",
           "Span gagal ditandai status=error beserta pesannya"),
       evidence=(f"{P}/core/tracing.py", f"{P}/tests/test_tracing.py"),
       depends_on=("INT-014",), source=_ARCH),

    _t("INT-021", "Dasbor biaya & latensi: token, Rupiah, TTFT p50/p95",
       "i4", priority="high", estimate=1.5, labels=(*B, *F, "epic-observability"),
       description=(
           "Epic 4 — Analitik Biaya & Latensi. Halaman Dasbor menampilkan, per "
           "rentang waktu (hari ini / 7 hari / 30 hari): total token prompt & "
           "completion, estimasi biaya dalam Rupiah (harga per 1k token dari "
           "pengaturan), jumlah percakapan, biaya per percakapan, TTFT p50 dan "
           "p95, serta 5 percakapan termahal. Semua angka dihitung dari tabel "
           "`traces` dan `messages` — bukan dari log teks. Sertakan tombol "
           "ekspor CSV supaya angka bisa dilampirkan di laporan akhir magang."),
       workflow=(
           _w("Intern", "Tulis query agregasi token/biaya/latensi",
              "core/analytics.py"),
           _w("Intern", "Bangun halaman dasbor + filter rentang waktu",
              "Angka tampil per rentang"),
           _w("Intern", "Tambah ekspor CSV",
              "Data bisa dilampirkan ke laporan"),
           _w("Pembimbing", "Cek satu percakapan manual vs angka dasbor",
              "Selisih 0 token"),
       ),
       wireframe="""
DASBOR  [ hari ini | 7 hari | 30 hari ]            [ekspor CSV]
+----------------+----------------+----------------+-----------+
| Token prompt   | Token jawaban  | Biaya (Rp)     | Percakapan|
|    128.400     |     41.220     |    12.740      |    36     |
+----------------+----------------+----------------+-----------+
| TTFT p50 0,8 s | TTFT p95 2,4 s | Rp/percakapan 354          |
+----------------+----------------+----------------------------+
5 percakapan termahal: ...
""",
       acceptance=(
           "Angka token dasbor sama persis dengan penjumlahan manual satu percakapan uji",
           "TTFT p50 dan p95 dihitung dari span llm_stream, bukan perkiraan",
           "Filter 3 rentang waktu bekerja dan mengubah seluruh kartu angka",
           "Ekspor CSV memuat kolom tanggal, sesi, token, biaya, TTFT",
           "Harga per 1k token diambil dari pengaturan, bukan hardcode"),
       evidence=(f"{P}/core/analytics.py", f"{P}/tests/test_analytics.py"),
       depends_on=("INT-020",), source=_ARCH),

    _t("INT-022", "Feedback 👍/👎 dengan alasan terstruktur + trace_id",
       "i4", priority="high", estimate=1, labels=(*B, *F, "epic-observability"),
       description=(
           "Epic 4 — User Feedback Loop. Tiap bubble jawaban punya tombol 👍 "
           "dan 👎. Menekan 👎 membuka pilihan alasan terstruktur (tidak "
           "akurat / tidak menjawab / sitasi salah / terlalu panjang / bahasa "
           "aneh) plus komentar bebas opsional. Simpan ke tabel `feedback(id, "
           "trace_id, session_id, message_id, nilai, alasan, komentar, "
           "created_at)` supaya tiap penilaian bisa ditarik kembali ke trace "
           "lengkapnya. Halaman Dasbor menampilkan rasio 👍 dan 5 alasan 👎 "
           "terbanyak sebagai bahan perbaikan prompt."),
       workflow=(
           _w("Intern", "Buat tabel feedback + API simpan",
              "core/feedback.py"),
           _w("Intern", "Tambah tombol 👍/👎 + dialog alasan di UI",
              "Feedback bisa dikirim 1 klik"),
           _w("Intern", "Tampilkan rasio & alasan terbanyak di dasbor",
              "Kualitas terukur"),
           _w("Intern", "Pastikan feedback menyimpan trace_id",
              "Jawaban buruk bisa ditelusuri"),
       ),
       wireframe="""
 🤖 Cuti tahunan 12 hari [1].            [👍] [👎]
      └ 👎 dipilih:
        ( ) tidak akurat   ( ) tidak menjawab  ( ) sitasi salah
        ( ) terlalu panjang ( ) bahasa aneh
        [ komentar (opsional) ........................ ] [Kirim]

DASBOR: 👍 74%  (37/50)   alasan 👎 teratas: sitasi salah (6)
""",
       acceptance=(
           "👍 tersimpan dengan satu klik tanpa dialog tambahan",
           "👎 mewajibkan pilih satu alasan dari 5 opsi sebelum tersimpan",
           "Setiap baris feedback memuat trace_id yang valid dan bisa dibuka",
           "Dasbor menampilkan rasio 👍 dan 5 alasan terbanyak",
           "Feedback yang sama bisa diubah, tidak menghasilkan baris ganda"),
       evidence=(f"{P}/core/feedback.py", f"{P}/tests/test_feedback.py"),
       depends_on=("INT-020",), source=_ARCH),

    _t("INT-023", "Set evaluasi 20 soal + skrip eval offline",
       "i4", priority="high", estimate=1.5, labels=(*B, "epic-observability", "llm"),
       description=(
           "Tanpa set evaluasi, 'kualitas' hanya perasaan. Susun 20 pertanyaan "
           "uji dari dokumen yang diingest: 12 pertanyaan yang jawabannya ada "
           "di dokumen (lengkap dengan kunci jawaban + dokumen/halaman yang "
           "seharusnya disitasi), 5 pertanyaan di luar dokumen (model harus "
           "mengaku tidak tahu), dan 3 pertanyaan yang butuh tool. Skrip "
           "`eval.py` menjalankan semuanya lewat pipeline nyata dan mencetak "
           "tabel: akurasi sitasi, tingkat 'mengaku tidak tahu', rata-rata "
           "token, rata-rata latensi, dan biaya total satu putaran evaluasi."),
       workflow=(
           _w("Intern", "Susun 20 soal + kunci jawaban + sumber yang benar",
              "evalset.yaml"),
           _w("Intern", "Tulis eval.py yang menjalankan pipeline & menilai",
              "Laporan evaluasi tercetak"),
           _w("Intern", "Jalankan baseline dan simpan hasilnya",
              "Angka awal tercatat"),
           _w("Intern", "Ulangi setelah perbaikan prompt",
              "Perbandingan sebelum/sesudah"),
       ),
       wireframe="""
evalset.yaml
 - id: E01
   tanya: "Berapa hari cuti tahunan?"
   kunci: "12 hari"
   sumber: kebijakan-cuti.pdf#3
   tipe: dokumen

python eval.py --run baseline
 +------------------+--------+
 | sitasi benar     | 10/12  |
 | mengaku tdk tahu |  5/5   |
 | tool benar       |  2/3   |
 | rata token       | 1.840  |
 | rata latensi     | 2,1 s  |
 +------------------+--------+
""",
       acceptance=(
           "evalset berisi tepat 20 soal dengan komposisi 12/5/3",
           "`python eval.py` berjalan end-to-end memakai mock provider tanpa API key",
           "Laporan memuat 5 metrik dan disimpan ke berkas hasil bertanggal",
           "Hasil baseline tersimpan di repo sebagai pembanding",
           "Satu perbaikan prompt didokumentasikan dengan angka sebelum/sesudah"),
       evidence=(f"{P}/eval.py", f"{P}/evalset.yaml", f"{P}/docs/EVAL.md"),
       depends_on=("INT-022", "INT-012"), source=_ARCH),

    # ================================================================ Sprint 5
    _t("INT-024", "Semantic cache: jawab pertanyaan berulang tanpa panggil LLM",
       "i5", priority="high", estimate=1.5, labels=(*B, "epic-performa"),
       description=(
           "Epic 5 — Semantic Caching, versi SQLite (tanpa Redis). Tabel "
           "`cache(id, pertanyaan, embedding, jawaban, sumber_json, "
           "prompt_version, created_at, hits)` menyimpan jawaban final. Sebelum "
           "memanggil LLM, embed pertanyaan dan cari entri dengan cosine >= "
           "0.92 yang usianya < 24 jam dan `prompt_version` sama; bila ketemu, "
           "kembalikan jawaban itu dan tandai di UI sebagai 'dari cache'. "
           "Cache dibatalkan otomatis saat dokumen sumbernya berubah atau "
           "system prompt naik versi, dan tidak pernah dipakai untuk "
           "pertanyaan yang memicu tool (hasilnya bisa berubah tiap saat)."),
       workflow=(
           _w("Intern", "Buat tabel cache + penyimpanan jawaban final",
              "Cache terisi"),
           _w("Intern", "Implementasi lookup cosine >= 0.92 + TTL 24 jam",
              "Hit terdeteksi"),
           _w("Intern", "Tambah invalidasi saat dokumen/prompt berubah",
              "Jawaban basi tidak disajikan"),
           _w("Intern", "Ukur hit-rate & penghematan biaya",
              "Angka tercatat di dasbor"),
       ),
       wireframe="""
lookup(q):
  qv = embed(q)
  cari cache WHERE prompt_version = aktif AND umur < 24 jam
  skor >= 0.92 ? -> HIT (hits += 1, 0 token dipakai)
                 -> MISS (jalankan pipeline, simpan hasil)

UI: 🤖 ... jawaban ...   ⚡ dari cache (hemat ~1.800 token)
INVALIDASI: dokumen di-ingest ulang | prompt_version naik | tool dipakai
""",
       acceptance=(
           "Pertanyaan diulang persis menghasilkan cache hit dan 0 token LLM",
           "Parafrase dekat (cosine >= 0.92) ikut hit; parafrase jauh tidak",
           "Ingest dokumen baru atau naik versi prompt membatalkan cache terkait",
           "Jawaban yang memakai tool tidak pernah di-cache",
           "Dasbor menampilkan hit-rate dan estimasi token yang dihemat"),
       evidence=(f"{P}/core/cache.py", f"{P}/tests/test_cache.py"),
       depends_on=("INT-021",), source=_ARCH),

    _t("INT-025", "Rate limit & antrean sederhana per pengguna",
       "i5", priority="high", estimate=1.5, labels=(*B, "epic-performa"),
       description=(
           "Epic 5 — Rate Limiting, versi in-process (tanpa RabbitMQ/Kafka). "
           "`core/quota.py` menerapkan tiga batas per pengguna: 10 pesan per "
           "menit (token bucket), 50 pesan per hari, dan 100.000 token per "
           "hari. Saat batas terlampaui, UI menampilkan pesan jelas berisi "
           "sisa waktu tunggu — bukan error mentah. Permintaan yang masuk "
           "bersamaan diserialisasi lewat antrean sederhana `queue.Queue` "
           "dengan maksimal 2 pekerja, supaya provider tidak terkena burst. "
           "Angka batas dibaca dari pengaturan agar bisa diubah tanpa deploy."),
       workflow=(
           _w("Intern", "Implementasi token bucket + penghitung harian di SQLite",
              "core/quota.py"),
           _w("Intern", "Sambungkan ke pipeline + pesan UI yang jelas",
              "Batas terasa wajar, bukan error"),
           _w("Intern", "Tambah antrean 2 pekerja untuk permintaan bersamaan",
              "Burst tidak menembus provider"),
           _w("Intern", "Uji 20 permintaan beruntun",
              "Perilaku sesuai batas"),
       ),
       wireframe="""
BATAS (bisa diubah di Pengaturan)
  10 pesan / menit   |  50 pesan / hari  |  100.000 token / hari

UI saat kena batas
 ⏳ Kuota per menit habis. Coba lagi dalam 24 detik.
    Sisa hari ini: 18 pesan • 42.100 token

ANTREAN: queue.Queue(maxsize=8), 2 worker -> "menunggu giliran (2)"
""",
       acceptance=(
           "Permintaan ke-11 dalam satu menit ditolak dengan sisa waktu tunggu yang benar",
           "Batas harian pesan dan token berlaku dan tereset lewat tengah malam",
           "20 permintaan beruntun tidak menghasilkan error provider 429",
           "Angka batas dibaca dari pengaturan, bukan hardcode",
           "Penolakan kuota tercatat di trace dan terlihat di dasbor"),
       evidence=(f"{P}/core/quota.py", f"{P}/tests/test_quota.py"),
       depends_on=("INT-024",), source=_ARCH),

    _t("INT-026", "Fallback model + timeout: layanan tetap menjawab",
       "i5", priority="high", estimate=1, labels=(*B, "epic-performa", "llm"),
       description=(
           "Epic 5 — Model Fallback Strategy. Konfigurasi daftar model "
           "berurutan (`AGENT_MODELS=utama,cadangan,mock`). Bila model utama "
           "gagal (error 5xx, timeout 30 detik, atau tidak ada token pertama "
           "dalam 10 detik), pipeline otomatis mencoba model berikutnya dan "
           "menandai di UI model mana yang akhirnya menjawab. Mock selalu jadi "
           "cadangan terakhir supaya demo tidak pernah gagal total. Setiap "
           "peralihan dicatat ke trace dengan alasannya agar bisa dihitung "
           "berapa sering model utama bermasalah."),
       workflow=(
           _w("Intern", "Tambah daftar model + logika peralihan",
              "core/llm.py"),
           _w("Intern", "Uji dengan provider palsu yang sengaja gagal",
              "Fallback terbukti"),
           _w("Intern", "Tandai model penjawab di UI + trace",
              "Transparan ke pengguna"),
           _w("Pembimbing", "Matikan endpoint utama saat demo",
              "Jawaban tetap keluar"),
       ),
       wireframe="""
AGENT_MODELS = "gpt-4o-mini, llama3-lokal, mock"

 utama  -> timeout 30s / 5xx / TTFT > 10s  ->  cadangan
 cadangan gagal                            ->  mock (selalu berhasil)

UI: 🤖 ... jawaban ...   (dijawab oleh: llama3-lokal — model utama timeout)
""",
       acceptance=(
           "Model utama yang sengaja dimatikan memicu fallback < 31 detik",
           "Mock sebagai cadangan terakhir membuat demo tidak pernah gagal total",
           "UI menampilkan model mana yang menjawab bila bukan model utama",
           "Setiap peralihan tercatat di trace beserta alasannya",
           "Test fallback memakai provider palsu yang melempar 500 dan timeout"),
       evidence=(f"{P}/core/llm.py", f"{P}/tests/test_fallback.py"),
       depends_on=("INT-025",), source=_ARCH),

    _t("INT-027", "Docker + volume persisten untuk prototipe intern",
       "i5", priority="critical", estimate=1, labels=(*B, "epic-performa", "docs"),
       description=(
           "Bungkus prototipe menjadi satu image yang bisa dideploy ulang tanpa "
           "kehilangan data. Dockerfile: base `python:3.11-slim`, install "
           "requirements, `EXPOSE 8501`, jalankan `streamlit run app.py "
           "--server.address=0.0.0.0`. SELURUH state (agent.db, index.npy, "
           "dokumen mentah, model embedding yang diunduh) harus berada di "
           "bawah `/app/data` yang di-mount sebagai named volume, dengan env "
           "`AGENT_DB_PATH=/app/data/agent.db`, `AGENT_INDEX_PATH=/app/data/index.npy`, "
           "`AGENT_DOCS_DIR=/app/data/docs`. Sertakan docker-compose.yml, "
           "HEALTHCHECK, dan bukti uji: rebuild + redeploy, percakapan lama "
           "tetap ada."),
       workflow=(
           _w("Intern", "Tulis Dockerfile + .dockerignore",
              "Image ter-build"),
           _w("Intern", "Arahkan semua path state ke /app/data + VOLUME",
              "Tidak ada state di dalam layer image"),
           _w("Intern", "Tulis docker-compose.yml dengan named volume",
              "`docker compose up -d` jalan"),
           _w("Intern", "Uji redeploy: build ulang lalu cek data lama",
              "Bukti persistensi di docs/DEPLOY.md"),
       ),
       wireframe="""
Dockerfile
  FROM python:3.11-slim
  ENV AGENT_DB_PATH=/app/data/agent.db  AGENT_INDEX_PATH=/app/data/index.npy \\
      AGENT_DOCS_DIR=/app/data/docs
  RUN pip install --no-cache-dir -r requirements.txt
  VOLUME /app/data
  EXPOSE 8501
  HEALTHCHECK CMD curl -fsS http://127.0.0.1:8501/_stcore/health || exit 1
  CMD ["streamlit","run","app.py","--server.address=0.0.0.0"]

compose: volumes: [ agent-data:/app/data ]
""",
       acceptance=(
           "`docker compose up -d --build` menghasilkan aplikasi yang bisa dibuka",
           "Semua path state berada di /app/data (dibuktikan lewat env & docker inspect)",
           "Rebuild + redeploy: percakapan, dokumen, dan indeks lama tetap ada",
           "`docker compose down` lalu `up` tidak menghapus data",
           "HEALTHCHECK berstatus healthy dalam 60 detik"),
       evidence=(f"{P}/Dockerfile", f"{P}/docker-compose.yml",
                 f"{P}/docs/DEPLOY.md"),
       depends_on=("INT-026",), source=_ARCH),

    _t("INT-028", "Uji menyeluruh: unit, integrasi pipeline, dan smoke UI",
       "i5", priority="high", estimate=1.5, labels=(*B, "epic-performa"),
       description=(
           "Kumpulkan pengujian menjadi satu perintah `pytest` yang hijau di "
           "mesin bersih tanpa API key (semua lewat mock provider). Minimal: "
           "unit test untuk tokens, chunking, retrieval, guardrail, PII, "
           "structured output, quota, dan cache; satu test integrasi yang "
           "menjalankan pipeline penuh dari pertanyaan sampai jawaban "
           "bersitasi plus baris trace; dan satu smoke test yang mengimpor "
           "aplikasi Streamlit untuk memastikan halaman tidak error saat "
           "dimuat. Target cakupan modul `core/` >= 70% dan waktu jalan "
           "seluruh test < 60 detik."),
       workflow=(
           _w("Intern", "Rapikan test yang sudah ada + tambah yang kurang",
              "Satu perintah pytest"),
           _w("Intern", "Tulis test integrasi pipeline penuh",
              "Jalur utama terlindungi"),
           _w("Intern", "Ukur cakupan dengan pytest-cov",
              "Angka cakupan tercatat"),
           _w("Pembimbing", "Jalankan di mesin bersih tanpa API key",
              "Hijau tanpa konfigurasi tambahan"),
       ),
       wireframe="""
pytest -q
 tests/test_tokens.py ....      tests/test_guardrail.py ....
 tests/test_rag.py ....         tests/test_pii.py ....
 tests/test_pipeline.py .       (integrasi: tanya -> jawab + sitasi + trace)
 tests/test_smoke_ui.py .
 42 passed in 38s   coverage core/: 74%
""",
       acceptance=(
           "`pytest` hijau di mesin bersih tanpa API key apa pun",
           "Cakupan modul core/ >= 70% (laporan pytest-cov dilampirkan)",
           "Ada 1 test integrasi pipeline penuh yang memeriksa sitasi & trace",
           "Seluruh test selesai < 60 detik",
           "Cara menjalankan test tertulis di README"),
       evidence=(f"{P}/tests/test_pipeline.py", f"{P}/tests/test_smoke_ui.py",
                 f"{P}/docs/TESTING.md"),
       depends_on=("INT-027",), source=_DOD),

    _t("INT-029", "Dokumentasi, runbook, dan demo akhir 10 menit",
       "i5", priority="critical", estimate=1.5, labels=(*_L, "docs", "epic-performa"),
       description=(
           "Penutup magang. Lengkapi README (arsitektur, cara jalan, env, "
           "batasan yang diketahui), tulis runbook singkat (cara menambah "
           "dokumen, mengganti model, membaca trace, mengatasi 5 masalah "
           "tersering, cara backup `/app/data`), dan susun skrip demo 10 menit "
           "yang menunjukkan kelima epic secara berurutan. Tutup dengan tabel "
           "metrik nyata vs target dari PRD bagian B — diisi apa adanya, "
           "termasuk yang meleset, beserta penjelasan singkat penyebab dan "
           "rencana perbaikannya."),
       workflow=(
           _w("Intern", "Lengkapi README + runbook",
              "Orang baru bisa melanjutkan proyek"),
           _w("Intern", "Susun skrip demo 10 menit per epic",
              "docs/DEMO.md"),
           _w("Intern", "Ukur ulang 5 metrik PRD dan isi tabel nyata vs target",
              "Hasil jujur tercatat"),
           _w("Pembimbing", "Tonton demo & review dokumen",
              "Serah terima selesai"),
       ),
       wireframe="""
SKRIP DEMO (10 menit)
 0:00 masalah & produk (PRD)              1 mnt
 1:00 chat + sesi lama dilanjutkan        1,5 mnt  (Epic 1)
 2:30 tanya dokumen + sitasi + tool       2 mnt    (Epic 2)
 4:30 coba prompt injection & PII         1,5 mnt  (Epic 3)
 6:00 trace waterfall + dasbor biaya      2 mnt    (Epic 4)
 8:00 cache hit + matikan model utama     1,5 mnt  (Epic 5)
 9:30 metrik nyata vs target + rencana    0,5 mnt
""",
       acceptance=(
           "README memuat arsitektur, setup, env, dan batasan yang diketahui",
           "Runbook memuat 5 masalah tersering beserta langkah penanganannya",
           "Skrip demo mencakup kelima epic dan selesai <= 10 menit saat dilatih",
           "Tabel metrik nyata vs target terisi angka, termasuk yang meleset",
           "Semua task papan berstatus akhir yang benar saat serah terima"),
       evidence=(f"{P}/README.md", f"{P}/docs/RUNBOOK.md", f"{P}/docs/DEMO.md"),
       depends_on=("INT-028", "INT-023"), source=_DOD),
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
