# Arsitektur prototipe (sudah dikunci)

Ringkasan operasional dari **PRD bagian C** ([01-template-prd.md](01-template-prd.md))
dan **design system** ([05-design-system.md](05-design-system.md)). Bila ada
selisih, PRD dan design system yang menang — dokumen ini hanya merapikannya
menjadi daftar kerja. Stack sudah ditetapkan: tidak dibandingkan ulang dan
tidak ditambah tanpa ADR yang disetujui pembimbing.

Repo kerja: **`ai-assistant-prototype`** (monorepo terpisah dari `ask-anything`).
`ask-anything` hanya boleh dibaca sebagai contoh pola, bukan disalin.

## 1. Stack

| Lapisan | Pilihan | Catatan |
|---|---|---|
| Arsitektur | **Monorepo decoupled + Clean Architecture** | ADR-01; 4 layer di backend dan frontend |
| Backend | **FastAPI** (Python, async) | Pydantic v2, SQLAlchemy 2 async, Alembic |
| Frontend | **Next.js 14+** (App Router, TypeScript, Tailwind) | controller/presenter di luar komponen UI |
| Database | **PostgreSQL on-premise** | ADR-02; satu-satunya database |
| Vektor | **pgvector + indeks HNSW** (`vector_cosine_ops`) | ADR-03; `vector(384)` |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` | lokal, vektor dinormalisasi; stub deterministik untuk test |
| Parser dokumen | PyMuPDF (PDF), python-docx (DOCX), markdown-it-py (MD) | maks 10 MB per berkas |
| Token | `tiktoken` (`cl100k_base`) | fallback perkiraan `len/4` |
| LLM | `ILLMProvider`: OpenAI-compatible, vLLM, HuggingFace + **Mock Provider** | ADR-05; mock wajib jalan tanpa API key |
| Streaming | **SSE** `/api/v1/chat/stream` | event bertipe, lihat INT-006 |
| Tracing | Tabel `traces` sendiri | ADR-04; tanpa SaaS eksternal |
| UI | **beUI** (registri `@beui` via shadcn) | `npx shadcn add @beui/<slug>` |
| Ikon | **`lucide-react`** saja | tanpa emoji |
| Motion | `motion/react` + token fisika beUI | hormati `prefers-reduced-motion` |
| Tema | **Light mode default** | token warna HSL/oklch di `globals.css` |
| Test | `pytest` + `pytest-asyncio`, `vitest`, Playwright | tanpa API key |
| Kemasan | Docker Compose (3 service) / Dockerfile tunggal (Coolify) | state di named volume |

### Yang sengaja TIDAK dipakai

Vector database terpisah (Chroma/Qdrant/Milvus/FAISS server), Redis,
Kafka/RabbitMQ, Kubernetes, LangChain/LlamaIndex, LangSmith/Datadog/Phoenix,
Streamlit, SQLite sebagai database aplikasi, pustaka ikon selain lucide-react.

### Non-goals (PRD A.4)

Tanpa suara, tanpa multi-tenant, tanpa fine-tuning, tanpa aplikasi mobile
native, **tanpa eksekusi shell/OS bebas** (tool agent dibatasi pada retrieval
dan perenderan komponen visual terdaftar), tanpa kolaborasi edit dokumen
real-time.

## 2. Struktur folder (PRD C.3)

```
ai-assistant-prototype/
  backend/
    app/
      domain/            entities (Document, Chunk, Message, Session, Trace, Cost), errors
      application/       use_cases/ (chat_stream, ingest_doc, retrieve_rag,
                         generate_visual, route_intent, build_context, ...),
                         interfaces/ (ILLMProvider, repositories, TokenCounter),
                         guardrails/, validators/, services/ (quota, cost)
      infrastructure/    db/ (session, models, repositories/), parsers/,
                         embeddings/, llm/ (factory, provider_chain, adapters),
                         tracing/, cache/, tokenizer/
      presentation/      api/v1/ (endpoints, router), schemas/, middlewares/
      config.py  main.py
    alembic/  tests/  Dockerfile  requirements.txt
  frontend/
    src/
      entities/          Message, Document, Citation, Visual
      application/       use_cases/, contracts/
      interface-adapters/ controllers/ (chat, session, document), presenters/
      infrastructure/    sseChatClient, HTTP API
      components/        agents/* (beUI), motion/*, ui/*
      lib/               ease.ts (token gerak beUI), hooks/
    app/                 layout.tsx, page.tsx (chat), documents/, admin/, login/
    components/          ChatContainer, GraphView, ChartRenderer,
                         DocumentUploader, CitationBadge
  docs/  scripts/  docker-compose.yml  Dockerfile  run.py  .env.example
```

Aturan lapisan: dependensi hanya mengarah ke dalam (presentation ->
application -> domain). Komponen UI **hanya presentasi**; pemanggilan endpoint
dan penanganan stream SSE ada di `src/infrastructure/` dan diorkestrasi oleh
`src/interface-adapters/controllers/`.

## 3. Alur satu jawaban (7 tahap, PRD C.1)

```
Tahap 1  Next.js (controller)   input + filter dokumen, buka stream SSE ke /api/v1/chat/stream
Tahap 2  Input guardrail        panjang 1-2.000 karakter, auth sesi, kuota harian,
                                prompt injection / jailbreak, redaksi PII
Tahap 3  Router                 grounded_qa | visual (flowchart, bar chart, GraphView) | general
Tahap 4  Retrieval / tool       embed query -> pgvector HNSW -> top-k, similarity >= 0.7
Tahap 5  Orkestrasi LLM         system prompt grounded + riwayat (maks 8.192) + chunk;
                                ILLMProvider streaming, jawaban maks 1.024 token
Tahap 6  Validasi output        sitasi valid, ambang 0.7 (fallback "tidak ditemukan"),
                                skema JSON payload visual
Tahap 7  Trace + biaya + SSE    traces, token_usage_logs, feedback; ChatPresenter merender
```

## 4. Tabel utama (PostgreSQL)

| Tabel | Isi | Task |
|---|---|---|
| `users` | akun + peran (`employee`, `power_user`, `admin`) | INT-007 |
| `chat_sessions`, `chat_messages` | percakapan, ringkasan, token per pesan | INT-008, INT-010 |
| `token_usage_logs` | prompt/completion token, biaya Rupiah per pemanggilan | INT-009, INT-024 |
| `documents`, `document_chunks` | dokumen, status, chunk + `embedding vector(384)` | INT-011, INT-012 |
| `guardrail_rules`, `guardrail_events` | aturan yang bisa disunting admin, kejadian blokir | INT-019 |
| `traces` | span bertingkat per request | INT-023 |
| `feedback` | suka/tidak suka + alasan + `trace_id` | INT-025 |
| `cache` | semantic cache pertanyaan berulang | INT-027 |

## 5. Anggaran & angka kunci (PRD bagian B)

| Parameter | Nilai |
|---|---|
| Context window | 8.192 token (system + chunk + riwayat) |
| Maks token jawaban | 1.024 |
| Kuota harian per pengguna | 50 pesan **atau** 100.000 token |
| Ambang similarity retrieval | >= 0.7 |
| Tarif acuan (gpt-4o-mini, kurs Rp16.000) | Rp2,4 / 1k token masuk; Rp9,6 / 1k token keluar |
| Target | tergrounding >= 80%, p95 TTFT <= 3 s (mock) / 6 s (nyata), suka >= 70%, biaya <= Rp500 per percakapan, cache hit >= 20% |

## 6. Variabel lingkungan (inti)

Lengkapnya di `.env.example` repo prototipe.

| Env | Contoh | Arti |
|---|---|---|
| `APP_ENV` | `development` | `development` / `staging` / `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | kosong di Docker (compose merakitnya dari `POSTGRES_PASSWORD`) |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` | `10`, `20`, `30` | pool koneksi |
| `LLM_PROVIDER` / `LLM_PROVIDERS` | `mock` / `openai,vllm,mock` | provider tunggal / rantai fallback (INT-029) |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | - | provider OpenAI-compatible (jangan pernah di-commit) |
| `VLLM_BASE_URL`, `VLLM_MODEL` | - | vLLM on-premise |
| `HUGGINGFACE_MODEL_ID`, `HUGGINGFACE_DEVICE` | - | inferensi lokal |
| `PRICE_INPUT_PER_1K_IDR`, `PRICE_OUTPUT_PER_1K_IDR` | `2.4`, `9.6` | tarif untuk kalkulator biaya (INT-024) |
| `QUOTA_DAILY_MESSAGES`, `QUOTA_DAILY_TOKENS`, `QUOTA_BURST_PER_MIN` | `50`, `100000`, `10` | kuota (INT-028) |
| `BACKEND_URL` | `http://backend:8000` | target proxy Next.js untuk `/api/v1/*` |

## 7. Aturan persistensi

Semua yang harus selamat dari redeploy berada di **volume Docker**:
`pgdata` (PostgreSQL termasuk vektor, sesi, trace, feedback), `uploads` (berkas
dokumen mentah), dan `hf_cache` (model embedding). Tidak ada state yang ditulis
ke layer image. Diuji di **INT-030**: `docker compose up -d --build` ulang,
percakapan, dokumen, dan vektor lama harus tetap ada (jangan memakai
`docker compose down -v`).

## 8. Aturan UI (ringkas dari design system)

1. Komponen baru dari beUI: `npx shadcn add @beui/<slug>` — jangan membuat
   komponen kustom bila beUI sudah menyediakannya.
2. Ikon hanya `lucide-react`; **tanpa emoji** di kode, teks UI, dan copywriting.
3. Warna lewat token CSS (`--primary`, `--muted`, `--destructive`, ...) — jangan
   menulis warna heksa langsung di komponen.
4. Light mode default; dark mode lewat kelas `.dark` tanpa mengganti nama utilitas.
5. Elemen interaktif punya ring fokus (`focus-visible:ring-2 focus-visible:ring-ring`),
   status agen memakai `role="status"` / `aria-live="polite"`.
