"""Rencana proyek internship — **Chatbot AI Agent production-ready, end to end**.

Papan ini terpisah dari rencana platform (`tasks_plan.py`, id `ASK-NNN`): id di
sini memakai prefix `INT-NNN` dan halaman-nya `/internship`.

Sasaran papan (berbeda dari versi sebelumnya yang berhenti di prototipe):
membangun **satu produk chatbot berbasis AI agent yang layak dipakai pengguna
sungguhan** — lengkap dengan RAG, memori percakapan, akuntansi & limit token per
pengguna, pencatatan feedback 👍/👎, observability, keamanan, dan peluncuran.

Tiap task ditulis agar bisa dikerjakan tanpa bertanya lagi:

  * ``description`` — konteks + keputusan teknis yang sudah ditetapkan,
  * ``workflow``    — alur kerja bernomor ``{actor, action, result}``
                      (siapa melakukan apa, hasilnya apa) — dipakai UI tab
                      *Workflow* di panel detail task,
  * ``wireframe``   — sketsa layout / bentuk data (ASCII) untuk task UI, atau
                      diagram alur/skema untuk task backend,
  * ``acceptance``  — kriteria selesai yang bisa dicentang & diuji,
  * ``evidence``    — berkas yang harus ada (diperiksa ``POST /api/tasks/sync``),
  * ``depends_on``  — prasyarat, supaya urutan pengerjaan jelas.

Konvensi id dipakai apa adanya di nama branch git (``feat/INT-007-…``).
"""
from __future__ import annotations

from typing import Any

from .tasks_plan import PRIORITIES, STATUSES, STATUS_LABELS  # noqa: F401  (re-export)

#: Penanda papan (dipakai filter `/api/tasks?track=internship`).
TRACK = "internship"

#: Folder proyek yang dibangun intern di dalam repo ini.
PROJECT_DIR = "projects/ai-agent"

PHASES: list[dict[str, str]] = [
    {"id": "i0", "name": "Fase 0 — Fondasi & Kontrak",
     "subtitle": "Repo, kontrak API, skema data, autentikasi, konfigurasi, CI."},
    {"id": "i1", "name": "Fase 1 — Chat Inti & Streaming",
     "subtitle": "Provider LLM, streaming SSE, persistensi percakapan, UI chat."},
    {"id": "i2", "name": "Fase 2 — Agent, Tool & Pengetahuan",
     "subtitle": "ReAct loop, tool registry, ingest + RAG, sitasi, guardrail."},
    {"id": "i3", "name": "Fase 3 — Memori & Konteks",
     "subtitle": "Jendela konteks, ringkasan otomatis, memori jangka panjang."},
    {"id": "i4", "name": "Fase 4 — Token, Kuota & Feedback",
     "subtitle": "Hitung token, limit per pengguna, 👍/👎, analitik kualitas."},
    {"id": "i5", "name": "Fase 5 — Hardening, Observability & Rilis",
     "subtitle": "Keamanan, logging, uji beban, deploy, runbook, serah terima."},
]

PHASE_IDS = tuple(p["id"] for p in PHASES)

#: Rujukan dokumen pendamping.
_DOC = "docs/internship"
_SPEC = f"{_DOC}/01-spesifikasi-produk.md"
_ARCH = f"{_DOC}/02-arsitektur-dan-tech-stack.md"
_API = f"{_DOC}/03-kontrak-api-dan-data.md"
_SPRINT = f"{_DOC}/04-rencana-sprint-dan-task.md"
_SUCCESS = f"{_DOC}/05-kriteria-sukses-dan-demo.md"
_WORK = f"{_DOC}/06-panduan-kerja-dan-review.md"

#: Berkas referensi di **ask-anything** yang boleh dibaca sebagai contoh pola
#: (bukan untuk disalin: proyek baru ditulis sendiri — lihat dokumen 06).
REF = {
    "agent": "ask-anything: backend/app/agent/loop.py",
    "tools": "ask-anything: backend/app/tools/__init__.py",
    "rag": "ask-anything: backend/app/rag.py",
    "memory": "ask-anything: backend/app/memory.py",
    "db": "ask-anything: backend/app/db.py",
    "auth": "ask-anything: backend/app/auth.py",
    "stream": "ask-anything: frontend/lib/live.ts",
    "feedback": "ask-anything: frontend/components/FeedbackButtons.tsx",
}


def _w(actor: str, action: str, result: str = "") -> dict[str, str]:
    """Satu langkah workflow: siapa (actor) → melakukan apa → hasilnya apa."""
    return {"actor": actor, "action": action, "result": result}


def _t(task_id: str, title: str, phase: str, *, priority: str = "medium",
       estimate: float = 1.0, labels: tuple[str, ...] = (),
       description: str = "", workflow: tuple[dict[str, str], ...] = (),
       wireframe: str = "", acceptance: tuple[str, ...] = (),
       evidence: tuple[str, ...] = (), depends_on: tuple[str, ...] = (),
       source: str = "", status: str = "todo", assignee: str = "") -> dict[str, Any]:
    return {
        "id": task_id, "title": title, "phase": phase, "priority": priority,
        "estimate": estimate, "labels": list(labels),
        "description": description.strip(),
        "workflow": [dict(step) for step in workflow],
        "wireframe": wireframe.strip("\n"),
        "acceptance": list(acceptance),
        "evidence": list(evidence), "depends_on": list(depends_on),
        "source": source, "status": status, "assignee": assignee,
    }


_L = ("internship",)
B = (*_L, "backend")
F = (*_L, "frontend")

#: Akun member contoh (dibuat otomatis saat backend pertama kali start).
INTERNS: tuple[str, ...] = ("intern1", "intern2", "intern3")

P = PROJECT_DIR

