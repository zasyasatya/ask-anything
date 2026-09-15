# Metodologi & Cara Kerja Ask Anything

Dokumen prose pendamping [`slides-cara-kerja.html`](./slides-cara-kerja.html)
(buka file itu langsung di browser, atau lewat app di `/slides/slides-cara-kerja.html`;
navigasi `←`/`→`, `F` untuk fullscreen).

## 1. Filosofi: event-first transparency

Ask Anything dibangun di atas satu keyakinan desain: **agent yang tidak bisa
diamati tidak bisa dipercaya**. Karena itu satuan kerja terkecil sistem bukanlah
"jawaban", melainkan **event**:

> meta · prompt · thinking · delta · logprobs · tool_call · tool_result · usage · done · error

Setiap event memiliki dua tujuan hidup: (1) di-stream via SSE ke UI saat terjadi,
(2) ditulis ke tabel `trace_events` sehingga percakapan lama pun bisa dibuka
kembali beserta seluruh "isi kepala" agentnya. Ini yang kami sebut
*Mechanistic Interpreter*: bukan sekadar log, melainkan rekonstruksi lengkap
urutan keputusan model + agent.

## 2. Arsitektur

```
Browser (Next.js 16)
   │  same-origin /api/*  (Next rewrites → backend)
   ▼
FastAPI monolith
   ├─ api/routes.py      POST /api/chat (SSE), conversations, settings, health
   ├─ agent/loop.py      ReAct loop + tracer
   ├─ providers/         openai-protocol client ← huggingface | openai | mock
   ├─ tools/             web_search, fetch_url, create_diagram, calculator
   └─ db.py              SQLite: conversations, messages, trace_events
   ▼
model HuggingFace lokal (transformers)  /  api.openai.com & gateway  /  mock
```

Keputusan kunci:

1. **Monolith** — satu proses backend; sederhana di-deploy, mudah di-trace.
2. **Same-origin proxy** — browser tidak pernah memanggil localhost:8000
   langsung; Next me-rewrite `/api/*`. Ini membuat app tahan di-proxy/iframe
   (preview environment, reverse proxy produksi).
3. **Satu wire protocol** — OpenAI chat-completions streaming. llama.cpp,
   vLLM, LM Studio, dan OpenAI semuanya berbicara protokol ini, sehingga
   "HuggingFace lokal" dan "OpenAI API" hanyalah dua konfigurasi, bukan dua
   codebase.

## 3. Cara kerja agent (runut waktu)

1. `POST /api/chat` → conversation dipastikan ada; history dimuat dan
   dikonversi ke message OpenAI (role internal `assistant_toolcalls`/`tool`
   dipetakan ke `assistant(tool_calls)`/`tool`).
2. Task agent dijalankan terpisah; event masuk `asyncio.Queue`;
   `StreamingResponse` menarik queue menjadi `data: {json}\n\n`.
3. **Langkah loop** (maks `ASK_MAX_STEPS`, default 6):
   - `provider.stream(...)` menghasilkan event; thinking/delta/logprobs
     langsung diteruskan ke klien dan DB.
   - Bila model mengembalikan `tool_calls`: argumen JSON yang datang dicicil
     diakumulasi per index; tiap call dieksekusi (timeout 30 dtk) lewat
     registry; hasilnya di-emit sebagai `tool_result`, dipersist sebagai
     message `role:tool`, lalu loop berlanjut sehingga model bisa *melihat*
     hasil toolnya (langkah observe).
   - Bila tidak ada tool call → jawaban final; loop berhenti.
4. `done` membawa `answer`, `usage`, `latency_ms`, `steps`; message assistant
   final dipersist; UI me-reload conversation sebagai sumber kebenaran.

Pola ini adalah **ReAct** (reason–act–observe) dengan pagar pengaman:
batas langkah, timeout tool, payload dipangkas (12k char), dan error tool
diberi ke model sebagai data (bukan exception yang membunuh percakapan).

## 4. Parser streaming yang benar-benar diuji

Dua kekasaran dunia nyata ditangani eksplisit di `openai_provider.py`:

- **Tag `<think>` terbelah chunk** — state machine dua mode dengan
  *suffix-hold*: sisa buffer yang merupakan prefix tag ditahan sampai chunk
  berikutnya, sehingga teks thinking tidak bocor ke jawaban.
- **`tool_calls.arguments` dicicil** — llama.cpp mengirim potongan JSON kecil;
  kita akumulasi per `index` dan parse sekali di akhir turn, dengan fallback
  `{"_raw": ...}` bila model menghasilkan JSON rusak.

## 5. Tools sebagai kontrak schema

Setiap tool = `(nama, deskripsi, JSON-Schema, fungsi async)`. Schema langsung
menjadi `tools[]` permintaan LLM — tidak ada drift dokumentasi.
`create_diagram` menambahkan lapisan deterministik di atas kreativitas model:
id dinormalisasi, label di-escape, endpoint edge yang belum dideklarasikan
**dibuat otomatis** (edge tidak pernah hilang diam-diam; catatannya masuk
`warnings`), argumen `nodes`/`edges` diterima dalam banyak bentuk (JSON string,
dict `{id: label}`, edge string `"A -> B: label"`, alias `source`/`target`), dan
output Mermaid dijamin sintaks dasarnya sebelum dirender `mermaid.render()` di
frontend. Jalur kedua tetap terbuka: model boleh menulis fence ```mermaid
sendiri (atau mengirim sumber Mermaid lewat argumen `mermaid`) dan markdown
renderer mendeteksinya. Payload tool juga disimpan sebagai artefak
(`meta.diagrams`) sehingga kartu diagram di UI tidak bergantung pada model
menyalin sumbernya ke jawaban.

## 6. Metodologi testing

| Lapis | Sasar | Cara |
|---|---|---|
| Unit provider | `OpenAIProtocolProvider.stream()` | `httpx.MockTransport` menyuntik byte SSE *nyata*: think terbelah, arguments dicicil, logprobs, usage, HTTP 401 |
| Unit tools | parsing DDG, fetch, Mermaid, kalkulator | fixture HTML + MockTransport; assert struktur |
| Integrasi | endpoint SSE + persistensi | Starlette `TestClient`, provider mock deterministik |
| E2E | seluruh stack via HTTP asli | `scripts/fake_llama_server.py` meniru llama-server (wire format identik) + `run.py --demo` |

Prinsip metodologis: **mock hanya di batas jaringan**. Parser, loop, tools,
endpoint, dan UI selalu kode produksi asli. Emulator dipilih bukan stub
in-process karena ia memvalidasi kontrak HTTP/SSE antar-proses — hal yang
persis terjadi di laptop pengguna bersama llama-server sungguhan.

## 7. Model & hardware (16 GB)

Model offline diambil langsung dari HuggingFace Hub ke `models/` dan dijalankan
`transformers` di proses backend — tidak ada server LLM sampingan. Untuk server
OpenAI-compatible (vLLM/llama.cpp/LM Studio) tersedia `hf_mode=server`.

Dulu defaultnya `Qwen/Qwen3-8B-GGUF` (Q4_K_M ≈ 6 GB) karena kombinasi langka:
reasoning `<think>`, tool-calling native, dan muat CPU-only. Naik kelas ke
Qwen3-14B Q4_K_M (≈ 9 GB) bila kualitas lebih penting dari headroom; pengguna
GPU 16 GB dapat memakai MoE Qwen3.6-35B-A3B IQ2_M yang sangat cepat.
Semua hanya perubahan konfigurasi (`ASK_HF_MODEL` + folder model), bukan kode.

## 8. Degradasi & kegagalan

Kegagalan diperlakukan sebagai *input*, bukan akhir: LLM offline → banner +
mode mock; tool offline → `tool_result` error yang dikutip model jujur;
Mermaid rusak → source + badge; klien putus → task cancel, DB konsisten.
Daftar lengkap ada di slide 15.

## 9. Reproduksibilitas

`python3 run.py --demo` memberi lingkungan deterministik lengkap (backend +
frontend + emulator) di mesin tanpa GPU/internet-eksternal; `--gguf` untuk
model asli. Seluruh klaim dokumen ini tervalidasi oleh: 15 pytest hijau,
`next build` + `tsc` bersih, dan E2E SSE yang direkam (lihat README).
