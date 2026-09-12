# Docs Developer — Ask Anything

> Peta lengkap codebase untuk kontributor: aliran data SSE, schema tracing,
> cara menambah provider/tool, setup dev, testing, dan pipeline screenshot
> dokumentasi. Versi interaktif: halaman in-app **`/developer`**.
> Pendamping user-facing: [`PANDUAN-PENGGUNA.md`](PANDUAN-PENGGUNA.md).

---

## Daftar isi

1. [Arsitektur](#1-arsitektur)
2. [Struktur repo](#2-struktur-repo)
3. [Setup lingkungan dev](#3-setup-lingkungan-dev)
4. [Menjalankan & testing](#4-menjalankan--testing)
5. [HTTP API & event SSE](#5-http-api--event-sse)
6. [Agent loop & tracing](#6-agent-loop--tracing)
7. [Providers](#7-providers)
8. [Tools registry](#8-tools-registry)
9. [Frontend](#9-frontend)
10. [Pipeline screenshot docs](#10-pipeline-screenshot-docs)
11. [Referensi env](#11-referensi-env-prefix-ask_)
12. [Troubleshooting dev](#12-troubleshooting-dev)

---

## 1. Arsitektur

Monolith **FastAPI** berbicara **SSE** dengan frontend **Next.js 16**. Agent
loop hidup di backend; provider (HuggingFace lokal / OpenAI / mock) dan tools
(search, fetch, diagram, calculator) di-plug lewat registry schema-driven.

```
┌──────────────┐   SSE (/api/chat)   ┌──────────────────────────────┐
│  Next.js UI  │ ◄────────────────── │  FastAPI backend (monolith)  │
│  + Mermaid   │ ──────────────────► │  agent loop + tools + trace  │
└──────────────┘      POST           │        │            │       │
                                     │   providers         tools   │
                                     │  hf / openai / mock  search │
                                     │        │             fetch  │
                                     │        ▼             diagram│
                                     │  llama-server(8081)  calc   │
                                     └──────────────────────────────┘
```

- **Backend** `backend/app/`: FastAPI + SQLite (`conversations`, `messages`,
  `trace_events`).
- **Frontend** `frontend/`: Next.js App Router + Tailwind + Mermaid.
- **Demo/test** `scripts/fake_llama_server.py`: emulator llama-server dengan
  wire-format SSE lengkap (`<think>` terbelah chunk, `tool_calls.arguments`
  dicicil per index, logprobs, usage) — dipakai `run.py --demo` dan test
  integrasi provider.

![Run lengkap di UI](images/04-chat-diagram-interpreter.png)
*Satu run: `tool_call create_diagram` → `tool_result` (Mermaid) → jawaban
final; setiap event juga persist ke `trace_events` untuk replay.*

## 2. Struktur repo

```
run.py / run.bat / run.sh      # launcher: cek+install dependensi, jalankan BE+FE
backend/
  app/
    main.py                  # FastAPI app + mount /slides & /docs-images
    config.py                # pydantic-settings (prefix ASK_*)
    db.py                    # SQLite: conversations, messages, trace_events
    providers/               # base / openai / huggingface / mock
    tools/                   # web_search, fetch_url, diagrams, calculator
    agent/                   # loop.py (agent+tracing), prompts.py
    api/routes.py            # /api/chat (SSE), conversations, settings, health
  tests/                     # pytest: parser SSE, agent, tools, API
scripts/
  fake_llama_server.py       # emulator llama-server (--demo & testing)
  capture_screenshots.py     # generator screenshot docs (Playwright)
docs/                        # METODOLOGI.md, slides, PANDUAN-*, images/
frontend/                    # Next.js 16: sidebar, hero, chat, interpreter, docs
```

## 3. Setup lingkungan dev

```bash
# backend
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
ASK_PROVIDER=mock .venv/bin/python -m uvicorn backend.app.main:app --port 8000

# frontend
cd frontend && npm install && npx next dev -p 3000

# atau satu perintah (cek+install otomatis; --demo = emulator LLM di :8081)
python3 run.py --demo
```

Catatan dev-server Next 16: resource dev (`/_next/*`) diblokir untuk origin
cross-site. Repo menyetel `allowedDevOrigins: ["127.0.0.1", "*.e2b.app",
"**.e2b.app"]` di `next.config.ts` agar UI hydrate saat diakses via loopback
atau host preview sandbox. Tanpa ini UI ter-render SSR tetapi **tidak
interaktif** (state kosong) — gejala yang mudah salah diagnosis.

## 4. Menjalankan & testing

```bash
.venv/bin/python -m pytest backend/tests -q   # 15 passed
cd frontend && npx tsc --noEmit && npx next build
python3 run.py --demo                          # E2E live (emulator LLM)
```

| File test | Cakupan |
|---|---|
| `test_providers.py` | Parser SSE protokol OpenAI: `<think>` terbelah antar chunk, akumulasi `tool_calls.arguments`, logprobs, usage. |
| `test_api.py` | `/api/chat` end-to-end via TestClient: urutan event SSE + persist trace (`prompt`, `tool_call`, `logprobs`). |
| `test_tools.py` | Validasi Mermaid, keamanan calculator (AST whitelist), ekstraksi `fetch_url`. |

## 5. HTTP API & event SSE

| Method | Path | Kegunaan |
|---|---|---|
| POST | `/api/chat` | Stream satu run agent (SSE). Body `{message, conversation_id?}`. |
| GET | `/api/conversations` | Daftar percakapan (sidebar). |
| GET | `/api/conversations/{id}` | Messages + trace lengkap (replay Interpreter). |
| DELETE | `/api/conversations/{id}` | Hapus percakapan. |
| GET/POST | `/api/settings` | Baca/ubah runtime settings (provider, base url, model, temperature). |
| GET | `/api/health` | Status backend + `llm_reachable` (banner & indikator sidebar). |
| GET | `/docs` | Swagger UI FastAPI. Static mount: `/slides/*`, `/docs-images/*`. |

### Event SSE (urutan khas satu run)

| `type` | Payload penting | Konsumsi UI |
|---|---|---|
| `start` | `conversation_id` | page.tsx: set active id |
| `meta` | provider, model, temperature, max_steps, logprobs | Interpreter → Metrics |
| `prompt` | `system`, `messages`, `tools` | Interpreter → Prompt |
| `thinking` | `text` (stream) | kotak 💭 + Timeline |
| `delta` | `text` (stream) | jawaban markdown |
| `logprobs` | `items[{token, prob, top[]}]` | Interpreter → Tokens |
| `tool_call` | `id`, `name`, `arguments` mentah | chip tool + Timeline |
| `tool_result` | `id`, `name`, `summary`, `data` | chip ✓ + Timeline |
| `usage` | prompt/completion/total tokens | Metrics |
| `done` | `answer`, `latency_ms`, `steps` | selesai + persist |
| `error` | `message` | banner inline + Timeline |

```bash
curl -N localhost:8000/api/chat -H 'Content-Type: application/json' \
     -d '{"message":"Buatkan diagram alur proses registrasi pengguna"}'
```

## 6. Agent loop & tracing

1. `routes.py` membuat conversation (bila baru) + `asyncio.Queue`; task agent
   dijalankan terpisah sehingga **klien putus = task di-cancel**.
2. `loop.py` merakit messages (history SQLite → protokol OpenAI, termasuk
   `role:tool` & `assistant_toolcalls`), emit event `prompt`, lalu stream dari
   provider.
3. Bila model emit `tool_calls` (maks `ASK_MAX_STEPS`): emit `tool_call` →
   eksekusi via registry (timeout 30 dtk) → emit `tool_result` →
   `messages += assistant(tool_calls) + role:tool` + hint sistem → stream lagi.
4. Setiap event persist ke `trace_events(conversation_id, run_id, seq, type,
   payload, ts)` sehingga riwayat bisa direplay penuh.
5. Pagar pengaman: payload di-cap 12k (`_cap`), error tool diberikan ke model
   sebagai data (graceful), DB tetap konsisten bila klien putus.

**Kontrak replay:** `db.list_trace()` **meratakan** `payload` ke level atas
sehingga bentuk event replay identik dengan wire SSE (`{type, ...fields}`).
UI membaca field top-level (`text`, `items`, `summary`, `arguments`, …) untuk
event live maupun replay — jangan kembalikan payload nested.

![Timeline replay](images/05-interpreter-timeline-expanded.png)
*Replay dari SQLite: payload JSON mentah per event tetap utuh.*

## 7. Providers

Semua provider mengimplementasikan `BaseProvider.stream()` yang yield
`StreamEvent` (`thinking` / `delta` / `logprobs` / `tool_calls` / `usage` /
`done`). `HuggingFaceProvider` mewarisi `OpenAIProtocolProvider` — parser SSE
bersama: state-machine `<think>` yang terbelah chunk, akumulasi
`tool_calls.arguments` per index, logprobs, usage.

Menambah provider baru:

1. Buat `backend/app/providers/foo_provider.py` (subclass `BaseProvider`, atau
   `OpenAIProtocolProvider` bila kompatibel).
2. Daftarkan di `providers/__init__.py:build_provider()` + nama provider di
   `config.py` dan pilihan di `SettingsModal`.
3. Tambah test parser di `backend/tests/test_providers.py`.

## 8. Tools registry

| Tool | Fungsi | Catatan keamanan |
|---|---|---|
| `web_search` | DuckDuckGo lite (default) / Serper / Tavily; parse BS4 judul+URL+snippet. | Timeout & cap payload; error → `tool_result`. |
| `fetch_url` | Ekstrak teks halaman (readability ringan) ≤ 12k char. | Hanya teks, tanpa eksekusi konten. |
| `create_diagram` | Mermaid `flowchart` / `graph` / `mindmap` dari nodes+edges. | Validasi server-side: id dinormalisasi, label di-escape, edge diverifikasi. |
| `calculator` | Aritmetika via AST whitelist (`+ - * / // % **`). | Tidak ada `eval()`; node di luar whitelist = error. |

Menambah tool baru:

```python
# backend/app/tools/foo.py
from .base import Tool, ToolContext, ToolResult

async def run_foo(args: dict, ctx: ToolContext) -> ToolResult:
    ...  # args tervalidasi JSON-Schema
    return ToolResult(summary="...", data={...})

FOO = Tool(name="foo", description="...", parameters={...}, run=run_foo)
# daftarkan di tools/__init__.py (ALL_TOOLS) — schema otomatis dikirim ke LLM
```

## 9. Frontend

| File | Tanggung jawab |
|---|---|
| `app/page.tsx` | Orkestrasi state: conversations, messages, trace, live-stream, settings, aksen. |
| `app/panduan/page.tsx`, `app/developer/page.tsx` | Halaman dokumentasi in-app (komponen di `components/docs/DocShell.tsx`). |
| `lib/api.ts` | Klien SSE (parser baris `data:`), CRUD conversations, settings, health. |
| `components/ChatView.tsx` | Render pesan, chip tool, kotak thinking, live answer. |
| `components/Interpreter.tsx` | 4 tab trace dari event live maupun replay. |
| `components/Mermaid.tsx` | `mermaid.render()` (`securityLevel: strict`) untuk fence ```mermaid & hasil tool. |
| `next.config.ts` | Rewrite `/api`, `/slides`, `/docs-images` ke backend (same-origin untuk browser & preview) + `allowedDevOrigins`. |

Gambar dokumentasi disajikan backend via mount `/docs-images` (direktori
`docs/images`) dan diproxy Next sehingga halaman docs tetap same-origin.

## 10. Pipeline screenshot docs

Semua PNG di `docs/images/` (dipakai markdown docs, `/panduan`, `/developer`)
diambil dari aplikasi yang **benar-benar berjalan**:

```bash
# 1) jalankan stack + emulator LLM
python3 run.py --demo

# 2) install tooling capture (sekali)
pip install playwright brotli
playwright install chromium        # bila jaringan mengizinkan

# 3) capture flow UI lalu halaman docs
BASE_URL=http://127.0.0.1:3000 python3 scripts/capture_screenshots.py main
python3 scripts/capture_screenshots.py pages
```

- Stage `main`: hero, Explore, banner offline, chat diagram/search/kalkulasi,
  4 tab Interpreter, settings, sidebar, slides, aksen, viewport mobile.
- Stage `pages`: screenshot `/panduan` & `/developer` (viewport-only agar
  tidak multi-MB).
- Lingkungan tanpa akses CDN browser: set env `CHROME_EXE` (binary Chromium
  alternatif, mis. dari paket npm `@sparticuz/chromium`), `CHROME_LIBS`
  (LD_LIBRARY_PATH tambahan), `CHROME_FONTS` (file fontconfig) — lihat
  docstring `scripts/capture_screenshots.py`.

![Halaman panduan in-app](images/17-halaman-panduan.png)
*Halaman `/panduan` — dokumen ini dalam bentuk interaktif.*

![Halaman developer in-app](images/18-halaman-developer.png)
*Halaman `/developer` — arsitektur & referensi kontributor.*

## 11. Referensi env (prefix `ASK_`)

| Variabel | Default | Keterangan |
|---|---|---|
| `ASK_PROVIDER` | `huggingface` | `huggingface` \| `openai` \| `mock` |
| `ASK_HF_BASE_URL` | `http://127.0.0.1:8081/v1` | Server lokal OpenAI-compatible (llama.cpp) |
| `ASK_HF_MODEL` | `Qwen/Qwen3-8B-GGUF` | Label model |
| `ASK_OPENAI_API_KEY` / `ASK_OPENAI_BASE_URL` / `ASK_OPENAI_MODEL` | – / api.openai.com / gpt-4o-mini | Provider OpenAI |
| `ASK_TEMPERATURE`, `ASK_MAX_STEPS`, `ASK_LOGPROBS` | 0.7 / 6 / true | Generasi & interpreter |
| `ASK_SEARCH_BACKEND` | `ddg` | `ddg` \| `serper` \| `tavily` (+ key masing-masing) |
| `ASK_DB_PATH` | `data/ask_anything.db` | Lokasi SQLite |

Semua juga bisa diubah runtime via `POST /api/settings` (dialog Settings).

## 12. Troubleshooting dev

| Masalah | Penyebab | Fix |
|---|---|---|
| UI ter-render tetapi state kosong / tidak interaktif | Next 16 memblokir dev-resources cross-origin → hydration gagal. | Tambahkan host ke `allowedDevOrigins` (`next.config.ts`), restart dev server. |
| Interpreter replay kosong | Event replay tidak flat (payload nested). | Jaga kontrak replay: `db.list_trace()` meratakan payload. |
| Playwright gagal download Chromium | CDN diblokir jaringan. | Pakai `CHROME_EXE` binary alternatif (docstring script). |
| Screenshot tanpa teks | Fontconfig tidak menemukan font. | Set `CHROME_FONTS` ke `fonts.conf` dengan `<dir>` font tersedia. |
| `web_search` error di sandbox offline | Egress diblokir. | Diharapkan (graceful); pakai Serper/Tavily bila punya akses. |
| Port 8081 bentrok | Emulator/llama-server lain jalan. | Ubah `ASK_HF_BASE_URL` atau matikan proses lama. |