TASKS: list[dict[str, Any]] = [
    # ================================================================== Fase 0
    _t("INT-001", "Spesifikasi produk: persona, ruang lingkup, non-goals",
       "i0", priority="critical", estimate=1, labels=(*_L, "produk", "docs"),
       description=(
           "Sebelum menulis kode, kunci dulu APA yang dibangun: chatbot AI agent "
           "internal yang menjawab pertanyaan karyawan berdasarkan dokumen "
           "perusahaan, bisa memakai tool (retrieval, kalkulator, pencarian), "
           "mengingat konteks percakapan, dan dibatasi kuota token per pengguna. "
           "Tulis 3 persona (karyawan biasa, power user, admin), 8-10 user story "
           "berformat 'Sebagai … saya ingin … supaya …', metrik keberhasilan "
           "(jawaban tergrounding >80%, p95 first-token <2 dtk, rasio 👍 >70%), "
           "dan daftar NON-goal yang eksplisit (tanpa voice, tanpa multi-tenant, "
           "tanpa fine-tuning model) supaya scope tidak melar."),
       workflow=(
           _w("Intern", "Wawancara/pahami kebutuhan dari pembimbing & dokumen slide",
              "Catatan kebutuhan mentah"),
           _w("Intern", "Rumuskan persona + user story + metrik + non-goals",
              "Draf 01-spesifikasi-produk.md"),
           _w("Pembimbing", "Review draf dan tandai scope yang ditolak",
              "Komentar revisi di merge request"),
           _w("Intern", "Revisi & kunci versi 1.0 spesifikasi",
              "Dokumen disetujui, jadi acuan semua task berikutnya"),
       ),
       wireframe="""
DOKUMEN 01 — SPESIFIKASI PRODUK
+--------------------------------------------------------------+
| 1. Masalah & peluang            (1 paragraf)                  |
| 2. Persona                                                    |
|    +----------------+----------------+----------------+       |
|    | Karyawan       | Power user     | Admin          |       |
|    | tujuan / nyeri | tujuan / nyeri | tujuan / nyeri |       |
|    +----------------+----------------+----------------+       |
| 3. User story (8-10)  [ ] Sebagai ... ingin ... supaya ...    |
| 4. Metrik sukses    grounded>80% | p95<2s | 👍>70% | biaya/hr |
| 5. NON-GOALS (daftar tegas yang TIDAK dibuat)                 |
| 6. Risiko & asumsi                                            |
+--------------------------------------------------------------+
""",
       acceptance=("3 persona lengkap dengan tujuan & titik nyeri",
                   "Minimal 8 user story berformat baku dan bisa diuji",
                   "Metrik sukses punya angka target, bukan kata sifat",
                   "Daftar non-goal ditulis eksplisit dan disetujui pembimbing"),
       evidence=(_SPEC,), source=_SPEC),

    _t("INT-002", "Arsitektur & pemilihan tech stack (ADR)",
       "i0", priority="critical", estimate=1, labels=(*_L, "arsitektur", "docs"),
       description=(
           "Gambar arsitektur target dan tulis 5 Architecture Decision Record "
           "singkat: (1) FastAPI + SQLite/Postgres, (2) Next.js App Router + "
           "Tailwind, (3) provider LLM di balik antarmuka `LLMProvider` supaya "
           "bisa ditukar (OpenAI-compatible / Ollama lokal), (4) vector store "
           "(Chroma persistent dengan fallback SQLite+cosine), (5) streaming "
           "memakai SSE bukan WebSocket. Setiap ADR memuat konteks, opsi yang "
           "dipertimbangkan, keputusan, dan konsekuensinya."),
       workflow=(
           _w("Intern", "Petakan komponen: UI → API → agent → tool → store → LLM",
              "Diagram arsitektur (mermaid) di dokumen 02"),
           _w("Intern", "Bandingkan minimal 2 opsi untuk tiap keputusan besar",
              "Tabel perbandingan dengan kriteria (biaya, offline, kecepatan)"),
           _w("Intern", "Tulis ADR-001..ADR-005 satu halaman masing-masing",
              "Keputusan terdokumentasi, alasan bisa ditelusuri"),
           _w("Pembimbing", "Setujui atau minta revisi ADR", "Stack terkunci"),
       ),
       wireframe="""
ARSITEKTUR TARGET
 Browser
   |  HTTPS
   v
+--------------------+       +--------------------------+
|  Next.js (App)     | --->  |  FastAPI /api            |
|  chat | sumber     |  SSE  |  auth · quota · agent    |
+--------------------+       +------------+-------------+
                                          |
        +-------------+-------------+-----+-------+--------------+
        v             v             v             v              v
   LLMProvider   ToolRegistry   VectorStore   MemoryStore   Telemetry
   (OpenAI/      (rag, calc,    (Chroma /     (ringkasan,   (log, metrik,
    Ollama)       search)        SQLite)       fakta user)   biaya token)
        |                            |
        +--------- SQLite/Postgres: users, conversations, messages,
                    feedback, token_usage, memories, documents, chunks
""",
       acceptance=("Diagram arsitektur bisa dibaca orang baru dalam 2 menit",
                   "5 ADR ditulis dengan konteks-opsi-keputusan-konsekuensi",
                   "Batas modul jelas: tidak ada komponen yang memanggil DB langsung dari UI",
                   "Stack disetujui pembimbing sebelum Fase 1 dimulai"),
       evidence=(_ARCH, f"{P}/docs/adr/ADR-001-llm-provider.md"),
       depends_on=("INT-001",), source=_ARCH),

    _t("INT-003", "Kontrak API & skema database v1",
       "i0", priority="critical", estimate=1.5, labels=(*_L, "design", "docs"),
       description=(
           "Tulis kontrak REST + SSE lengkap dengan contoh request/response JSON "
           "supaya frontend & backend bisa jalan paralel: auth, conversations, "
           "messages (streaming), documents, feedback, usage/quota, admin. "
           "Sertakan skema tabel lengkap: users, sessions, conversations, "
           "messages, message_citations, documents, chunks, memories, feedback, "
           "token_usage, quota_policies, audit_log — beserta index dan aturan "
           "kaskade hapus. Kunci juga bentuk error standar "
           "`{error: {code, message, detail}}` dan kode status yang dipakai."),
       workflow=(
           _w("Intern", "Daftar semua endpoint dari user story dokumen 01",
              "Tabel endpoint × metode × peran"),
           _w("Intern", "Tulis contoh request/response JSON tiap endpoint",
              "Kontrak yang bisa dipakai membuat mock"),
           _w("Intern", "Rancang tabel + relasi + index",
              "DATA-MODEL.md berisi DDL siap pakai"),
           _w("Frontend & Backend", "Sepakati kontrak dalam satu review bersama",
              "Kontrak v1 dibekukan; perubahan wajib lewat MR"),
       ),
       wireframe="""
ENDPOINT v1
  POST   /api/auth/login             → {token, user}
  GET    /api/conversations          → [{id, title, updated_at}]
  POST   /api/conversations          → {id}
  GET    /api/conversations/{id}     → {messages[], citations[]}
  POST   /api/chat            (SSE)  → event: token|tool|citation|usage|done
  POST   /api/documents/upload       → {document_id, status}
  POST   /api/feedback               → {ok}  {message_id, rating, reason, note}
  GET    /api/usage/me               → {used_tokens, limit, reset_at}
  GET    /api/admin/analytics        → {csat, top_bad_answers, cost}

SKEMA (inti)
  users ──< conversations ──< messages ──< message_citations
                                 |
                                 +──< feedback (1 per user per message)
  users ──< token_usage (harian)      users ──< memories
  documents ──< chunks (vector)
""",
       acceptance=("Semua endpoint punya contoh request DAN response",
                   "Skema tabel lengkap dengan tipe, index, dan aturan kaskade",
                   "Format error & daftar kode status disepakati",
                   "Kontrak direview bersama frontend + backend + pembimbing"),
       evidence=(f"{P}/docs/API.md", f"{P}/docs/DATA-MODEL.md"),
       depends_on=("INT-002",), source=_API),

    _t("INT-004", "Kerangka backend: config, logging terstruktur, error handler",
       "i0", priority="critical", estimate=1, labels=B,
       description=(
           "Aplikasi FastAPI dasar: `/api/health` (status, versi, provider, "
           "koneksi DB), konfigurasi dari .env lewat pydantic-settings (tanpa "
           "rahasia hardcoded), logging JSON terstruktur dengan `request_id` "
           "yang mengalir dari middleware ke seluruh log, dan exception handler "
           "yang selalu membalas JSON `{error:{code,message}}` — bukan traceback "
           "HTML. Tambahkan middleware CORS dan timing (durasi tiap request)."),
       workflow=(
           _w("Browser", "Kirim request ke /api/*", "Middleware membuat request_id"),
           _w("Middleware", "Catat mulai, teruskan ke handler, catat durasi",
              "Log JSON {request_id, path, status, ms}"),
           _w("Handler", "Lempar AppError bila input/bisnis salah",
              "Exception handler mengubahnya jadi JSON 4xx"),
           _w("Exception handler", "Tangkap error tak terduga",
              "Log level error + balas 500 generik tanpa bocorkan internal"),
       ),
       wireframe="""
BENTUK LOG & ERROR
  log  → {"ts":"…","level":"info","request_id":"a1b2","path":"/api/chat",
          "user":"u_12","status":200,"ms":842}
  err  → HTTP 400
         {"error":{"code":"invalid_input",
                   "message":"pesan tidak boleh kosong",
                   "detail":{"field":"message"}}}
  health → {"status":"ok","version":"0.1.0","provider":"ollama",
            "db":"ok","uptime_s":120}
""",
       acceptance=("/api/health membalas status, versi, provider, dan status DB",
                   "Semua konfigurasi dibaca dari .env; .env.example lengkap",
                   "Semua error 4xx/5xx berbentuk JSON dengan code+message",
                   "request_id muncul di setiap baris log satu request",
                   "pytest untuk health, config, dan error handler hijau"),
       evidence=(f"{P}/backend/app/main.py", f"{P}/backend/app/config.py",
                 f"{P}/backend/tests/test_health.py"),
       depends_on=("INT-003",), source=_ARCH),

    _t("INT-005", "Autentikasi & peran (user / admin) + sesi aman",
       "i0", priority="critical", estimate=1.5, labels=(*B, "security"),
       description=(
           "Login berbasis username+password (hash Argon2/bcrypt, bukan plain), "
           "sesi disimpan di cookie HttpOnly + SameSite=Lax dengan masa berlaku "
           "dan pencabutan (logout menghapus baris sesi). Dua peran: `user` "
           "(chat, lihat kuota & riwayat sendiri) dan `admin` (semua + analitik "
           "+ atur kuota). Sediakan dependency `current_user` dan `require_admin` "
           "yang dipakai seluruh endpoint, serta rate limit login (5 percobaan / "
           "15 menit per IP) untuk menahan brute force."),
       workflow=(
           _w("Pengguna", "Isi username & password lalu submit",
              "POST /api/auth/login"),
           _w("Backend", "Verifikasi hash password + cek rate limit IP",
              "Gagal → 401 pesan generik; berhasil → buat baris sesi"),
           _w("Backend", "Set cookie HttpOnly berisi token sesi acak 32 byte",
              "Browser membawa cookie otomatis di request berikutnya"),
           _w("Dependency current_user", "Baca cookie → cari sesi aktif → muat user",
              "Handler menerima objek user; sesi kedaluwarsa → 401"),
           _w("Pengguna", "Logout", "Baris sesi dihapus, cookie dikosongkan"),
       ),
       wireframe="""
HALAMAN LOGIN
+--------------------------------------------+
|            [logo]  Masuk                   |
|  Username [________________________]       |
|  Password [________________________] 👁     |
|  [ Masuk ]                                 |
|  ⚠ Username atau password salah            |
|  ⚠ Terlalu banyak percobaan, coba 15 menit |
+--------------------------------------------+
""",
       acceptance=("Password tersimpan sebagai hash; tidak ada plain text di DB/log",
                   "Cookie sesi HttpOnly + SameSite dan punya kedaluwarsa",
                   "Logout benar-benar mencabut sesi (request berikutnya 401)",
                   "Endpoint admin menolak user biasa dengan 403",
                   "Rate limit login terbukti lewat test"),
       evidence=(f"{P}/backend/app/auth.py", f"{P}/backend/tests/test_auth.py"),
       depends_on=("INT-004",), source=_API),

    _t("INT-006", "Kerangka frontend Next.js + proxy /api + shell layout",
       "i0", priority="high", estimate=1, labels=F,
       description=(
           "Next.js App Router + Tailwind: layout shell (sidebar riwayat, area "
           "chat, header dengan indikator kuota), rewrite `/api/*` ke backend "
           "supaya browser tidak pernah memanggil host backend langsung, "
           "halaman login, dan guard klien yang mengalihkan ke /login saat 401. "
           "Sediakan `lib/api.ts` (fetch wrapper: JSON, error terstandar, "
           "credentials: include) yang dipakai seluruh halaman."),
       workflow=(
           _w("Pengguna", "Buka aplikasi", "Guard memanggil /api/auth/me"),
           _w("Guard", "401 → arahkan ke /login; 200 → render shell",
              "Tidak pernah ada layar chat tanpa identitas"),
           _w("lib/api.ts", "Bungkus fetch: tambah header, parse error standar",
              "Komponen cukup menangkap Error berisi pesan yang siap tampil"),
       ),
       wireframe="""
SHELL APLIKASI (desktop)
+----------------+---------------------------------------+
| ☰ Percakapan   |  Judul percakapan      [kuota 62%]   |
| + Baru         +---------------------------------------+
| · Cuti tahunan |                                       |
| · SOP klaim    |            area pesan                 |
| · Onboarding   |                                       |
|                +---------------------------------------+
| [profil ▾]     |  [ tulis pesan ...............] [→]   |
+----------------+---------------------------------------+
mobile: sidebar jadi drawer, header tetap menampilkan sisa kuota
""",
       acceptance=("npm run dev menampilkan shell + login",
                   "Semua panggilan data lewat /api (relatif), bukan host absolut",
                   "401 dari backend otomatis mengarahkan ke /login",
                   "npm run build dan lint lolos tanpa warning baru"),
       evidence=(f"{P}/frontend/app/layout.tsx", f"{P}/frontend/lib/api.ts",
                 f"{P}/frontend/next.config.ts"),
       depends_on=("INT-005",), source=_ARCH),

    _t("INT-007", "docker-compose, seed data, dan pipeline CI",
       "i0", priority="high", estimate=1, labels=(*_L, "devops"),
       description=(
           "Satu perintah untuk menjalankan semuanya: docker-compose (backend, "
           "frontend, volume data) + `scripts/seed.py` idempoten yang membuat "
           "user demo (user & admin), 1 dokumen contoh, dan kebijakan kuota "
           "default. CI (GitHub Actions) menjalankan lint, pytest, dan vitest "
           "pada setiap push/MR dan menolak merge bila merah."),
       workflow=(
           _w("Developer", "Jalankan `docker compose up`",
              "Backend + frontend hidup, data persist di volume"),
           _w("Developer", "Jalankan `python scripts/seed.py`",
              "User demo, dokumen contoh, dan kuota default tersedia"),
           _w("CI", "Pada push: install → lint → pytest → vitest → build",
              "Status check hijau/merah menempel di merge request"),
       ),
       wireframe="""
PIPELINE CI
  push/MR ─► [lint ruff+eslint] ─► [pytest] ─► [vitest] ─► [build] ─► ✅/❌
                    |                 |            |
                 gagal → berhenti & laporkan langkah yang merah

docker compose up
  backend :8000  ── volume ./data
  frontend :3000 ── proxy /api → backend:8000
""",
       acceptance=("`docker compose up` menjalankan kedua service tanpa langkah manual",
                   "seed.py idempoten (dijalankan 2x tidak menggandakan data)",
                   "CI gagal bila ada test merah atau lint error",
                   "README memuat cara menjalankan dari nol"),
       evidence=(f"{P}/docker-compose.yml", f"{P}/scripts/seed.py",
                 f"{P}/.github/workflows/ci.yml"),
       depends_on=("INT-004", "INT-006"), source=_WORK),

    # ================================================================== Fase 1
    _t("INT-008", "Abstraksi LLMProvider + fallback & retry",
       "i1", priority="critical", estimate=1.5, labels=(*B, "llm"),
       description=(
           "Antarmuka `LLMProvider` dengan dua implementasi: OpenAI-compatible "
           "(HTTP) dan Ollama lokal, plus `EchoProvider` untuk test offline. "
           "Metode: `chat(messages, tools, stream)` mengembalikan potongan token "
           "dan/atau permintaan tool. Tangani kegagalan secara dewasa: timeout, "
           "retry dengan exponential backoff untuk 429/5xx (maks 2x), circuit "
           "breaker sederhana, dan pesan ramah saat provider mati — bukan "
           "stack trace ke pengguna."),
       workflow=(
           _w("Agent", "Panggil provider.chat(messages, tools)",
              "Provider memilih implementasi sesuai .env"),
           _w("Provider", "Kirim HTTP dengan timeout 60 dtk",
              "Sukses → alirkan potongan; 429/5xx → retry backoff 1s, 3s"),
           _w("Provider", "Setelah 3 kegagalan beruntun buka circuit 60 dtk",
              "Request berikutnya langsung gagal cepat dengan pesan jelas"),
           _w("Backend", "Ubah kegagalan jadi event SSE `error` yang sopan",
              "UI menampilkan banner 'Layanan AI sedang sibuk, coba lagi'"),
       ),
       wireframe="""
ALUR PROVIDER
  chat() ─► [timeout 60s] ─► LLM
             |  429/5xx
             ├─ retry #1 (1s) ─► LLM
             ├─ retry #2 (3s) ─► LLM
             └─ gagal ─► circuit OPEN 60s ─► event SSE:
                         {"type":"error","code":"llm_unavailable",
                          "message":"Layanan AI sedang sibuk."}
""",
       acceptance=("Ganti provider cukup lewat .env tanpa mengubah kode pemanggil",
                   "Retry & backoff terbukti lewat test dengan provider palsu",
                   "Circuit breaker mencegah banjir request saat provider mati",
                   "Kegagalan provider tidak pernah membocorkan URL/kunci API"),
       evidence=(f"{P}/backend/app/llm/provider.py",
                 f"{P}/backend/tests/test_provider.py"),
       depends_on=("INT-004",), source=_ARCH),

    _t("INT-009", "Endpoint chat streaming SSE + persistensi percakapan",
       "i1", priority="critical", estimate=2, labels=(*B, "chat"),
       description=(
           "`POST /api/chat` menerima {conversation_id?, message} dan mengalirkan "
           "Server-Sent Events bertipe: `start`, `token`, `tool`, `citation`, "
           "`usage`, `done`, `error`. Percakapan & pesan disimpan sebelum dan "
           "sesudah generasi sehingga refresh tidak kehilangan apa pun. Judul "
           "percakapan dibuat otomatis dari pesan pertama. Batalkan generasi "
           "dengan rapi bila klien memutus koneksi (hemat token)."),
       workflow=(
           _w("Pengguna", "Kirim pesan dari composer",
              "POST /api/chat dengan conversation_id"),
           _w("Backend", "Simpan pesan user + buat baris pesan assistant kosong",
              "Riwayat aman walau proses terputus di tengah"),
           _w("Backend", "Alirkan event start → token* → usage → done",
              "UI menampilkan jawaban mengalir kata demi kata"),
           _w("Backend", "Saat done: simpan teks final, token terpakai, sitasi",
              "Pesan tersimpan utuh dan bisa dibuka lagi"),
           _w("Pengguna", "Tutup tab di tengah jawaban",
              "Server mendeteksi disconnect → hentikan generasi, simpan parsial"),
       ),
       wireframe="""
ALIRAN EVENT SSE
  event: start     data: {"message_id":"m_9","conversation_id":"c_3"}
  event: tool      data: {"name":"retrieve_knowledge","status":"running"}
  event: citation  data: {"n":1,"doc":"SOP-Cuti.pdf","page":4}
  event: token     data: {"text":"Cuti "}
  event: token     data: {"text":"tahunan "}
  event: usage     data: {"prompt":812,"completion":140,"total":952}
  event: done      data: {"message_id":"m_9","finish":"stop"}
""",
       acceptance=("Jawaban tampil mengalir, bukan sekaligus di akhir",
                   "Refresh halaman menampilkan percakapan lengkap dari DB",
                   "Judul percakapan terisi otomatis dari pesan pertama",
                   "Klien putus → generasi dihentikan dan teks parsial tersimpan",
                   "Ada test SSE memakai provider palsu"),
       evidence=(f"{P}/backend/app/api/chat.py",
                 f"{P}/backend/tests/test_chat_stream.py"),
       depends_on=("INT-008", "INT-005"), source=_API),

    _t("INT-010", "UI chat: composer, bubble streaming, status, dan error",
       "i1", priority="critical", estimate=2, labels=F,
       description=(
           "Komponen chat lengkap: daftar pesan (markdown + blok kode + salin), "
           "bubble assistant yang mengalir dengan kursor ketik, indikator "
           "'sedang memakai tool …', tombol Hentikan, retry saat gagal, dan "
           "composer yang mendukung Enter kirim / Shift+Enter baris baru serta "
           "auto-resize. Fokus pada layar yang **tenang**: satu kolom utama, "
           "detail teknis disembunyikan di balik panel yang bisa dibuka."),
       workflow=(
           _w("Pengguna", "Ketik pertanyaan lalu tekan Enter",
              "Bubble user muncul instan (optimistis)"),
           _w("UI", "Buka koneksi SSE dan tambahkan token ke bubble assistant",
              "Teks bertambah halus, auto-scroll mengikuti"),
           _w("UI", "Tampilkan chip tool saat event `tool` diterima",
              "Pengguna tahu agent sedang mencari dokumen"),
           _w("Pengguna", "Klik Hentikan", "Koneksi ditutup, teks parsial tetap ada"),
           _w("UI", "Saat event error", "Banner sopan + tombol Coba lagi"),
       ),
       wireframe="""
LAYAR CHAT
+--------------------------------------------------------------+
|  Kebijakan cuti                          [kuota 62% ▓▓▓░░]   |
+--------------------------------------------------------------+
|                            +-------------------------------+ |
|                            | Berapa hari cuti tahunan?  🧑 | |
|                            +-------------------------------+ |
| +----------------------------------------------------------+ |
| | 🤖  🔎 mencari dokumen…                                   | |
| |     Cuti tahunan adalah 12 hari kerja [1]. ▌              | |
| |     ─────────────────────────────────────                 | |
| |     Sumber: [1] SOP-Cuti.pdf hal. 4                       | |
| |     👍  👎   ⧉ salin                                       | |
| +----------------------------------------------------------+ |
+--------------------------------------------------------------+
| [ Tulis pesan…                               ]  [Hentikan] → |
+--------------------------------------------------------------+
""",
       acceptance=("Token tampil mengalir tanpa layar berkedip",
                   "Enter mengirim, Shift+Enter baris baru, composer auto-resize",
                   "Tombol Hentikan benar-benar memutus generasi",
                   "Pesan error tampil sebagai banner ramah + tombol coba lagi",
                   "Markdown & blok kode ter-render dengan tombol salin"),
       evidence=(f"{P}/frontend/components/ChatView.tsx",
                 f"{P}/frontend/components/Composer.tsx"),
       depends_on=("INT-009", "INT-006"), source=_SPEC),

    _t("INT-011", "Riwayat percakapan: daftar, ganti nama, hapus, cari",
       "i1", priority="high", estimate=1, labels=(*_L, "fullstack"),
       description=(
           "Sidebar riwayat yang benar-benar terpakai: daftar percakapan milik "
           "user (terbaru di atas, dikelompokkan Hari ini / 7 hari / Lebih lama), "
           "ganti nama inline, hapus dengan konfirmasi, dan pencarian teks pada "
           "judul + isi pesan. Backend menyediakan pagination (limit/cursor) "
           "supaya daftar tetap ringan setelah ratusan percakapan."),
       workflow=(
           _w("Pengguna", "Buka aplikasi", "Sidebar memuat 20 percakapan terbaru"),
           _w("Pengguna", "Scroll ke bawah", "Halaman berikutnya dimuat lewat cursor"),
           _w("Pengguna", "Ketik kata kunci di kolom cari",
              "Backend mencari judul+isi, hasil ditandai"),
           _w("Pengguna", "Klik hapus", "Dialog konfirmasi → percakapan & pesan terhapus"),
       ),
       wireframe="""
SIDEBAR RIWAYAT
+--------------------------+
| 🔍 cari percakapan...    |
| + Percakapan baru        |
|--------------------------|
| HARI INI                 |
| · Kebijakan cuti    ⋯    |
| · Klaim kesehatan   ⋯    |
| 7 HARI TERAKHIR          |
| · Onboarding        ⋯    |
| LEBIH LAMA               |
| · Aturan lembur     ⋯    |
|        [muat lagi]       |
+--------------------------+
menu ⋯ : Ganti nama · Hapus
""",
       acceptance=("Percakapan hanya terlihat oleh pemiliknya (diuji dengan 2 akun)",
                   "Ganti nama & hapus bekerja dengan konfirmasi",
                   "Pencarian menemukan kata pada isi pesan, bukan hanya judul",
                   "Daftar memakai pagination, bukan memuat semuanya sekaligus"),
       evidence=(f"{P}/backend/app/api/conversations.py",
                 f"{P}/frontend/components/Sidebar.tsx"),
       depends_on=("INT-009", "INT-010"), source=_API),

    _t("INT-012", "System prompt terkelola + parameter generasi",
       "i1", priority="medium", estimate=1, labels=(*B, "llm"),
       description=(
           "System prompt tidak boleh tersebar di banyak tempat: simpan sebagai "
           "template berversi (`prompts/system.v1.md`) dengan placeholder "
           "{persona}, {tanggal}, {aturan_sitasi}, {ringkasan_memori}. Admin bisa "
           "mengubah suhu, max_tokens, dan memilih versi prompt aktif lewat "
           "endpoint pengaturan; perubahan tercatat di audit log sehingga "
           "perbedaan kualitas jawaban bisa ditelusuri ke versi prompt."),
       workflow=(
           _w("Admin", "Ubah versi prompt / suhu di halaman pengaturan",
              "PATCH /api/admin/settings tercatat di audit_log"),
           _w("Backend", "Saat menyusun request, render template + placeholder",
              "Prompt final konsisten untuk semua percakapan"),
           _w("Backend", "Simpan `prompt_version` pada setiap pesan assistant",
              "Analitik bisa membandingkan 👍/👎 antar versi prompt"),
       ),
       wireframe="""
prompts/system.v1.md
  Kamu adalah asisten internal {persona}. Hari ini {tanggal}.
  ATURAN:
  1. Jawab hanya dari konteks yang diberikan.
  2. Sertakan sitasi [n] untuk setiap klaim faktual.
  3. Bila konteks tidak memuat jawabannya, katakan tidak tahu.
  MEMORI PENGGUNA: {ringkasan_memori}

messages.prompt_version = "system.v1"   ← ikut tersimpan per jawaban
""",
       acceptance=("Prompt tersimpan sebagai berkas berversi, bukan string di kode",
                   "Admin bisa mengganti versi prompt & parameter tanpa deploy",
                   "Setiap pesan assistant menyimpan prompt_version",
                   "Perubahan pengaturan tercatat di audit log"),
       evidence=(f"{P}/backend/app/llm/prompts.py",
                 f"{P}/backend/app/prompts/system.v1.md"),
       depends_on=("INT-009",), source=_SPEC),

    # ================================================================== Fase 2
    _t("INT-013", "Ingest dokumen: upload, parser, dan status pemrosesan",
       "i2", priority="critical", estimate=2, labels=(*B, "rag"),
       description=(
           "`POST /api/documents/upload` menerima PDF/DOCX/MD/TXT (validasi tipe "
           "& ukuran maks 20 MB), menyimpan berkas asli, lalu memproses di "
           "background: parse structure-aware (heading berlevel, paragraf, tabel "
           "utuh) menjadi `structure.json`. Status dokumen bergerak "
           "`uploaded → parsing → chunking → embedding → ready | failed` dan bisa "
           "dipantau dari UI. PDF hasil scan (tanpa teks) ditolak dengan pesan "
           "yang jelas, bukan menghasilkan chunk kosong."),
       workflow=(
           _w("Pengguna", "Seret berkas ke area upload", "POST multipart, status=uploaded"),
           _w("Worker background", "Parse berkas sesuai tipe",
              "structure.json: [{type, level, text, page, hierarchy}]"),
           _w("Worker", "Pecah jadi chunk lalu hitung embedding",
              "Status berpindah chunking → embedding"),
           _w("Worker", "Selesai / gagal", "Status ready atau failed + alasan"),
           _w("UI", "Polling status tiap 2 dtk", "Progress bar per dokumen"),
       ),
       wireframe="""
HALAMAN DOKUMEN
+--------------------------------------------------------------+
|  ⬆  Seret berkas ke sini atau [pilih berkas]                 |
|     PDF, DOCX, MD, TXT · maks 20 MB                          |
+--------------------------------------------------------------+
| Nama              | Ukuran | Status                | Aksi    |
|-------------------|--------|-----------------------|---------|
| SOP-Cuti.pdf      | 1.2 MB | ✅ ready · 84 chunk    | 🗑 ⧉    |
| Panduan-HR.docx   | 3.4 MB | ⏳ embedding ▓▓▓░░ 60% | —       |
| Scan-Lama.pdf     | 8.1 MB | ❌ gagal: tidak ada    | 🗑      |
|                   |        |    teks (hasil scan)  |         |
+--------------------------------------------------------------+
""",
       acceptance=("PDF/DOCX/MD/TXT terparse jadi structure.json dengan hierarchy",
                   "Tabel tidak terpotong dan tetap satu elemen",
                   "Status dokumen terlihat bergerak sampai ready/failed",
                   "Berkas terlalu besar / tipe salah ditolak dengan pesan jelas",
                   "PDF hasil scan memberi pesan 'tidak ada lapisan teks'"),
       evidence=(f"{P}/backend/app/ingest/pipeline.py",
                 f"{P}/frontend/components/DocumentUploader.tsx",
                 f"{P}/backend/tests/test_ingest.py"),
       depends_on=("INT-004",), source=_SPEC),

    _t("INT-014", "Chunking structure-aware + embedding + vector store",
       "i2", priority="critical", estimate=2, labels=(*B, "rag"),
       description=(
           "Pecah struktur dokumen dengan menghormati batas semantik: tabel & "
           "daftar langkah selalu utuh, heading menempel pada paragraf "
           "pertamanya, sisanya sliding window ±400 token overlap 50. Embedding "
           "memakai all-MiniLM-L6-v2 (384 dim) dengan fallback hashing "
           "deterministik supaya test jalan offline. Simpan di Chroma persistent "
           "(fallback tabel SQLite + cosine) beserta metadata doc_id, page, "
           "hierarchy, type. Hapus dokumen → chunk & vektornya ikut terhapus."),
       workflow=(
           _w("Pipeline", "Terima structure.json", "Chunker menyusun potongan semantik"),
           _w("Chunker", "Tabel/daftar → satu chunk; teks panjang → sliding window",
              "Chunk + metadata hierarchy"),
           _w("Embedder", "Hitung vektor per chunk (batch 32)",
              "Vektor 384 dim, di-cache per hash isi"),
           _w("Vector store", "Upsert chunk+vektor+metadata",
              "Siap dicari; re-index otomatis saat dokumen diganti"),
       ),
       wireframe="""
BENTUK CHUNK
{ "id":"ch_0042", "doc_id":"doc_7", "page":4, "type":"paragraph",
  "hierarchy":["Kebijakan Cuti","Cuti Tahunan"],
  "text":"Karyawan tetap berhak 12 hari kerja…",
  "tokens":118, "vector":[0.013, -0.220, …384] }

ALUR: structure.json ─► chunker ─► embedder ─► store(Chroma|SQLite)
      hapus dokumen  ─────────────────────────► hapus chunk + vektor
""",
       acceptance=("Tabel besar tidak pernah terbelah antar chunk",
                   "Setiap chunk membawa hierarchy dan nomor halaman",
                   "Fallback embedding offline dipakai otomatis bila model tak ada",
                   "Menghapus dokumen membersihkan chunk & vektornya",
                   "Unit test chunking + store (tambah, cari, hapus) hijau"),
       evidence=(f"{P}/backend/app/rag/chunking.py",
                 f"{P}/backend/app/rag/store.py",
                 f"{P}/backend/tests/test_chunking.py"),
       depends_on=("INT-013",), source=_ARCH),

    _t("INT-015", "Retrieval berkualitas: top-k, threshold, MMR, re-rank",
       "i2", priority="critical", estimate=1.5, labels=(*B, "rag"),
       description=(
           "`POST /api/rag/query` mengembalikan chunk relevan beserta skor. "
           "Kualitas dijaga dengan: top-k awal 20 → MMR untuk keberagaman → "
           "re-rank sederhana (cross-encoder bila tersedia, kalau tidak skor "
           "gabungan cosine + kecocokan kata kunci) → ambil 5 teratas → buang "
           "yang di bawah threshold. Bila hasil kosong, kembalikan daftar kosong "
           "secara eksplisit supaya agent menjawab 'tidak tahu', bukan mengarang."),
       workflow=(
           _w("Agent/UI", "Kirim pertanyaan + filter dokumen (opsional)",
              "POST /api/rag/query"),
           _w("Retriever", "Embed pertanyaan → cari 20 kandidat terdekat",
              "Kandidat + skor cosine"),
           _w("Retriever", "MMR (λ=0.7) buang kandidat yang saling duplikat",
              "Kandidat beragam"),
           _w("Re-ranker", "Urutkan ulang berdasar relevansi, ambil 5 teratas",
              "Konteks final"),
           _w("Retriever", "Buang skor < threshold (0.35)",
              "Kosong → sinyal 'tidak ada dasar jawaban'"),
       ),
       wireframe="""
PIPELINE RETRIEVAL
 pertanyaan ─► embed ─► top-20 ─► MMR(λ=0.7) ─► re-rank ─► top-5 ─► ≥0.35?
                                                                     │
                                          ya ─► konteks + sitasi ────┘
                                          tidak ─► [] → agent jawab "tidak tahu"

respons: {"hits":[{"chunk_id","doc","page","hierarchy","score","text"}],
          "took_ms":38, "filtered_by_threshold":3}
""",
       acceptance=("Pertanyaan di luar dokumen mengembalikan hasil kosong, bukan chunk asal",
                   "MMR terbukti mengurangi chunk duplikat (diuji)",
                   "Threshold & top-k bisa diatur lewat konfigurasi",
                   "Waktu query p95 < 300 ms untuk 5.000 chunk",
                   "Respons memuat skor sehingga bisa di-debug"),
       evidence=(f"{P}/backend/app/rag/retriever.py",
                 f"{P}/backend/tests/test_retriever.py"),
       depends_on=("INT-014",), source=_ARCH),

    _t("INT-016", "Agent loop (ReAct) + tool registry + batas iterasi",
       "i2", priority="critical", estimate=2.5, labels=(*B, "agent"),
       description=(
           "Inti produk: loop agent yang memutuskan sendiri kapan memakai tool. "
           "`ToolRegistry` mendaftarkan tool dengan JSON Schema parameter, "
           "deskripsi, dan izin peran. Loop: LLM → (tool call?) → jalankan tool "
           "→ masukkan hasil → ulangi. Batas keras: maks 5 iterasi, maks 30 detik, "
           "maks 3 pemanggilan tool yang sama, dan setiap tool punya timeout "
           "sendiri. Semua langkah dicatat sebagai `trace` yang bisa dilihat di UI "
           "dan disimpan bersama pesan untuk audit."),
       workflow=(
           _w("Pengguna", "Ajukan pertanyaan", "Agent menerima pesan + riwayat + memori"),
           _w("Agent", "Minta keputusan ke LLM beserta daftar tool",
              "LLM membalas jawaban ATAU permintaan tool"),
           _w("Agent", "Validasi argumen tool terhadap JSON Schema",
              "Argumen tidak valid → hasil error dikembalikan ke LLM untuk diperbaiki"),
           _w("Agent", "Jalankan tool dengan timeout, catat durasi",
              "Hasil tool masuk ke konteks + event SSE `tool`"),
           _w("Agent", "Ulangi sampai LLM menjawab atau batas tercapai",
              "Batas tercapai → jawab dengan info terbaik + catatan keterbatasan"),
           _w("Agent", "Simpan trace lengkap bersama pesan", "Bisa diaudit ulang"),
       ),
       wireframe="""
SIKLUS AGENT (maks 5 iterasi / 30 dtk)
   ┌──────────────────────────────────────────┐
   │  pesan + riwayat + memori + daftar tool  │
   └───────────────┬──────────────────────────┘
                   v
              [ LLM berpikir ]
                   │
        jawab ◄────┴────► panggil tool
          │                   │
          │        validasi schema → jalankan (timeout 10s)
          │                   │
          │              hasil tool ──┐
          v                           │
      jawaban final  ◄────────────────┘ (ulang, maks 5x)

TRACE tersimpan:
 [{"i":1,"thought":"perlu cari SOP","tool":"retrieve_knowledge",
   "args":{"q":"cuti tahunan"},"ms":42,"ok":true}, …]
""",
       acceptance=("Agent memakai tool hanya bila perlu (pertanyaan sapaan tidak memicu retrieval)",
                   "Batas iterasi/waktu/pengulangan tool benar-benar berlaku & diuji",
                   "Argumen tool divalidasi; argumen salah tidak membuat server error",
                   "Trace tersimpan dan bisa ditampilkan ulang untuk pesan lama",
                   "Loop diuji dengan provider palsu yang men-skenario-kan tool call"),
       evidence=(f"{P}/backend/app/agent/loop.py",
                 f"{P}/backend/app/agent/registry.py",
                 f"{P}/backend/tests/test_agent_loop.py"),
       depends_on=("INT-008", "INT-015"), source=REF["agent"]),

    _t("INT-017", "Tool retrieve_knowledge + jawaban tergrounding & sitasi",
       "i2", priority="critical", estimate=1.5, labels=(*B, "agent", "rag"),
       description=(
           "Tool utama yang menyambungkan agent ke dokumen. Prompt grounded "
           "mewajibkan: jawab hanya dari konteks, beri nomor sitasi [n] pada "
           "setiap klaim, dan katakan tidak tahu bila konteks tidak memadai. "
           "Setelah jawaban selesai, verifikasi sitasi: nomor yang tidak merujuk "
           "chunk nyata ditandai `unverified`, dan rasio kalimat bersitasi dicatat "
           "sebagai metrik grounding per jawaban."),
       workflow=(
           _w("Agent", "Panggil retrieve_knowledge(query, doc_ids?)",
              "Konteks 5 chunk + daftar sitasi bernomor"),
           _w("Agent", "Susun prompt grounded berisi konteks bernomor",
              "LLM menjawab dengan penanda [1], [2]"),
           _w("Verifier", "Cocokkan tiap [n] dengan chunk yang benar-benar dikirim",
              "Sitasi liar ditandai unverified"),
           _w("Backend", "Simpan message_citations + skor grounding",
              "UI bisa menampilkan sumber yang bisa diklik"),
           _w("UI", "Klik [1]", "Panel sumber terbuka pada kutipan yang disorot"),
       ),
       wireframe="""
JAWABAN + SUMBER
+--------------------------------------------------------------+
| 🤖 Cuti tahunan adalah 12 hari kerja per tahun [1] dan hangus |
|    bila tidak diambil sampai 31 Maret tahun berikutnya [2].   |
|    ─────────────────────────────────────────────────────────  |
|    Sumber                                                     |
|    [1] SOP-Cuti.pdf · hal. 4 · Kebijakan Cuti › Cuti Tahunan  |
|    [2] SOP-Cuti.pdf · hal. 5 · … › Kedaluwarsa                |
|    grounding 100% · 2/2 kalimat faktual bersitasi             |
+--------------------------------------------------------------+
klik [1] ▸ panel kanan menampilkan chunk penuh dengan sorotan
""",
       acceptance=("Pertanyaan di luar dokumen dijawab 'tidak tahu', bukan karangan",
                   "Setiap klaim faktual membawa sitasi yang bisa diklik",
                   "Sitasi yang tidak cocok dengan konteks ditandai unverified",
                   "Skor grounding tersimpan per jawaban",
                   "Sitasi tetap benar saat percakapan lama dibuka kembali"),
       evidence=(f"{P}/backend/app/tools/retrieve_knowledge.py",
                 f"{P}/backend/app/agent/citations.py",
                 f"{P}/frontend/components/CitationPanel.tsx"),
       depends_on=("INT-016",), source=_SUCCESS),

    _t("INT-018", "Tool tambahan: kalkulator, waktu, dan pencarian web (opsional)",
       "i2", priority="medium", estimate=1, labels=(*B, "agent"),
       description=(
           "Buktikan registry tool benar-benar generik dengan menambah tool "
           "kedua & ketiga tanpa menyentuh loop: `calculator` (ekspresi aman, "
           "tanpa eval Python), `current_time` (zona waktu Asia/Jakarta), dan "
           "`web_search` yang dimatikan secara default lewat feature flag serta "
           "hanya boleh dipakai peran tertentu. Tool web wajib punya domain "
           "allowlist dan timeout ketat."),
       workflow=(
           _w("Developer", "Daftarkan tool baru ke registry dengan schema",
              "Tool otomatis muncul di daftar yang dikirim ke LLM"),
           _w("Agent", "Panggil calculator('12*7.5')",
              "Parser aman mengevaluasi; ekspresi berbahaya ditolak"),
           _w("Admin", "Nyalakan web_search lewat feature flag",
              "Hanya peran yang diizinkan bisa memicunya"),
       ),
       wireframe="""
REGISTRY
 name: calculator
 desc: "Hitung ekspresi aritmetika sederhana."
 schema: {"expression": {"type":"string","maxLength":200}}
 roles: ["user","admin"]   enabled: true   timeout: 2s

 name: web_search
 roles: ["admin"]          enabled: false  timeout: 8s
 allowlist: ["*.go.id", "wikipedia.org"]
""",
       acceptance=("Menambah tool tidak mengubah kode agent loop sama sekali",
                   "Calculator menolak ekspresi berbahaya (tanpa eval)",
                   "web_search mati secara default dan dibatasi peran + allowlist",
                   "Setiap tool punya timeout dan tercatat di trace"),
       evidence=(f"{P}/backend/app/tools/calculator.py",
                 f"{P}/backend/tests/test_tools.py"),
       depends_on=("INT-016",), source=REF["tools"]),

    _t("INT-019", "Guardrail input & output: PII, prompt injection, topik terlarang",
       "i2", priority="high", estimate=1.5, labels=(*B, "security"),
       description=(
           "Lapisan keamanan konten di dua sisi. Input: tolak/pangkas pesan "
           "terlalu panjang, deteksi pola prompt injection ('abaikan instruksi "
           "sebelumnya', 'tampilkan system prompt') dan tandai, serta masker PII "
           "(NIK, nomor rekening, email) sebelum dikirim ke provider eksternal. "
           "Output: cegah kebocoran system prompt & kunci API, saring topik "
           "terlarang sesuai kebijakan, dan selalu beri jalan keluar sopan. "
           "Semua blokir dicatat ke audit log untuk ditinjau admin."),
       workflow=(
           _w("Pengguna", "Kirim pesan", "Guardrail input memeriksa panjang & pola"),
           _w("Guardrail input", "Deteksi injeksi → tandai & netralkan",
              "Instruksi berbahaya tidak diperlakukan sebagai perintah sistem"),
           _w("Guardrail input", "Masker PII sebelum keluar ke provider",
              "Log menyimpan versi termasker saja"),
           _w("Guardrail output", "Periksa jawaban sebelum dikirim ke UI",
              "Kebocoran prompt/kunci diblokir, diganti pesan aman"),
           _w("Backend", "Catat kejadian blokir", "Admin bisa meninjau di audit log"),
       ),
       wireframe="""
DUA GERBANG
  pesan user ─► [guard IN] ─► agent ─► [guard OUT] ─► pengguna
                  │                        │
                  ├ panjang > batas        ├ bocor system prompt
                  ├ pola injeksi           ├ kunci API / kredensial
                  └ PII → masker           └ topik terlarang
                            │                        │
                            └────── audit_log ───────┘

contoh masker:  "NIK saya 3204xxxxxxxxxx" → "NIK saya [PII:NIK]"
""",
       acceptance=("Pesan berisi upaya injeksi tidak membuat agent membocorkan system prompt",
                   "PII termasker sebelum dikirim ke provider eksternal (diuji)",
                   "Jawaban yang memuat kredensial diblokir sebelum sampai ke UI",
                   "Setiap blokir tercatat di audit log dengan alasan",
                   "Guardrail punya test untuk tiap pola yang didukung"),
       evidence=(f"{P}/backend/app/safety/guardrails.py",
                 f"{P}/backend/tests/test_guardrails.py"),
       depends_on=("INT-016",), source=_SPEC),

    # ================================================================== Fase 3
    _t("INT-020", "Manajemen jendela konteks & penghitungan token",
       "i3", priority="critical", estimate=1.5, labels=(*B, "memory"),
       description=(
           "Tidak boleh ada request yang meledak karena konteks kepanjangan. "
           "Buat `ContextBuilder` yang menyusun prompt dengan anggaran token "
           "eksplisit: system (±800) + memori (±400) + konteks RAG (±2.000) + "
           "riwayat (sisa) + ruang jawaban (1.000). Hitung token dengan tiktoken "
           "(fallback estimasi 4 karakter/token). Bila melebihi, pangkas dari "
           "pesan terlama, jangan pernah memotong system prompt atau pesan "
           "terakhir pengguna."),
       workflow=(
           _w("ContextBuilder", "Hitung token tiap bagian dengan tokenizer",
              "Anggaran terpakai diketahui sebelum request"),
           _w("ContextBuilder", "Bila melebihi, buang pesan terlama berpasangan",
              "Riwayat mengecil, makna percakapan terjaga"),
           _w("ContextBuilder", "Bila masih lebih, pangkas konteks RAG skor terendah",
              "System prompt & pesan terakhir selalu utuh"),
           _w("Backend", "Catat komposisi token per request",
              "Bisa dianalisis: berapa token habis untuk RAG vs riwayat"),
       ),
       wireframe="""
ANGGARAN KONTEKS (model 8k)
 ┌─────────────────────────────────────────────────────────┐
 │ system 800 │ memori 400 │ RAG 2000 │ riwayat 3800 │ out │
 └─────────────────────────────────────────────────────────┘
 melebihi? urutan pemangkasan:
   1. pesan riwayat terlama (berpasangan user+assistant)
   2. chunk RAG dengan skor terendah
   3. ringkasan memori dipendekkan
   ✗ system prompt & pesan terakhir user TIDAK PERNAH dipangkas

log: {"budget":8000,"system":760,"memory":318,"rag":1840,
      "history":2210,"reserved_out":1000,"trimmed_msgs":4}
""",
       acceptance=("Percakapan 100 pesan tidak pernah melebihi batas konteks model",
                   "System prompt & pesan terakhir user tidak pernah terpangkas",
                   "Komposisi token tercatat per request",
                   "Penghitung token punya fallback saat tiktoken tidak tersedia",
                   "Ada test dengan percakapan panjang buatan"),
       evidence=(f"{P}/backend/app/memory/context.py",
                 f"{P}/backend/app/llm/tokens.py",
                 f"{P}/backend/tests/test_context_budget.py"),
       depends_on=("INT-009",), source=_ARCH),

    _t("INT-021", "Ringkasan percakapan otomatis (memori jangka menengah)",
       "i3", priority="high", estimate=1.5, labels=(*B, "memory"),
       description=(
           "Agar percakapan panjang tetap nyambung tanpa mengirim semua riwayat: "
           "setiap 10 pesan (atau saat riwayat melewati 60% anggaran), jalankan "
           "peringkasan di background yang memadatkan pesan lama menjadi "
           "ringkasan ≤200 token berisi fakta, keputusan, dan preferensi. "
           "Ringkasan disimpan per percakapan, diperbarui inkremental (ringkasan "
           "lama + pesan baru → ringkasan baru), dan bisa dilihat pengguna."),
       workflow=(
           _w("Backend", "Setelah pesan ke-10 (kelipatan), antrekan peringkasan",
              "Tugas background tidak memperlambat jawaban"),
           _w("Summarizer", "Kirim ringkasan lama + 10 pesan terakhir ke LLM",
              "Ringkasan baru ≤200 token"),
           _w("Backend", "Simpan ke conversations.summary + versi",
              "Pesan lama boleh dikeluarkan dari jendela konteks"),
           _w("ContextBuilder", "Sisipkan ringkasan sebagai pesan system tambahan",
              "Agent tetap ingat konteks awal percakapan"),
           _w("Pengguna", "Buka 'Apa yang diingat?'", "Ringkasan tampil & bisa dihapus"),
       ),
       wireframe="""
PEMADATAN RIWAYAT
  pesan 1..10  ─┐
  pesan 11..20 ─┼─► [summarizer] ─► ringkasan v3 (≤200 token)
  ringkasan v2 ─┘

konteks yang dikirim:
  [system] [ringkasan v3] [pesan 21..30 utuh] [pertanyaan baru]

PANEL "APA YANG DIINGAT?"
+------------------------------------------+
| Ringkasan percakapan          v3 · 14:22 |
| • User menanyakan kebijakan cuti         |
| • Sudah dijelaskan 12 hari & kedaluwarsa |
| • User bekerja di cabang Bandung         |
|                       [perbarui] [hapus] |
+------------------------------------------+
""",
       acceptance=("Percakapan 50 pesan tetap menjawab konsisten soal hal di pesan awal",
                   "Peringkasan berjalan di background, tidak menunda jawaban",
                   "Ringkasan diperbarui inkremental, bukan menghitung ulang semua",
                   "Pengguna bisa melihat & menghapus ringkasan percakapannya",
                   "Ada test yang memverifikasi ringkasan ikut ke dalam konteks"),
       evidence=(f"{P}/backend/app/memory/summarizer.py",
                 f"{P}/backend/tests/test_summarizer.py"),
       depends_on=("INT-020",), source=REF["memory"]),

    _t("INT-022", "Memori jangka panjang per pengguna (fakta & preferensi)",
       "i3", priority="high", estimate=2, labels=(*B, "memory"),
       description=(
           "Chatbot yang terasa personal: ekstrak fakta tahan lama dari "
           "percakapan (jabatan, lokasi kerja, preferensi bahasa/gaya jawaban, "
           "proyek yang sedang dikerjakan) ke tabel `memories` {user_id, kind, "
           "key, value, confidence, source_message_id, created_at}. Saat "
           "percakapan baru, ambil memori paling relevan (embedding + kebaruan) "
           "maksimal 400 token. Wajib bisa dikendalikan pengguna: lihat, edit, "
           "hapus satu per satu, hapus semua, dan matikan fitur memori."),
       workflow=(
           _w("Extractor", "Setelah jawaban selesai, periksa pesan user",
              "Kandidat fakta + confidence"),
           _w("Backend", "Deduplikasi terhadap memori yang ada (key sama)",
              "Nilai diperbarui, bukan bertumpuk"),
           _w("Retriever memori", "Saat percakapan baru, ambil top-5 memori relevan",
              "Disisipkan ke system prompt (≤400 token)"),
           _w("Pengguna", "Buka Pengaturan → Memori",
              "Daftar memori bisa diedit/dihapus; ada tombol hapus semua"),
           _w("Pengguna", "Matikan memori", "Ekstraksi & penyisipan berhenti seketika"),
       ),
       wireframe="""
PENGATURAN › MEMORI
+--------------------------------------------------------------+
| Memori membantu asisten mengingat hal penting tentang Anda.  |
| Aktifkan memori  [ ●—— ]                                     |
|--------------------------------------------------------------|
| Jenis     | Isi                              | Dari    |     |
| profil    | Bekerja di cabang Bandung        | 12 Sep  | ✎ 🗑 |
| preferensi| Suka jawaban ringkas & poin-poin | 14 Sep  | ✎ 🗑 |
| proyek    | Sedang menyiapkan audit ISO      | 19 Sep  | ✎ 🗑 |
|--------------------------------------------------------------|
|                                    [ Hapus semua memori ]    |
+--------------------------------------------------------------+
""",
       acceptance=("Fakta yang disebut di percakapan A terpakai di percakapan B",
                   "Memori duplikat tidak bertumpuk (key sama → diperbarui)",
                   "Pengguna bisa melihat, mengedit, dan menghapus memorinya",
                   "Mematikan memori benar-benar menghentikan ekstraksi & penyisipan",
                   "Memori satu pengguna tidak pernah bocor ke pengguna lain (diuji)"),
       evidence=(f"{P}/backend/app/memory/long_term.py",
                 f"{P}/frontend/components/MemorySettings.tsx",
                 f"{P}/backend/tests/test_memory.py"),
       depends_on=("INT-021",), source=REF["memory"]),

    _t("INT-023", "Privasi memori: retensi, ekspor, dan hapus akun",
       "i3", priority="medium", estimate=1, labels=(*B, "security"),
       description=(
           "Kewajiban privasi yang sering dilupakan prototipe: kebijakan retensi "
           "(percakapan & memori lebih tua dari N hari dihapus otomatis lewat job "
           "harian, N dapat dikonfigurasi), ekspor data pribadi (semua percakapan, "
           "memori, feedback → satu berkas JSON), dan penghapusan akun yang "
           "benar-benar menghapus/menganonimkan seluruh jejak. Tulis juga halaman "
           "kebijakan privasi singkat di dalam aplikasi."),
       workflow=(
           _w("Job harian", "Cari data melebihi masa retensi", "Hapus permanen + catat jumlah"),
           _w("Pengguna", "Klik 'Unduh data saya'",
              "Backend menyusun JSON lengkap → unduhan"),
           _w("Pengguna", "Klik 'Hapus akun' + konfirmasi ketik ulang username",
              "Semua percakapan/memori/feedback dihapus, akun dinonaktifkan"),
           _w("Backend", "Catat aksi ke audit log (tanpa isi data pribadi)",
              "Bisa dibuktikan saat audit"),
       ),
       wireframe="""
PENGATURAN › PRIVASI
+--------------------------------------------------------------+
| Retensi data     : percakapan disimpan 180 hari              |
| Unduh data saya  [ ⬇ Ekspor JSON ]                            |
|--------------------------------------------------------------|
| Zona berbahaya                                               |
| Menghapus akun menghapus semua percakapan & memori Anda.     |
| Ketik ulang username untuk konfirmasi: [__________]          |
|                                        [ Hapus akun saya ]   |
+--------------------------------------------------------------+
""",
       acceptance=("Job retensi berjalan terjadwal dan idempoten",
                   "Ekspor memuat percakapan, memori, dan feedback pengguna",
                   "Hapus akun menghilangkan seluruh data pribadi (diverifikasi test)",
                   "Halaman kebijakan privasi tersedia di aplikasi"),
       evidence=(f"{P}/backend/app/privacy.py",
                 f"{P}/backend/tests/test_privacy.py"),
       depends_on=("INT-022",), source=_SPEC),

    # ================================================================== Fase 4
    _t("INT-024", "Akuntansi token & biaya per pesan, percakapan, pengguna",
       "i4", priority="critical", estimate=1.5, labels=(*B, "quota"),
       description=(
           "Setiap panggilan LLM dicatat: prompt_tokens, completion_tokens, "
           "model, provider, latensi, dan biaya (dihitung dari tabel harga per "
           "1K token yang dikonfigurasi). Simpan per pesan dan diagregasi harian "
           "per pengguna di tabel `token_usage` (unik per user+tanggal) supaya "
           "kueri kuota murah. Jika provider tidak mengembalikan usage, hitung "
           "sendiri dengan tokenizer. Sediakan `GET /api/usage/me` dan agregat "
           "admin per hari/pengguna/model."),
       workflow=(
           _w("Agent", "Selesai memanggil LLM", "Dapat usage dari provider / hitung sendiri"),
           _w("Accountant", "Simpan baris usage per pesan + hitung biaya",
              "messages.prompt_tokens, completion_tokens, cost"),
           _w("Accountant", "UPSERT agregat harian user",
              "token_usage(user_id, date) bertambah atomik"),
           _w("Pengguna", "Buka halaman pemakaian", "Grafik 30 hari + sisa kuota"),
           _w("Admin", "Buka analitik", "Biaya per pengguna & per model"),
       ),
       wireframe="""
HALAMAN PEMAKAIAN SAYA
+--------------------------------------------------------------+
| Hari ini      12.480 / 50.000 token   ▓▓▓▓▓░░░░░░░░░  25%    |
| Reset pukul 00:00 WIB                                        |
|--------------------------------------------------------------|
| 30 hari terakhir                                             |
|  ▁▂▅▃▇▂▁▄▆▃▂▁▅▇▄▂▃▁▂▄▆▅▃▂▁▄▂▃▅                               |
| Total bulan ini : 384.120 token · estimasi biaya Rp 96.000   |
| Percakapan termahal: "Audit ISO" · 42.300 token              |
+--------------------------------------------------------------+
""",
       acceptance=("Setiap pesan assistant menyimpan prompt & completion token",
                   "Agregat harian akurat dibanding jumlah per pesan (diuji)",
                   "Biaya dihitung dari tabel harga yang bisa dikonfigurasi",
                   "Provider tanpa usage tetap menghasilkan angka (hitung sendiri)",
                   "GET /api/usage/me mengembalikan pemakaian & sisa kuota"),
       evidence=(f"{P}/backend/app/billing/usage.py",
                 f"{P}/backend/tests/test_usage.py"),
       depends_on=("INT-020",), source=_API),

    _t("INT-025", "Kuota & rate limit per pengguna (harian, bulanan, per menit)",
       "i4", priority="critical", estimate=2, labels=(*B, "quota"),
       description=(
           "Kebijakan kuota bertingkat yang ditegakkan SEBELUM memanggil LLM: "
           "batas token harian & bulanan per peran (mis. user 50k/hari, admin "
           "tanpa batas), batas pesan per menit (anti-spam, token bucket), dan "
           "batas token per satu permintaan. Saat kuota hampir habis (80%) UI "
           "memberi peringatan; saat habis, request ditolak 429 dengan pesan "
           "jelas + waktu reset. Admin bisa mengatur kebijakan dan memberi "
           "kuota tambahan sekali pakai ke pengguna tertentu."),
       workflow=(
           _w("Pengguna", "Kirim pesan", "Middleware kuota dijalankan lebih dulu"),
           _w("Quota guard", "Estimasi token permintaan + cek sisa harian/bulanan",
              "Cukup → lanjut; tidak cukup → 429 quota_exceeded"),
           _w("Quota guard", "Cek token bucket per menit",
              "Melebihi → 429 rate_limited + Retry-After"),
           _w("UI", "Terima 429", "Banner jelas: batas harian tercapai, reset 00:00"),
           _w("Admin", "Tambah kuota sekali pakai untuk user",
              "Grant tercatat di audit log dan langsung berlaku"),
       ),
       wireframe="""
GERBANG SEBELUM LLM
  pesan ─► [rate limit/menit] ─► [kuota harian] ─► [kuota bulanan] ─► LLM
              │ lewat                 │ habis            │ habis
              v                       v                  v
          429 rate_limited     429 quota_exceeded  429 quota_exceeded
          Retry-After: 30      reset_at: 00:00     reset_at: 1 Okt

UI SAAT 80%
+--------------------------------------------------------------+
| ⚠ Sisa kuota Anda 20% (10.000 token). Reset 00:00 WIB.       |
+--------------------------------------------------------------+
UI SAAT HABIS — composer dinonaktifkan + tombol "Minta tambahan"
""",
       acceptance=("Permintaan melebihi kuota ditolak 429 SEBELUM token terpakai",
                   "Batas per menit, harian, dan bulanan semuanya berlaku & diuji",
                   "UI memperingatkan di 80% dan menonaktifkan composer saat habis",
                   "Admin bisa mengubah kebijakan per peran & memberi kuota tambahan",
                   "Kuota tidak bisa ditembus dengan request paralel (diuji bersamaan)"),
       evidence=(f"{P}/backend/app/billing/quota.py",
                 f"{P}/backend/tests/test_quota.py",
                 f"{P}/frontend/components/QuotaBanner.tsx"),
       depends_on=("INT-024",), source=_API),

    _t("INT-026", "Feedback 👍/👎 per jawaban + alasan terstruktur",
       "i4", priority="critical", estimate=1.5, labels=(*_L, "fullstack", "feedback"),
       description=(
           "Mekanisme kualitas yang jadi bahan bakar perbaikan. Setiap jawaban "
           "assistant punya tombol 👍/👎 (satu penilaian per pengguna per pesan, "
           "bisa diubah atau dibatalkan). 👎 membuka dialog alasan terstruktur: "
           "'tidak akurat', 'tidak relevan', 'sumber salah', 'terlalu panjang', "
           "'bahasa/nada', 'lainnya' + catatan bebas (opsional, maks 500 "
           "karakter). Simpan bersama snapshot konteks: message_id, model, "
           "prompt_version, daftar chunk yang dipakai, dan trace tool — supaya "
           "kasus buruk bisa direproduksi, bukan sekadar angka."),
       workflow=(
           _w("Pengguna", "Klik 👍", "POST /api/feedback {rating:+1}; ikon terisi seketika"),
           _w("Pengguna", "Klik 👎", "Dialog alasan terbuka"),
           _w("Pengguna", "Pilih alasan + catatan lalu kirim",
              "POST /api/feedback {rating:-1, reason, note}"),
           _w("Backend", "UPSERT unik (user_id, message_id)",
              "Penilaian bisa diubah, tidak menggandakan baris"),
           _w("Backend", "Lampirkan snapshot: model, prompt_version, chunk, trace",
              "Kasus bisa direproduksi persis oleh tim"),
           _w("UI", "Tampilkan konfirmasi halus 'Terima kasih atas masukannya'",
              "Tidak mengganggu alur membaca"),
       ),
       wireframe="""
DI BAWAH SETIAP JAWABAN
   👍  👎   ⧉ salin   ⟲ jawab ulang

DIALOG SETELAH 👎
+--------------------------------------------------+
|  Apa yang kurang tepat?                      [×] |
|  ( ) Tidak akurat / salah fakta                  |
|  ( ) Tidak relevan dengan pertanyaan             |
|  ( ) Sumber/sitasi salah                         |
|  ( ) Terlalu panjang atau bertele-tele           |
|  ( ) Bahasa atau nada tidak sesuai               |
|  ( ) Lainnya                                     |
|  Catatan (opsional)                              |
|  [____________________________________]  0/500   |
|                        [Batal]  [Kirim masukan]  |
+--------------------------------------------------+

TERSIMPAN
 feedback{user_id, message_id, rating:-1, reason:"sumber_salah",
          note:"…", model, prompt_version, chunk_ids[], trace_ref,
          created_at}   UNIQUE(user_id, message_id)
""",
       acceptance=("Satu pengguna hanya punya satu penilaian per pesan (bisa diubah/dibatalkan)",
                   "👎 selalu menawarkan alasan terstruktur + catatan opsional",
                   "Snapshot model, prompt_version, chunk, dan trace ikut tersimpan",
                   "Penilaian tetap terlihat saat percakapan lama dibuka kembali",
                   "Aksi feedback tidak pernah memblokir atau mereset tampilan chat",
                   "Ada test API (buat, ubah, batalkan) dan test komponen tombol"),
       evidence=(f"{P}/backend/app/api/feedback.py",
                 f"{P}/backend/tests/test_feedback.py",
                 f"{P}/frontend/components/FeedbackButtons.tsx"),
       depends_on=("INT-017",), source=REF["feedback"]),

    _t("INT-027", "Dasbor analitik kualitas: CSAT, jawaban buruk, biaya",
       "i4", priority="high", estimate=2, labels=(*_L, "admin", "feedback"),
       description=(
           "Halaman admin yang mengubah feedback jadi keputusan: skor kepuasan "
           "(👍 / total) harian & 7-hari, sebaran alasan 👎, daftar jawaban "
           "berperingkat buruk yang bisa dibuka lengkap dengan pertanyaan, "
           "jawaban, sumber, dan trace tool, serta perbandingan CSAT antar versi "
           "prompt/model. Tambahkan metrik operasional: p50/p95 latensi, rasio "
           "jawaban 'tidak tahu', dan biaya token per hari. Semua bisa difilter "
           "rentang tanggal dan diekspor CSV."),
       workflow=(
           _w("Admin", "Buka /admin/analytics", "Ringkasan 7 hari dimuat"),
           _w("Admin", "Ubah rentang tanggal / filter model",
              "Grafik & tabel dihitung ulang dari agregat"),
           _w("Admin", "Klik satu baris jawaban buruk",
              "Drawer menampilkan Q&A, sumber, trace, dan catatan pengguna"),
           _w("Admin", "Tandai 'sudah ditindaklanjuti' + catatan",
              "Status triase tersimpan supaya tidak ditinjau dua kali"),
           _w("Admin", "Ekspor CSV", "Berkas untuk dianalisis lebih lanjut"),
       ),
       wireframe="""
ADMIN › ANALITIK KUALITAS          [7 hari ▾] [semua model ▾] [⬇ CSV]
+--------------------------------------------------------------+
| CSAT 78%   👍 312  👎 88   | p95 1.8s | tidak tahu 9% | Rp412k |
+--------------------------------------------------------------+
| Tren CSAT                     Alasan 👎                       |
|  ▁▃▄▆▅▇▆                      tidak akurat   ▓▓▓▓▓▓▓▓ 41%     |
|                               sumber salah   ▓▓▓▓▓ 26%        |
|                               tidak relevan  ▓▓▓ 18%          |
+--------------------------------------------------------------+
| JAWABAN BERPERINGKAT BURUK                                   |
| Waktu  | Pertanyaan          | Alasan       | Model | Status  |
| 09:12  | Berapa uang lembur? | tidak akurat | 4o-mini | 🔴 baru|
| 11:40  | Syarat klaim rawat  | sumber salah | 4o-mini | ✅ beres|
|            ▸ klik baris → drawer: Q&A + sumber + trace        |
+--------------------------------------------------------------+
""",
       acceptance=("CSAT & sebaran alasan dihitung benar (dibandingkan data uji)",
                   "Daftar jawaban buruk bisa dibuka lengkap dengan trace & sumber",
                   "Perbandingan CSAT antar versi prompt/model tersedia",
                   "Metrik latensi p50/p95, rasio 'tidak tahu', dan biaya tampil",
                   "Filter tanggal dan ekspor CSV berfungsi",
                   "Halaman hanya bisa diakses admin (user biasa 403)"),
       evidence=(f"{P}/backend/app/api/analytics.py",
                 f"{P}/frontend/app/admin/analytics/page.tsx"),
       depends_on=("INT-026", "INT-024"), source=_SUCCESS),

    _t("INT-028", "Regenerate, edit pertanyaan, dan set evaluasi dari feedback",
       "i4", priority="medium", estimate=1.5, labels=(*_L, "fullstack"),
       description=(
           "Tutup lingkaran umpan balik. Di UI: tombol 'Jawab ulang' (regenerate) "
           "dan 'Edit pertanyaan' yang membuat cabang jawaban baru tanpa "
           "menghapus yang lama, sehingga pengguna bisa membandingkan. Di sisi "
           "tim: setiap jawaban 👎 yang sudah ditriase bisa dipromosikan menjadi "
           "kasus uji di `evals/dataset.jsonl` (pertanyaan, jawaban ideal, "
           "dokumen sumber). Skrip `scripts/eval.py` menjalankan seluruh dataset "
           "dan melaporkan skor grounding, kecocokan sumber, dan regresi terhadap "
           "baseline."),
       workflow=(
           _w("Pengguna", "Klik 'Jawab ulang'",
              "Jawaban baru dibuat sebagai varian, yang lama tetap bisa dilihat"),
           _w("Admin", "Dari analitik, klik 'Jadikan kasus uji'",
              "Baris baru ditambahkan ke evals/dataset.jsonl"),
           _w("Developer", "Jalankan scripts/eval.py sebelum rilis",
              "Laporan skor + daftar kasus yang memburuk"),
           _w("CI", "Jalankan eval ringkas pada MR yang menyentuh prompt/agent",
              "Regresi kualitas ketahuan sebelum merge"),
       ),
       wireframe="""
VARIAN JAWABAN
  🤖 Jawaban A (14:02)  👍 👎      ‹ 1/2 ›
  🤖 Jawaban B (14:03)  👍 👎   ← hasil "jawab ulang"

evals/dataset.jsonl
 {"q":"Berapa hari cuti tahunan?",
  "expect_contains":["12 hari kerja"],
  "expect_source":"SOP-Cuti.pdf#p4",
  "from_feedback":"fb_2291"}

laporan: grounding 0.86 (+0.04) · sumber tepat 0.91 · regresi: 2 kasus
""",
       acceptance=("Jawab ulang membuat varian tanpa menghapus jawaban sebelumnya",
                   "Edit pertanyaan membuat cabang baru yang bisa dibandingkan",
                   "Jawaban 👎 bisa dipromosikan jadi kasus uji satu klik",
                   "scripts/eval.py melaporkan skor & regresi terhadap baseline",
                   "Dataset evaluasi punya minimal 20 kasus nyata"),
       evidence=(f"{P}/scripts/eval.py", f"{P}/evals/dataset.jsonl"),
       depends_on=("INT-027",), source=_SUCCESS),

    # ================================================================== Fase 5
    _t("INT-029", "Observability: log terstruktur, metrik, dan trace request",
       "i5", priority="high", estimate=1.5, labels=(*B, "ops"),
       description=(
           "Saat produksi bermasalah, tim harus bisa menjawab 'apa yang terjadi "
           "pada request jam 09:12' dalam hitungan menit. Sediakan: log JSON "
           "berkorelasi `request_id`+`conversation_id`, endpoint `/metrics` "
           "(Prometheus) berisi jumlah request, latensi histogram, token "
           "terpakai, error per tipe, dan tool per nama, serta trace per "
           "percakapan yang bisa dibuka admin. Pastikan log TIDAK memuat isi "
           "pesan pengguna secara utuh (hanya panjang & hash) demi privasi."),
       workflow=(
           _w("Backend", "Setiap request menghasilkan log terkorelasi",
              "Bisa dicari dengan satu request_id"),
           _w("Backend", "Perbarui metrik Prometheus di setiap tahap",
              "/metrics siap di-scrape"),
           _w("Admin", "Buka trace satu percakapan",
              "Urutan langkah, durasi, token, dan error terlihat"),
           _w("Tim", "Saat insiden, telusuri dari metrik → log → trace",
              "Akar masalah ditemukan tanpa menebak"),
       ),
       wireframe="""
METRIK YANG DIEKSPOR
  chat_requests_total{status}          counter
  chat_latency_seconds{phase}          histogram (retrieval|llm|total)
  llm_tokens_total{type,model}         counter (prompt|completion)
  tool_calls_total{name,ok}            counter
  quota_rejections_total{kind}         counter
  feedback_total{rating}               counter

PRIVASI LOG
  ✗ {"message":"gaji saya berapa"}
  ✓ {"message_len":18,"message_hash":"9f2c…"}
""",
       acceptance=("Satu request bisa ditelusuri lengkap lewat request_id",
                   "/metrics mengekspor minimal 6 metrik di atas",
                   "Trace percakapan bisa dibuka admin dari UI",
                   "Log tidak memuat isi pesan pengguna secara utuh",
                   "Ada dokumen singkat 'cara menyelidiki insiden'"),
       evidence=(f"{P}/backend/app/observability.py",
                 f"{P}/docs/RUNBOOK.md"),
       depends_on=("INT-025",), source=_ARCH),

    _t("INT-030", "Uji keamanan & pengerasan (hardening) sebelum rilis",
       "i5", priority="critical", estimate=1.5, labels=(*B, "security"),
       description=(
           "Checklist keamanan yang dikerjakan, bukan sekadar dibaca: header "
           "keamanan (CSP, X-Frame-Options, HSTS), CORS ketat ke domain yang "
           "dikenal, validasi ukuran & tipe semua input, proteksi IDOR (uji "
           "akses lintas pengguna untuk percakapan/pesan/feedback/dokumen), "
           "rahasia hanya dari environment, dependensi dipindai (pip-audit & npm "
           "audit), dan tidak ada kunci API yang pernah sampai ke browser. Tulis "
           "hasil pengujian di dokumen SECURITY.md."),
       workflow=(
           _w("Intern", "Jalankan checklist OWASP ringkas terhadap aplikasi",
              "Daftar temuan dengan tingkat keparahan"),
           _w("Intern", "Uji IDOR: akun A mencoba membuka data akun B",
              "Semua percobaan harus 403/404, dibuktikan test otomatis"),
           _w("Intern", "Jalankan pip-audit & npm audit, perbaiki yang kritis",
              "Tidak ada kerentanan kritis tersisa"),
           _w("Intern", "Tulis SECURITY.md + sisa risiko yang diterima",
              "Pembimbing menyetujui rilis"),
       ),
       wireframe="""
CHECKLIST HARDENING
  [ ] Header: CSP, X-Frame-Options, X-Content-Type-Options, HSTS
  [ ] CORS allowlist domain produksi saja
  [ ] IDOR: /conversations/{id}, /messages/{id}, /feedback, /documents
  [ ] Upload: batas ukuran, tipe MIME diverifikasi, nama file disanitasi
  [ ] Rahasia: hanya dari env; .env tidak pernah di-commit
  [ ] Dependensi: pip-audit ✅  npm audit ✅ (tak ada kritis)
  [ ] Tidak ada kunci API di bundle frontend (dicek grep build)
""",
       acceptance=("Semua header keamanan terpasang & diverifikasi",
                   "Test otomatis membuktikan tidak ada IDOR di 4 endpoint utama",
                   "Tidak ada kerentanan dependensi tingkat kritis",
                   "Grep pada bundle frontend tidak menemukan kunci API",
                   "SECURITY.md memuat temuan, perbaikan, dan risiko yang diterima"),
       evidence=(f"{P}/docs/SECURITY.md",
                 f"{P}/backend/tests/test_authorization.py"),
       depends_on=("INT-019", "INT-025"), source=_WORK),

    _t("INT-031", "Uji beban & optimasi performa",
       "i5", priority="high", estimate=1.5, labels=(*B, "performance"),
       description=(
           "Ukur sebelum menebak. Skenario k6/locust: 20 pengguna bersamaan "
           "mengirim pertanyaan selama 5 menit dengan provider tiruan berlatensi "
           "realistis. Targetnya p95 first-token < 2 dtk dan p95 retrieval < 300 "
           "ms. Perbaiki temuan yang biasa muncul: index DB yang hilang, N+1 "
           "query pada riwayat, embedding dihitung ulang, dan koneksi HTTP yang "
           "tidak di-pool. Catat hasil sebelum-sesudah di dokumen performa."),
       workflow=(
           _w("Intern", "Tulis skenario beban + provider tiruan",
              "Beban bisa diulang kapan saja"),
           _w("Intern", "Jalankan baseline & kumpulkan metrik", "Angka awal tercatat"),
           _w("Intern", "Profil titik lambat (query, embedding, serialisasi)",
              "Daftar perbaikan berdasar data"),
           _w("Intern", "Terapkan perbaikan lalu jalankan ulang",
              "Tabel sebelum-sesudah membuktikan peningkatan"),
       ),
       wireframe="""
HASIL UJI BEBAN (20 VU, 5 menit)
 Metrik                    | Sebelum | Sesudah | Target
 first token p95           | 3.4 s   | 1.7 s   | < 2 s     ✅
 retrieval p95             | 520 ms  | 180 ms  | < 300 ms  ✅
 error rate                | 2.1 %   | 0.0 %   | < 1 %     ✅
 memori puncak backend     | 780 MB  | 410 MB  | < 512 MB  ✅
 Perbaikan: index (user_id,created_at) · cache embedding · pool HTTP
""",
       acceptance=("Skenario beban tersimpan di repo dan bisa dijalankan ulang",
                   "p95 first-token < 2 dtk dan retrieval p95 < 300 ms tercapai",
                   "Tabel sebelum-sesudah beserta perbaikan terdokumentasi",
                   "Tidak ada error rate > 1% pada beban target"),
       evidence=(f"{P}/loadtest/chat.js", f"{P}/docs/PERFORMANCE.md"),
       depends_on=("INT-029",), source=_SUCCESS),

    _t("INT-032", "Aksesibilitas, responsif, dan status kosong/gagal yang rapi",
       "i5", priority="medium", estimate=1.5, labels=F,
       description=(
           "Merapikan pengalaman agar layak dipakai sehari-hari: navigasi penuh "
           "dengan keyboard (Tab, Esc menutup dialog, fokus terjebak di modal), "
           "label ARIA pada tombol ikon termasuk 👍/👎, kontras teks memenuhi "
           "WCAG AA, pengumuman live region saat jawaban selesai mengalir, "
           "layout yang tetap nyaman di layar 360 px, serta status kosong / "
           "memuat / gagal yang informatif di setiap layar (chat, dokumen, "
           "riwayat, analitik)."),
       workflow=(
           _w("Intern", "Audit dengan keyboard saja dan pembaca layar",
              "Daftar masalah aksesibilitas"),
           _w("Intern", "Perbaiki fokus, label ARIA, dan kontras", "Audit ulang bersih"),
           _w("Intern", "Rancang state kosong/memuat/gagal tiap layar",
              "Tidak ada layar putih tanpa penjelasan"),
           _w("Intern", "Uji di lebar 360/768/1440 px", "Tidak ada elemen terpotong"),
       ),
       wireframe="""
STATUS KOSONG — CHAT
+--------------------------------------------------------------+
|                        💬                                     |
|            Mulai percakapan pertama Anda                     |
|   Coba: "Berapa hari cuti tahunan?"  "Cara klaim kesehatan?" |
|                  [ gunakan contoh ]                          |
+--------------------------------------------------------------+
STATUS GAGAL — DOKUMEN
+--------------------------------------------------------------+
|  ⚠ Gagal memuat dokumen. Periksa koneksi Anda.   [Coba lagi] |
+--------------------------------------------------------------+
Keyboard: Tab ▸ fokus terlihat · Esc ▸ tutup dialog · ⏎ ▸ kirim
""",
       acceptance=("Seluruh alur utama bisa diselesaikan tanpa mouse",
                   "Tombol ikon (termasuk 👍/👎) punya label yang terbaca pembaca layar",
                   "Kontras teks memenuhi WCAG AA pada mode terang",
                   "Setiap layar punya status kosong, memuat, dan gagal",
                   "Layout utuh pada lebar 360 px"),
       evidence=(f"{P}/frontend/components/EmptyState.tsx",
                 f"{P}/docs/ACCESSIBILITY.md"),
       depends_on=("INT-010", "INT-027"), source=_SPEC),

    _t("INT-033", "Uji menyeluruh: unit, integrasi, dan end-to-end",
       "i5", priority="critical", estimate=2, labels=(*_L, "test"),
       description=(
           "Jaring pengaman sebelum rilis. Unit test untuk chunking, retriever, "
           "context budget, kuota, dan guardrail. Integrasi: alur upload → ingest "
           "→ tanya → jawab bersitasi → 👍/👎 → pemakaian token bertambah, "
           "dijalankan dengan provider tiruan. E2E Playwright untuk tiga skenario "
           "pengguna: login → tanya → beri 👎 dengan alasan; unggah dokumen → "
           "tanya isinya; habiskan kuota → lihat pesan 429. Target: seluruh jalur "
           "kritis tercakup dan CI menjalankan semuanya."),
       workflow=(
           _w("Developer", "Jalankan `make test`",
              "Unit + integrasi + e2e berjalan berurutan"),
           _w("CI", "Jalankan suite yang sama pada setiap MR",
              "Merah → merge diblokir"),
           _w("Tim", "Tambah test regresi setiap kali bug ditemukan",
              "Bug yang sama tidak kembali"),
       ),
       wireframe="""
PIRAMIDA UJI
        ╱╲      E2E (3 skenario Playwright)
       ╱──╲     Integrasi (alur ingest→chat→feedback→usage)
      ╱────╲    Unit (chunking, retriever, konteks, kuota, guardrail)

SKENARIO E2E
 1. login → tanya → jawaban bersitasi muncul → klik 👎 → pilih alasan → tersimpan
 2. unggah PDF → tunggu ready → tanya isinya → jawaban menyebut dokumen itu
 3. set kuota 100 token → kirim pesan → banner 429 + composer nonaktif
""",
       acceptance=("Unit test mencakup 5 modul inti di atas",
                   "Test integrasi menjalankan alur lengkap dengan provider tiruan",
                   "3 skenario E2E Playwright hijau",
                   "Satu perintah menjalankan seluruh suite",
                   "CI memblokir merge saat ada test merah"),
       evidence=(f"{P}/backend/tests/test_e2e_flow.py",
                 f"{P}/frontend/e2e/chat.spec.ts", f"{P}/Makefile"),
       depends_on=("INT-026", "INT-025", "INT-022"), source=_SUCCESS),

    _t("INT-034", "Deploy produksi + backup, migrasi, dan rollback",
       "i5", priority="critical", estimate=1.5, labels=(*_L, "devops"),
       description=(
           "Bawa aplikasi ke lingkungan nyata: Dockerfile multi-stage yang "
           "ramping, docker-compose produksi di belakang reverse proxy dengan "
           "HTTPS, migrasi database berversi (Alembic) yang dijalankan otomatis "
           "saat start, backup harian database + folder dokumen ke lokasi "
           "terpisah beserta prosedur restore yang SUDAH PERNAH DIUJI, health "
           "check untuk orkestrator, dan prosedur rollback ke versi sebelumnya "
           "dalam < 10 menit."),
       workflow=(
           _w("CI", "Build image saat tag rilis dibuat", "Image ter-push ke registry"),
           _w("Deployer", "Jalankan compose produksi",
              "Migrasi dijalankan, health check hijau, trafik dialihkan"),
           _w("Cron", "Backup harian DB + dokumen", "Arsip tersimpan & terverifikasi"),
           _w("Deployer", "Bila rilis bermasalah, jalankan prosedur rollback",
              "Versi sebelumnya aktif < 10 menit, data utuh"),
           _w("Intern", "Uji restore dari backup ke lingkungan kosong",
              "Bukti bahwa backup benar-benar bisa dipulihkan"),
       ),
       wireframe="""
ALUR RILIS
  tag v1.0.0 ─► CI build ─► registry ─► deploy ─► migrasi ─► health ✅
                                              │
                                        gagal ─┴─► rollback ke v0.9.x

BACKUP
  02:00 setiap hari → data.db + data/documents → arsip terenkripsi
  retensi 14 hari · uji restore minimal 1x sebelum serah terima
""",
       acceptance=("Aplikasi berjalan di lingkungan produksi/staging lewat HTTPS",
                   "Migrasi database berversi dan dijalankan otomatis saat start",
                   "Backup harian berjalan dan restore SUDAH diuji sekali",
                   "Prosedur rollback tertulis dan pernah dicoba",
                   "Health check dipakai orkestrator untuk menahan trafik saat belum siap"),
       evidence=(f"{P}/Dockerfile", f"{P}/docker-compose.prod.yml",
                 f"{P}/docs/DEPLOY.md"),
       depends_on=("INT-030", "INT-033"), source=_ARCH),

    _t("INT-035", "Dokumentasi, runbook, dan serah terima",
       "i5", priority="high", estimate=1.5, labels=(*_L, "docs"),
       description=(
           "Produk yang tidak bisa dijalankan orang lain belum selesai. Lengkapi: "
           "README (arsitektur, setup dari nol, variabel environment, perintah "
           "umum), panduan pengguna singkat (cara bertanya yang baik, arti "
           "sitasi, arti 👍/👎, kuota), runbook operasional (gejala → penyebab "
           "→ tindakan untuk 6 insiden umum: LLM mati, kuota habis massal, "
           "ingest macet, DB penuh, latensi naik, error rate naik), dan catatan "
           "utang teknis + rekomendasi lanjutan yang jujur."),
       workflow=(
           _w("Intern", "Tulis README & panduan pengguna",
              "Orang baru bisa menjalankan dari nol"),
           _w("Intern", "Tulis runbook 6 insiden dengan langkah konkret",
              "Operator tahu harus apa jam 2 pagi"),
           _w("Orang lain", "Ikuti README dari mesin bersih tanpa bertanya",
              "Berhasil jalan → dokumentasi lulus uji"),
           _w("Intern", "Catat utang teknis & rencana lanjutan", "Serah terima jujur"),
       ),
       wireframe="""
STRUKTUR DOKUMEN
  README.md              ringkasan, setup, env, perintah
  docs/USER-GUIDE.md     cara pakai untuk karyawan
  docs/RUNBOOK.md        insiden → gejala → tindakan
  docs/DEPLOY.md         rilis, backup, rollback
  docs/SECURITY.md       temuan & risiko
  docs/HANDOVER.md       utang teknis, rekomendasi lanjutan

RUNBOOK (contoh baris)
  Gejala: banyak 429 quota_exceeded mendadak
  Cek   : /metrics quota_rejections_total, kebijakan kuota terbaru
  Aksi  : naikkan batas sementara via admin, umumkan, telusuri penyebab
""",
       acceptance=("Orang di luar tim berhasil menjalankan proyek hanya dari README",
                   "Panduan pengguna menjelaskan sitasi, feedback, dan kuota",
                   "Runbook memuat minimal 6 insiden dengan langkah konkret",
                   "Utang teknis & rekomendasi lanjutan ditulis jujur",
                   "Semua dokumen tertaut dari README"),
       evidence=(f"{P}/README.md", f"{P}/docs/RUNBOOK.md", f"{P}/docs/HANDOVER.md"),
       depends_on=("INT-034",), source=_WORK),

    _t("INT-036", "Demo akhir & review terhadap kriteria sukses",
       "i5", priority="medium", estimate=0.5, labels=(*_L, "review"),
       description=(
           "Tutup proyek dengan demo 10 menit yang menunjukkan produk bekerja "
           "utuh: unggah dokumen → tanya → jawaban bersitasi → 👎 dengan alasan → "
           "admin melihatnya di analitik → kuota berkurang → memori dipakai di "
           "percakapan berikutnya. Bandingkan hasil akhir dengan metrik di "
           "dokumen 01 secara apa adanya, rekam videonya, dan sepakati status "
           "akhir setiap task di papan ini."),
       workflow=(
           _w("Intern", "Susun skrip demo 10 menit berurutan",
              "Tidak ada bagian yang improvisasi"),
           _w("Intern", "Latih & rekam demo", "Video tersimpan di dokumen"),
           _w("Intern", "Bandingkan metrik nyata vs target dokumen 01",
              "Tabel jujur: tercapai / tidak + alasannya"),
           _w("Pembimbing", "Review dan tentukan kelanjutan proyek",
              "Papan task ditutup dengan status akhir"),
       ),
       wireframe="""
SKRIP DEMO (10 MENIT)
  0:00 masalah & sasaran                      (1 mnt)
  1:00 unggah SOP → status ready              (1 mnt)
  2:00 tanya → jawaban mengalir + sitasi      (2 mnt)
  4:00 klik sumber → chunk asli tersorot      (1 mnt)
  5:00 beri 👎 + alasan                        (1 mnt)
  6:00 admin: analitik menampilkan kasus itu  (1.5 mnt)
  7:30 kuota berkurang; batas → 429           (1 mnt)
  8:30 percakapan baru: memori masih ingat    (1 mnt)
  9:30 metrik vs target + rencana lanjutan    (0.5 mnt)
""",
       acceptance=("Demo berjalan tanpa langkah yang gagal",
                   "Tabel metrik nyata vs target diisi apa adanya",
                   "Video/rekaman demo tersimpan di repo atau tautan di dokumen",
                   "Semua task di papan punya status akhir yang benar"),
       evidence=(f"{P}/docs/DEMO.md",),
       depends_on=("INT-035",), source=_SUCCESS),
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
