# Dokumentasi Teknis — Ask Anything

Referensi mendalam: **setiap paket yang dipakai, apa fungsinya, dan bagaimana
cara kerjanya** di dalam kode ini. Ditulis dari sumber yang benar-benar ada di
repo (bukan generik) — kalau sebuah paket hanya opsional, itu dikatakan.

> Dokumen ini melengkapi [`PANDUAN-DEVELOPER.md`](PANDUAN-DEVELOPER.md)
> (arsitektur, setup, API, testing) dan [`METODOLOGI.md`](METODOLOGI.md)
> (alasan desain). Untuk perilaku UI: [`PANDUAN-PENGGUNA.md`](PANDUAN-PENGGUNA.md).

---

## Daftar isi

1. [Peta dependensi](#1-peta-dependensi)
2. [Paket runtime frontend](#2-paket-runtime-frontend)
3. [Paket toolchain frontend](#3-paket-toolchain-frontend)
4. [Paket runtime backend](#4-paket-runtime-backend)
5. [Paket opsional: inference lokal](#5-paket-opsional-inference-lokal)
6. [Paket testing & capture](#6-paket-testing--capture)
7. [Cara kerja: aliran data satu run](#7-cara-kerja-aliran-data-satu-run)
8. [Cara kerja: agent loop & event trace](#8-cara-kerja-agent-loop--event-trace)
9. [Cara kerja: provenance tool & registri sitasi](#9-cara-kerja-provenance-tool--registri-sitasi)
10. [Cara kerja: provider OpenAI-compatible (retry ladder)](#10-cara-kerja-provider-openai-compatible-retry-ladder)
11. [Cara kerja: HuggingFace Hub → models/ → transformers](#11-cara-kerja-huggingface-hub--models--transformers)
12. [Cara kerja: markdown → DiagramBlock → GraphView](#12-cara-kerja-markdown--diagramblock--graphview)
13. [Cara kerja: layout graph deterministik](#13-cara-kerja-layout-graph-deterministik)
14. [Cara kerja: layar penuh & refit kanvas](#14-cara-kerja-layar-penuh--refit-kanvas)
15. [Cara kerja: navbar collapsible & lebar ruang chat](#15-cara-kerja-navbar-collapsible--lebar-ruang-chat)
16. [Cara kerja: Interpreter sebagai pembaca log](#16-cara-kerja-interpreter-sebagai-pembaca-log)
17. [Cara kerja: persistensi SQLite & replay](#17-cara-kerja-persistensi-sqlite--replay)
18. [Ukuran, batas, dan keputusan teknis](#18-ukuran-batas-dan-keputusan-teknis)

---

## 1. Peta dependensi

```
frontend/package.json ──┬── runtime : next, react, react-dom, mermaid
                        └── dev     : typescript, tailwindcss, postcss,
                                      autoprefixer, vitest, jsdom,
                                      @testing-library/{react,dom}, @types/*

backend/requirements.txt ─┬── serving  : fastapi, uvicorn[standard]
                          ├── HTTP     : httpx
                          ├── model    : pydantic, pydantic-settings
                          ├── parsing  : beautifulsoup4 (→ soupsieve)
                          └── testing  : pytest, pytest-asyncio

backend/requirements-local.txt ── opsional: torch, transformers, accelerate,
                                          safetensors, sentencepiece, huggingface_hub

scripts/capture_screenshots.py ── playwright (dipakai juga oleh smoke_ui.py)
```

Prinsipnya: **nol dependency runtime untuk UI selain React/Next**, dan paket
berat (PyTorch) dipisah ke file requirements sendiri agar deployment API/mock
tidak ikut meng-download ~2 GB.

---

## 2. Paket runtime frontend

| Paket | Versi | Fungsi | Cara kerja di repo ini |
|---|---|---|---|
| `next` | 16.3.5 | App Router, dev server, build | `frontend/app/{page,layout,panduan,developer}`. Bukan static-export: halaman utama client component (`"use client"`) karena memakai `fetch`/SSE/`localStorage`. |
| `react` / `react-dom` | 19.3.0 | Render + hooks | Memakai `useMemo`/`useCallback` untuk layout graph (`layoutGraph` di memo, karena deterministik terhadap model), `useRef` untuk state drag agar tidak memicu render per frame, dan `useEffect` untuk sinkronisasi `localStorage`. |
| `mermaid` | 11.17.2 | Renderer SVG resmi Mermaid | Dimuat **statis** di `components/Mermaid.tsx` (`import mermaid from "mermaid"`), `initialize({startOnLoad:false, theme:"neutral", securityLevel:"strict"})` sekali per modul (flag `initialized`), lalu `mermaid.render(id, src)`. `securityLevel:"strict"` penting: sumber datang dari LLM, jadi HTML di label tidak boleh dieksekusi. Kegagalan render **tidak** melempar ke UI — dilaporkan lewat `onError` sehingga `DiagramBlock` bisa menawarkan fallback. |

Kenapa `mermaid` bukan satu-satunya renderer: renderer ini **all-or-nothing** —
satu baris cacat membuat seluruh diagram hilang, sedangkan sumber sering
dihasilkan LLM. Karena itu `GraphView` (HTML/SVG buatan sendiri) dijadikan mode
default; `Mermaid` tetap tersedia sebagai mode alternatif.

Paket yang **sengaja tidak dipakai** di frontend, dan alasannya:

| Tidak dipakai | Alasan |
|---|---|
| `react-markdown` + `remark-*` (+ ~40 paket transitif) | Kebutuhan markdown di sini kecil dan harus bisa memotong stream di tengah fenced block; renderer sendiri (`lib/markdown.tsx`, ±200 baris) lebih mudah dikendalikan dan diuji. |
| `react-flow` / `cytoscape` / `d3` | Menambah 100–500 kB untuk hal yang bisa dilakukan layout sendiri (`lib/graph/layout.ts`) dan membuat interaksi (drag node, zoom, inspektur) lebih mudah disesuaikan. |
| `zustand` / `redux` | State app = beberapa `useState` di `app/page.tsx`; tidak perlu store global. |
| `next/font` / Google Fonts | sandbox kadang memblokir CDN font; stack `Inter → ui-sans-serif → system-ui` cukup dan bebas jaringan. |

---

## 3. Paket toolchain frontend

| Paket | Versi | Cara kerja |
|---|---|---|
| `typescript` | 5.9.3 | `tsconfig.json` dengan `strict` + path alias `@/*` → root frontend. Diperiksa lewat `npm run typecheck` (`tsc --noEmit`). `tsconfig.tsbuildinfo` dipakai `incremental` agar cek ulang cepat. |
| `tailwindcss` | 3.4.19 | Build-on-demand: konten dipindai dari `./app/**/*.{ts,tsx}` + `./components/**/*.{ts,tsx}`. `theme.extend` mendaftarkan warna `accent` / `accent-soft` / `accent-ring` yang **bernilai CSS variable** (`var(--accent)`) — inilah yang membuat pemilih aksen di composer bekerja tanpa kelas dinamis: `page.tsx` menyetel `--accent` inline di root, Tailwind tinggal merujuknya. Font `sans`/`mono` juga diikat ke var. Bayangan `shadow-card` didefinisikan di sini. |
| `postcss` + `autoprefixer` | 8.5.28 / 10.5.6 | Rantai minimum: Tailwind diproses sebagai plugin PostCSS (`postcss.config.mjs`), autoprefixer menambah prefix vendor. Tidak ada plugin lain → build ringan. |
| `vitest` | 3.2.7 | Runner unit/component. `vitest.config.ts` menyetel `environment: "jsdom"`, `include: {lib,components,app}/**/*.test.{ts,tsx}`, `restoreMocks: true`, dan alias `@` (sama dengan tsconfig, supaya modul yang sama teresolusi di test & build). |
| `jsdom` | 30.0.1 | Implementasi DOM untuk vitest. **Batasannya penting**: tidak punya `ResizeObserver`, `requestFullscreen`, `scrollIntoView`, atau layout engine — makanya komponen ditulis defensif (`typeof ResizeObserver === "undefined"`, `bottomRef.current?.scrollIntoView?.()`, fallback focus mode) dan test tidak bergantung pada geometri nyata. |
| `@testing-library/react` / `dom` | 16.3.3 / 10.4.1 | Render + query by role/label/testid, `fireEvent` untuk interaksi. Tidak memakai `userEvent` (butuh environment lebih lengkap); `fireEvent` cukup untuk toggle/klik dan membuat test cepat & deterministik. |
| `@types/*` | node 22, react 19 | Tipe ambient; tidak dipanggil saat runtime. |

---

## 4. Paket runtime backend

| Paket | Versi | Cara kerja |
|---|---|---|
| `fastapi` | 0.141.1 | Router + validasi request. `app/api/routes.py` memakai `APIRouter(prefix="/api")`; body di-model dengan Pydantic (`ChatRequest`, `SettingsUpdate`, `RepoRequest`) sehingga 422 otomatis dan `_known_provider`/`_known_mode` di `field_validator` menolak nilai ngawur **sebelum** mengenai state global. `StreamingResponse` dari Starlette dipakai langsung untuk SSE (FastAPI tidak punya helper SSE sendiri). |
| `uvicorn[standard]` | 0.52.4 | ASGI server + reloader. `[standard]` menambah `httptools`/`websockets`/`watchfiles`; yang relevan di sini: implementasi HTTP parsing yang lebih cepat. `--proxy-headers` tidak diperlukan karena Next yang jadi face publik. |
| `httpx` | 0.28.1 | Client HTTP async untuk **tiga** hal: stream provider (`openai_provider`), tool browsing (`web_search`, `fetch_url`), dan diagnostik/Hub. Yang krusial: `httpx.MockTransport` dipakai test sebagai injeksi transport → pengujian parsing & retry tanpa jaringan. Timeout tool dibungkus `asyncio.wait_for(..., 30)` di loop, bukan di client, supaya batasnya milik orkestrasi. |
| `pydantic` | 2.13.5 | Model Settings + request. V2 (`model_dump`, `model_fields`). |
| `pydantic-settings` | 2.15.0 | `BaseSettings` dengan `env_prefix="ASK_"` + `extra="ignore"` → `ASK_OPENAI_MODEL` mengisi `openai_model`; variabel asing tidak membuat crash. Singleton `settings` **dimutasi runtime** oleh `update_settings()` (UI bisa ganti provider tanpa restart); `_URL_FIELDS` dinormalisasi saat tulis supaya `.../v1/chat/completions` yang tertempel di input tidak menghasilkan URL dobel. |
| `beautifulsoup4` | 4.15.0 | Ekstraksi teks halaman di `fetch_url` (`html.parser`, tanpa lxml) dan parsing hasil DuckDuckGo-lite di `web_search`. `fetch_url` melakukan `decompose()` pada `script/style/noscript/svg/iframe/nav/footer/header` lalu `_WS.sub(" ", get_text(" "))` → teks bersih satu baris per paragraf, dipotong `max_chars` (default 12 000). `web_search` memanfaatkan struktur tabel lite: `<a href="http…">` + sel snippet tetangga (`find_parent("td") → find_next_sibling("td")`, fallback baris berikutnya). |
| `soupsieve` | 2.9.2 | Dependency CSS-selector BeautifulSoup (dipakai `soup(["script","style",…])`). |

Struktur paket backend dibuat **tanpa framework agent** (LangChain/LlamaIndex
dan sejenisnya): loop ReAct-nya ±300 baris dan justru karena itu bisa
menghasilkan trace mekanistik yang presisi — sesuatu yang sulit dicapai kalau
orkestrasi didelegasikan ke library.

---

## 5. Paket opsional: inference lokal

Di `backend/requirements-local.txt`, **tidak** dipasang otomatis:

| Paket | Batas | Peran |
|---|---|---|
| `torch` | ≥2.2 | Tensor + device. `local_inference` memilih `cuda → mps → cpu`, dan `torch.set_num_threads()` dari `ASK_HF_THREADS` (0 = serahkan ke torch). |
| `transformers` | ≥4.46 | `AutoTokenizer` + `AutoModelForCausalLM`; `TextIteratorStreamer` untuk streaming token. |
| `accelerate` | ≥1.0 | Device/placement saat load. |
| `safetensors` | ≥0.45 | Format bobot yang diunduh (aman, tanpa pickle). |
| `sentencepiece` | ≥0.2 | Tokenizer model tertentu (Qwen/Llama Lama). |
| `huggingface_hub` | ≥0.25 | Unduhan Hub dengan resume (`Range`). |

Cara kerjanya dirangkum di §11. Kalau paket tidak ada, backend **tetap jalan**:
`dependencies()` melaporkan `available: false` + `install_hint`, UI menampilkan
petunjuk, dan provider `openai`/`mock` tetap berfungsi.

---

## 6. Paket testing & capture

| Paket | Versi | Cara kerja |
|---|---|---|
| `pytest` | 9.1.1 | `backend/pytest.ini` → `asyncio_mode=auto` (test async tanpa dekorator), `testpaths=tests`. `conftest.py` memaksa `ASK_PROVIDER=mock` + DB sementara **sebelum** import app, dan fixture `client` menjalankan `TestClient(app)` dengan `raise_server_exceptions=False` supaya error handler ikut teruji. |
| `pytest-asyncio` | 1.4.0 | Event loop per test; `httpx.AsyncClient` dengan `MockTransport` dibuang di `finally`. |
| `playwright` | 1.62.0 | Dipakai `scripts/capture_screenshots.py` (foto dokumentasi) dan `scripts/smoke_ui.py` (pemeriksaan UI end-to-end). `sync_playwright` → `chromium.launch(executable_path=…, args=…, env=…)`; kalau Chromium tidak bisa diunduh dari CDN, binary dari paket npm `@sparticuz/chromium` bisa dipakai lewat `CHROME_EXE` (lib & `fonts.conf` di sampingnya dideteksi otomatis). Tanpa `FONTCONFIG_FILE` yang benar, teks pada screenshot **tidak ter-render** — jebakan yang dicatat di header skrip. |
| `brotli` | 1.2.0 | Hanya untuk mengekstrak arsip `@sparticuz/chromium` (`chromium.br`) di lingkungan tanpa akses CDN. Bukan dependensi aplikasi. |

---

## 7. Cara kerja: aliran data satu run

```
Browser (React)                Next dev (rewrite)          FastAPI                    LLM
──────────────                 ──────────────────          ────────                   ───
POST /api/chat {msg} ────────►  proxy same-origin  ───────►  chat():
                                                            • db.new_conversation()
                                                            • history = db.list_messages()
                                                            • queue = asyncio.Queue()
                                                            • task = create_task(runner)
                                 SSE  data: {type:"start"}  ◄── emit({"type":"start",…})
                                 SSE  data: {type:"delta"}  ◄── trace() per token ──────── stream()
                                 SSE  data: {type:"tool_call"}                            │
                                 SSE  data: {type:"tool_result"} ◄── tool.run(args, ctx) ─
                                 SSE  data: {type:"citations"}   ◄── finalize_answer()
                                 SSE  data: {type:"done"}
                                                            • db.add_message(assistant, meta={sources,citations,…})
                                                            • queue.put(None) → stream ditutup
GET /api/conversations/{id} ─────────────────────────────►  messages + trace  (replay penuh)
```

Tiga hal yang disengaja di desain ini:

1. **`queue` sebagai pemisah** — `run_agent` tidak mengembalikan jawaban di akhir,
   tapi menulis event ke antrean yang dikonsumsi generator SSE. Konsekuensinya:
   konsumen bisa putus di tengah tanpa membatalkan kerja model, dan `finally`
   mem-`cancel()` task hanya kalau belum selesai.
2. **Keep-alive** — komentar `": keep-alive\n\n"` tiap 10 s mencegah proxy
   (rewrite Next, nginx, Coolify) menutup stream yang diam saat model berpikir;
   `experimental.proxyTimeout` di `next.config.ts` dinaikkan ke 300 000 ms untuk
   alasan yang sama.
3. **Satu sumber kebenaran** — `trace()` menulis ke SQLite **dan** men-emit ke
   stream dengan payload yang sama, jadi UI live dan replay tidak pernah beda.

---

## 8. Cara kerja: agent loop & event trace

`run_agent()` (`app/agent/loop.py`) = ReAct dengan pagar pengaman:

```python
for step in range(settings.max_steps):
    async for ev in provider.stream(llm_messages, tool_schemas(), …):
        thinking / delta / logprobs / usage / tool_calls / note / error / done
    if not collected_calls:              # model selesai
        break
    llm_messages.append(assistant+tool_calls)   # protokol OpenAI
    for call in collected_calls:
        result = await asyncio.wait_for(tool.run(call["arguments"], ctx), 30)
        llm_messages.append({"role":"tool","tool_call_id":…, "content":json})
    llm_messages.append(system TOOL_RESULT_HINT)
    llm_messages.append(system sources.prompt_block())   # daftar sumber bernomor
```

Event yang di-trace (tiap event otomatis memakai `t_ms` relatif ke awal run dan
`step`), dikelompokkan per keperluan UI:

| Event | Kapan | payload kunci | Dipakai di |
|---|---|---|---|
| `meta` | awal run | provider, model, temperature, max_tokens, max_steps, logprobs, tools | Metrik, baris `start` log |
| `prompt` | sebelum langkah 1 | system, messages, tools schema, message_count | tab LLM |
| `llm_request` | tiap langkah | messages persis, tools, sampling | tab LLM + baris `request #n` |
| `thinking` | per delta | text | diringkas jadi `N chunk · B byte` |
| `delta` | per token jawaban | text | **tidak** ditempel ke log; diringkas `N delta · B byte` |
| `logprobs` | per batch token | items[{token,logprob,top}] | chip token di LLM |
| `llm_response` | tiap langkah | text, thinking, finish_reason, tool_calls, chars, duration_ms | baris `response #n` |
| `tool_call` | per panggilan | id, name, arguments, source, args_preview | baris `tool.exec` (running) |
| `tool_result` | per hasil | id, name, source, label, summary, ok, hits, new_sources, error, duration_ms, data | baris `tool.result` + tab Tools |
| `sources` | setelah tool browser | total, items[], block | tab Sumber |
| `note` | catatan provider / “0 hasil” / max_steps | message, status, tool | baris `note:*` (amber) |
| `usage` | per langkah | prompt/completion/total tokens | Metrik |
| `citations` | akhir | status, total, cited[], uncited[], invalid[], detail, sources[] | baris `citations` + bar Sitasi |
| `done` | akhir run | answer, stopped_reason, steps, latency_ms | baris `finish` |
| `error` | kegagalan provider | message, status, hint | baris merah + bubble |

Pagar pengaman yang perlu diketahui: kalau `max_steps` habis sementara model
masih meminta tool, jawaban **tidak** dibiarkan kosong — `stopped_reason =
"max_steps"`, sebuah `note` dikirim, dan teksnya memberi tahu persis apa yang
harus dinaikkan/diubah.

---

## 9. Cara kerja: provenance tool & registri sitasi

**Provenance** dideklarasikan di alatnya, bukan disimpulkan UI:

```python
# app/tools/base.py
@dataclass
class Tool:
    name: str; description: str; parameters: dict; run: Callable
    source: str = "compute"      # "browser" | "diagram" | "compute"
    evidence: bool = False       # hasil = bukti eksternal?

@dataclass
class ToolResult:
    summary: str
    data: dict
    ok: bool = True              # False = kegagalan tertangani
    hits: int | None = None      # None = bukan hasil pencarian; 0 = kosong
```

`hits` membedakan tiga keadaan yang kalau disatukan akan menipu: `None`
(diagram/kalkulator tidak punya "jumlah hasil"), `0` (browser hidup tapi tidak
menemukan apa pun), dan `>0`. UI memetakannya ke `ok` / `0 hasil` / `gagal`.

Registri sitasi (`app/sources.py`) bekerja dalam empat tahap:

1. **Kumpul** — `register_tool_result()` menyerap payload: `web_search.results[*]`
   jadi entri `read=False`, `fetch_url` jadi `read=True`. Dedup per URL: halaman
   yang pertama muncul sebagai hasil pencarian lalu dibaca penuh **mempertahankan
   nomornya** (agar `[1]` tidak bergeser di tengah run) tetapi naik status ke
   `read=True` dan boleh mendapat judul lebih baik.
2. **Umpan balik** — `prompt_block()` menyisipkan daftar bernomor ke
   `llm_messages` tepat setelah hasil tool, plus instruksi menulis `[n]`. Bila
   kosong, bloknya secara eksplisit melarang model mengarang nomor.
3. **Verifikasi** — `report()` mencari `\[(\d{1,3}(?:[,;-]\d+)*)\]`, membagi
   hasilnya jadi `cited` / `uncited`, dan mencatat `invalid` (nomor di luar
   daftar) — angka yang salah **tidak disembunyikan**, ditandai.
4. **Jaminan** — `finalize_answer()` menjamin jawaban tetap dapat diperiksa:
   status `cited` (model sudah benar), `appended` (model lupa → blok `## Sumber`
   disisipkan), `no-evidence` (tidak ada bukti web → tidak ada yang diarang),
   `na` (run tidak menyentuh browser).

Yang **tidak** dianggap sumber: keluaran `create_diagram` dan `calculator`.
Diagram tetap bisa dilihat: payload `create_diagram` disimpan sebagai artefak
(`meta.diagrams` + event `tool_result`/`agent_done`) dan dirender UI sebagai
kartu graph interaktif, terpisah dari mekanisme sitasi.
Alasannya eksplisit di kode — konten yang dibangkitkan bukan bukti eksternal,
dan memperbolehkannya disitasi berarti mengizinkan agent mengutip dirinya
sendiri. Frontend melakukan pengecekan yang sama (`sourceOf()` memetakan tool
tak dikenal ke `compute`, bukan `browser`).

---

## 10. Cara kerja: provider OpenAI-compatible (retry ladder)

`OpenAIProtocolProvider.stream()` membuka `POST {base}/chat/completions` dengan
`stream:true` dan mengurai baris `data:` menjadi `StreamEvent` normal
(`thinking`, `delta`, `logprobs`, `usage`, `tool_calls`, `done`, `error`,
`note`). Bila server menolak payload, ia **turun anak tangga**, bukan langsung
gagal:

```
tools + logprobs + stream_options
   → tanpa stream_options
   → tanpa logprobs
   → tanpa tools
   → non-streaming (bentuk contoh curl)
```

Bentuk yang diterima **diingat per provider** (`reset_payload_memory()` dipakai
test agar tidak bocor antar kasus), jadi satu sesi tidak mengulang tangga yang
sama tiap pesan. Tiga penyebab "bubble kosong" dilaporkan terpisah: error di
dalam stream ber-HTTP 200 (`data: {"error":…}`), stream 200 tanpa isi, dan
`message` kosong pada respons non-streaming. 401/403/429 **tidak** di-retry —
itu urusan kredensial/kuota, dan `POST /api/models/test` mengukurnya apa adanya
(GET /models, chat non-streaming, chat streaming, masing-masing dengan
status/latensi/pesan server).

Provider lain: `HFLocalProvider` meneruskan ke mesin `transformers` di proses
yang sama; `MockProvider` menghasilkan alur agen tiruan (thinking → tool_call →
jawaban) lengkap dengan marker `[n]` **hanya bila** payload tool memang
berisi hasil — sehingga UI dan test bisa dijalankan tanpa jaringan tanpa pernah
berpura-pura punya sumber.

---

## 11. Cara kerja: HuggingFace Hub → models/ → transformers

```
/api/hf/search   →  GET {hf_endpoint}/api/models?search=…
                    (repo id persis di-resolve langsung ke /api/models/{repo})
/api/hf/models/download → hf_hub.start_download(repo)
     pilih file yang perlu saja : config*.json, tokenizer*, *.safetensors
     lewati                     : README, gambar, ONNX, GGUF, original
     *.bin hanya bila tak ada safetensors
     unduh per-file dengan resume Range + progress (DownloadState)
     manifest .ask-anything.json (repo, ukuran, waktu, file)
/api/hf/models/use → hf_hub.use_model(repo) → settings
                   → engine.start_load(path, device, dtype)
/api/hf/runtime    → status{state,device,dtype,params,generating,error,hint}
```

`local_inference.py` memuat dan melepas model **di thread** supaya event loop
tetap hidup; saat generate, `TextIteratorStreamer` dijalankan di thread kedua.
Tag khusus (`…`, blok tool-call) bisa terpotong antar token, karena itu
diparse oleh `app/streamtags.py` (buffer tahan-potong) bukan regex langsung per
delta. Error yang mungkin terjadi dilaporkan sebagai saran yang bisa
ditindaklanjuti (OOM, `trust_remote_code`, file rusak), bukan traceback telanjang.

---

## 12. Cara kerja: markdown → DiagramBlock → GraphView

```
teks jawaban (streaming) → lib/markdown.tsx
   ├─ baris "```mermaid" → DiagramBlock(source, provenance)
   │      ├─ parseMermaid(source)  → GraphModel {nodes, edges, groups, problems}
   │      ├─ mode "graph"   → GraphView (HTML/SVG interaktif)   ← default
   │      └─ mode "mermaid" → Mermaid (SVG statis) + banner fallback saat error
   ├─ marker [n]  → CiteChips (superscript, tertaut URL sumber)
   └─ lainnya     → heading / list / bold / inline code / link / blockquote / pre
```

`parseMermaid` **toleran**: tiap baris yang tidak dipahami masuk ke
`problems[]` dan dilewati, tidak pernah melempar. Bentuk node yang dikenali
`[] () {} (()) [[]] {{}} ([])`, edge `-->` `---` `-.->` `==>` dengan label
`|teks|` atau `-- teks -->`, rantai `A --> B --> C`, chaining `&`, subgraph,
mindmap, komentar. DiagramBlock menampilkan `N baris dilewati` sehingga
kehilangan sebagian grafik itu **terlihat**, bukan diam-diam.

Renderer ini dipakai bersama antara teks yang sedang di-stream dan riwayat:
`Markdown` hanya menerima `text`, `sources`, dan `diagramOrigin`.

---

## 13. Cara kerja: layout graph deterministik

`lib/graph/layout.ts` → `layoutGraph(model): LayoutResult`:

1. **Ukuran node** dihitung dari panjang label (font 12.5px, padding 12px, clamp
   3 baris) → `w`, `h`; angka ini dipakai lagi saat render agar posisi & titik
   potong edge konsisten.
2. **Ranking** longest-path pada DAG; siklus diputus dengan mengabaikan edge
   yang kembali ke rank lebih tinggi (edge-nya tetap dirender, hanya tidak
   dipakai untuk ranking).
3. **Ordering** per rank dengan iterasi barycenter (rata-rata posisi tetangga)
   untuk mengurangi persilangan edge.
4. **Koordinat** ditentukan arah (`TD` = kolom per rank; `LR` = baris per rank),
   lalu bbox subgraph dihitung dari anggotanya.

Deterministik = input yang sama menghasilkan posisi yang sama, dan itu yang
memungkinkan unit test assertion geometri (`layout.test.ts`).

---

## 14. Cara kerja: layar penuh & refit kanvas

`lib/useFullscreen.ts` membungkus Fullscreen API dengan **fallback yang jujur**:

```ts
toggle():  el.requestFullscreen()
             ├─ berhasil           → mode = "native"
             ├─ ditolak (reject)   → notice = pesan error  → mode = "fallback"
             └─ API tidak ada      →                                        "fallback"
exit():    document.exitFullscreen() (bila native) + reset state
Esc:       keluar dari mode apa pun (listener keydown)
```

Mode fallback = kartu dipasang `fixed inset-0 z-50` — secara visual sama penuh
layar, dan strip kecil di kepala kartu menulis kenapa fallback dipakai (mis.
aplikasi dibuka di iframe tanpa `allow="fullscreen"`), bukan berpura-pura
berhasil.

Refit: `GraphView` memasang `ResizeObserver` pada kontainernya; setiap perubahan
ukuran menjadwalkan satu `fit()` per frame (`requestAnimationFrame`, observer
dibersihkan di cleanup). Ditambah `fitSignal` dari DiagramBlock (naik saat
fullscreen masuk/keluar dan saat mode berganti) supaya zoom ikut menyesuaikan
ruang baru — tanpa ini diagram tetap sekecil ukuran sebelum fullscreen.
Semua jalur itu dijaga `typeof ResizeObserver === "undefined"` agar jsdom aman.

---

## 15. Cara kerja: navbar collapsible & lebar ruang chat

Navbar (`components/Sidebar.tsx`) menyimpan **satu** boolean (`aa:nav-collapsed`)
dan menurunkan semuanya darinya:

```
collapsed=false → width 268px, label lengkap, riwayat per kelompok tanggal
collapsed=true  → width  64px, ikon + title/aria-label, riwayat = rail titik
                  (tiap titik tetap <button>, bisa difokus & dipilih keyboard)
```

State awal selalu `false` lalu disinkronkan di efek pertama (`hydrated`) —
menghindari mismatch hidrasi Next yang muncul kalau `localStorage` dibaca saat
render server. Lebar diset inline agar transisi `transition-[width]` mulus dan
identik dengan nilai yang dipakai pengukuran. `Ctrl/Cmd+B` dipasang di `window`
(dilepas di cleanup) agar bekerja dari mana pun fokus berada.

Karena `main` adalah `flex-1 min-w-0` di samping `aside` yang `shrink-0`,
mengecilkan navbar **otomatis** mengembalikan ~204px ke ruang chat tanpa
pengukuran ulang. Ruang chat sendiri memakai `max-w-[1180px]` + `px-6 md:px-10`
(bukan `max-w-3xl`), dan kartu diagram/`pre` dibiarkan mengisi seluruh kolom
sehingga visual tidak tercekik lebar teks.

---

## 16. Cara kerja: Interpreter sebagai pembaca log

Interpreter tidak merender event mentah; ia memetakannya lewat fungsi murni
`buildLog(events)` (`lib/log.ts`):

```
TraceEvent[] ──► LogLine[] { tMs, durMs, step, level, actor, action,
                              status, source, detail, raw }
```

Tiga keputusan di dalamnya:

* **delta/logprobs dijumlahkan, tidak ditempel** — satu baris
  `stream · 89 delta · 625 B · 619ms` menggantikan 89 baris teks. Detailnya tetap
  bisa dibuka di tab LLM.
* **thinking diringkas per langkah** (`N chunk · B byte`) agar panel tidak jadi
  esai; isi mentahnya ada di `llm_response.thinking`.
* **status berasal dari field, bukan dari narasi** — `ok`/`hits` tool menentukan
  `ok` / `0 hasil` / `gagal`, sehingga chip chat, baris log, dan tab Tools selalu
  sepakat karena ketiganya membaca angka yang sama.

`logToText(lines)` menghasilkan kolom sejajar untuk tombol **copy log** —
salin apa yang benar-benar terjadi, bukan tangkapan layar.

---

## 17. Cara kerja: persistensi SQLite & replay

`app/db.py` memakai satu koneksi `check_same_thread=False` + `threading.Lock`
di sekeliling eksekusi (SQLite menulis serial; cukup untuk app lokal). Tiga
tabel: `conversations`, `messages`, `trace_events(conversation_id, run_id, seq,
type, payload JSON, ts)`.

Replay: `list_trace()` **meratakan payload ke tingkat atas** sehingga bentuk
event hasil replay identik dengan bentuk di SSE — frontend tidak perlu tahu
apakah datanya datang dari stream atau dari DB. Field `t_ms`/`step` ikut
tersimpan di payload, jadi log yang direkonstruksi punya timing aslinya.

---

## 18. Ukuran, batas, dan keputusan teknis

| Hal | Nilai | Alasan / akibat |
|---|---|---|
| Timeout tool | 30 s (`asyncio.wait_for`) | Satu tool yang hang tidak boleh menggantung seluruh run. |
| Kapasitas payload tool | string > 12 000 char dipotong, `results` dibatasi 8 (`_cap`) | Trace & SSE tetap ringan; yang dipotong ditandai `…[truncated]`. |
| `max_steps` | 6 (env `ASK_MAX_STEPS`) | Mencegah loop tanpa akhir; habis → `stopped_reason="max_steps"`, bukan bubble kosong. |
| SSE keep-alive | komentar tiap 10 s; `proxyTimeout` 300 s | Stream diam tidak diputus proxy. |
| Lebar ruang chat | `max-w-[1180px]`, `px-6 md:px-10` | Teks tetap nyaman dibaca, visual dapat ruang. |
| Navbar | 268px ↔ 64px | Satu nilai boolean; sisanya turunan. |
| Interpreter | 380–980px, drag, persist | Membaca JSON butuh lebar; tidak boleh memaksa user edit CSS. |
| Kartu diagram | `min(66vh, 620px)`, min 380px | Mengikuti viewport, tidak pernah setinggi kartu biasa. |
| Snippet sumber | 400 char di registri, 220 char di blok prompt | Prompt tidak membengkak, masih cukup untuk mencocokkan konteks. |
| Zoom kanvas | 25 %–250 % | Batas praktis untuk graph besar vs kecil. |

**Ukuran bundel**: `next build` menghasilkan 4 route (`/`, `/panduan`,
`/developer`, `/_not-found`). `mermaid` adalah paket terbesar di sisi klien dan
di-import **statis** oleh `DiagramBlock` (bukan dynamic import) — konsekuensi
yang diterima karena kartu diagram bisa muncul di jawaban streaming mana pun;
menunda muatnya berarti flash kosong saat fence pertama kali ter-buka.
Backend tanpa `requirements-local.txt` hanya butuh 6 paket runtime
(`fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`,
`beautifulsoup4`) + 2 paket test.

---

*Lihat juga: [`PANDUAN-DEVELOPER.md`](PANDUAN-DEVELOPER.md) untuk API &
panduan running, [`METODOLOGI.md`](METODOLOGI.md) untuk alasan desain,
[`PENYESUAIAN-PROVIDER.md`](PENYESUAIAN-PROVIDER.md) untuk integrasi provider.*
