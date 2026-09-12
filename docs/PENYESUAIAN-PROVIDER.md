# Penyesuaian Provider per Mode — Ask Anything

> Cara menyetel **provider LLM** untuk tiap mode (`huggingface` lokal,
> `openai`/gateway, `mock`): lewat UI **Settings provider** maupun env, cara
> memuat **daftar model** dari endpoint, apa yang terjadi di balik layar, dan
> troubleshooting yang sudah diverifikasi terhadap server sungguhan.
>
> Bagian [8. Log percobaan nyata](#8-log-percobaan-nyata) berisi rekaman
> percobaan end-to-end dengan **model asli** (SmolLM2-135M-Instruct via
> llama.cpp) — bukan mock.

---

## Daftar isi

1. [Tiga mode provider](#1-tiga-mode-provider)
2. [Alur penyesuaian (UI → backend → provider)](#2-alur-penyesuaian-ui--backend--provider)
3. [Mode `huggingface` — server lokal / llama.cpp](#3-mode-huggingface--server-lokal--llamacpp)
4. [Mode `openai` — OpenAI API & gateway OpenAI-compatible](#4-mode-openai--openai-api--gateway-openai-compatible)
5. [Mode `mock` — demo offline tanpa LLM](#5-mode-mock--demo-offline-tanpa-llm)
6. [Memuat daftar model dari endpoint](#6-memuat-daftar-model-dari-endpoint)
7. [Troubleshooting](#7-troubleshooting)
8. [Log percobaan nyata](#8-log-percobaan-nyata)
9. [Referensi API](#9-referensi-api)

---

## 1. Tiga mode provider

| Mode | Dipakai untuk | Endpoint | Perlu API key | Env utama |
|---|---|---|---|---|
| `huggingface` (default) | Server OpenAI-compatible **lokal**: `llama-server` (llama.cpp), vLLM, LM Studio, TGI | `ASK_HF_BASE_URL` (default `http://127.0.0.1:8081/v1`) | opsional | `ASK_HF_BASE_URL`, `ASK_HF_MODEL`, `ASK_HF_API_KEY`, `ASK_THINKING` |
| `openai` | **OpenAI API** atau **gateway** OpenAI-compatible apa pun (Sumopod, OpenRouter, Together, …) | `ASK_OPENAI_BASE_URL` (default `https://api.openai.com/v1`) | ya (umumnya) | `ASK_OPENAI_BASE_URL`, `ASK_OPENAI_MODEL`, `ASK_OPENAI_API_KEY` |
| `mock` | Demo/offline: agent loop + tools + Interpreter tetap jalan, LLM di-emulasi | – | – | – |

Ketiganya memakai **protokol yang sama** (`/chat/completions` streaming), jadi
satu klien (`OpenAIProtocolProvider`) menangani mode `huggingface` dan `openai`;
perbedaannya hanya sumber konfigurasi dan `chat_template_kwargs` (khusus lokal).

```
UI Settings provider ──POST /api/settings──► settings singleton (runtime)
                                                    │
                     POST /api/chat ──► build_provider(settings)
                                                    │
                       ┌────────────────────────────┼────────────────────┐
                  huggingface                     openai                mock
             HuggingFaceProvider          OpenAIProtocolProvider    MockProvider
        (base=hf_base_url + enable_thinking)  (base=openai_base_url)   (offline)
```

---

## 2. Alur penyesuaian (UI → backend → provider)

1. **Env dibaca saat proses start** (`ASK_*`, prefix `ASK_`) → `Settings()`.
2. **UI menimpa saat runtime**: `POST /api/settings` mengubah singleton
   `settings` tanpa restart. Yang dikirim UI hanyalah field yang berubah;
   field yang tidak disentuh **tidak dikirim** sehingga nilainya tetap.
3. **Setiap request chat** membangun provider dari `settings` yang berlaku saat
   itu (`build_provider(settings)`), jadi pergantian provider langsung berlaku
   pada pesan berikutnya — tanpa restart backend.
4. **Kerahasiaan**: API key tidak pernah dikembalikan ke UI, hanya
   `hf_api_key_masked` / `openai_api_key_masked` (mis. `rah…-123`).

Aturan penting tentang **API key**:

| Yang dikirim UI | Arti | Efek |
|---|---|---|
| field tidak ada / `null` | "tidak disentuh" | key lama dipertahankan |
| `""` (string kosong) | "saya hapus key-nya" | **key dihapus** |
| `"sk-…"` | ganti key | key disimpan |

Tombol **Hapus** di samping kolom API key mengirim `""` secara eksplisit.
(Sebelumnya field kosong selalu diabaikan, sehingga key yang salah tidak bisa
dihapus — sekarang bisa.)

`provider` yang tidak dikenal ditolak **HTTP 422** dengan pesan
`provider harus salah satu dari: huggingface, openai, mock` (dulu diam-diam
jatuh ke default, jadi UI terlihat "sudah ganti" padahal tidak).

---

## 3. Mode `huggingface` — server lokal / llama.cpp

### 3.1 Lewat UI

1. Buka **Settings provider** (tombol gerigi di sidebar) → tab
   **Provider & endpoint** → pilih **huggingface**.
2. **Base URL**: `http://127.0.0.1:8081/v1` (boleh juga ditulis
   `http://127.0.0.1:8081/v1/chat/completions` — otomatis dinormalkan).
3. Klik **Muat model** → dropdown **Model** terisi dari `GET <base>/models`.
   (llama.cpp melaporkan id berupa path GGUF, mis.
   `/models/Qwen3-4B-Q4_K_M.gguf`; dropdown menampilkan label
   `Qwen3-4B-Q4_K_M` tetapi mengirim id aslinya.)
4. **API key**: isi hanya bila `llama-server` dijalankan dengan `--api-key`.
5. **Thinking (reasoning)**: kirim `chat_template_kwargs.enable_thinking`.
   Nyalakan hanya untuk model yang template-nya mendukung (Qwen3). Bila server
   menolaknya, provider otomatis mencoba ulang tanpa key itu (lihat §7).
6. **Save** → chip di header berubah menjadi `huggingface · <model>`.

### 3.2 Lewat env

```bash
ASK_PROVIDER=huggingface \
ASK_HF_BASE_URL="http://127.0.0.1:8081/v1" \
ASK_HF_MODEL="Qwen3-4B-Q4_K_M.gguf" \
ASK_HF_API_KEY="" \
ASK_THINKING=true \
python3 run.py
```

Menyalakan servernya:

```bash
llama-server -m models/Qwen3-4B-Q4_K_M.gguf --host 0.0.0.0 --port 8081 \
             --jinja -c 4096
# GPU: ASK_HF_GPU_LAYERS=99 (Apple Silicon otomatis Metal)
```

Atau sekali klik dari UI: tab **Model offline (HuggingFace)** → pilih model →
otomatis terunduh ke `models/` → **Pakai** / **Jalankan** (aplikasi yang
menyalakan `llama-server`).

### 3.3 Catatan mode lokal

- `ASK_THINKING` **hanya** dikirim pada mode `huggingface`.
- Model yang template-nya tidak punya switch thinking (Gemma 3, Llama 3.2,
  SmolLM2) sebaiknya dimatikan thinking-nya; kalaupun lupa, retry ladder
  menyelamatkannya.
- Banner kuning *"LLM lokal tidak terjangkau"* muncul bila
  `GET <hf_base_url>/models` gagal; tombol **Pakai mode mock** tersedia di sana.

---

## 4. Mode `openai` — OpenAI API & gateway OpenAI-compatible

### 4.1 Lewat UI

1. **Settings provider** → pilih **openai**.
2. **Base URL**: tempel apa adanya dari dokumentasi API. Semua bentuk ini
   setara dan dinormalkan ke `https://ai.sumopod.com/v1`:

   | Ditempel | Dinormalkan menjadi |
   |---|---|
   | `https://ai.sumopod.com` | `https://ai.sumopod.com/v1` |
   | `https://ai.sumopod.com/v1` | `https://ai.sumopod.com/v1` |
   | `https://ai.sumopod.com/v1/` | `https://ai.sumopod.com/v1` |
   | `https://ai.sumopod.com/v1/models` | `https://ai.sumopod.com/v1` |
   | `https://ai.sumopod.com/v1/chat/completions` | `https://ai.sumopod.com/v1` |
   | `ai.sumopod.com/v1` (tanpa skema) | `https://ai.sumopod.com/v1` |

   Tanpa normalisasi ini URL menjadi
   `…/v1/chat/completions/chat/completions` → **404**.
3. Klik **Muat model** → dropdown terisi dari `GET <base>/models` memakai key
   yang sedang diketik (kalau ada). Bila endpoint menolak, pesannya tampil di
   bawah kolom (mis. `API key ditolak (401)`), bukan error kosong.
4. **Model**: pilih dari dropdown, atau **✎ Ketik nama model lain…** untuk
   mengetik manual (model yang sedang aktif tetapi tidak ada di daftar tetap
   dipertahankan sebagai pilihan).
5. **API key**: tempel token. Setelah Save, kolom menampilkan
   `tersimpan (ran…-123)`; tombol **Hapus** menghapusnya.
6. **Save** → header menampilkan `openai · <model>`.

### 4.2 Lewat env (contoh gateway dari README)

```bash
ASK_PROVIDER=openai \
ASK_OPENAI_BASE_URL="https://ai.sumopod.com/v1/chat/completions" \
ASK_OPENAI_API_KEY="random_token" \
ASK_OPENAI_MODEL="qwen3.7-flash-2026-07-15" \
python3 run.py
```

OpenAI resmi cukup:

```bash
ASK_PROVIDER=openai ASK_OPENAI_API_KEY=sk-... python3 run.py
# base URL default https://api.openai.com/v1, model default gpt-4o-mini
```

### 4.3 Retry ladder (payload downgrade)

Tidak semua endpoint menerima payload lengkap. Provider mencoba bertingkat dan
menulis tiap penurunan sebagai event **`note`** di Timeline Interpreter:

| Rung | Payload | Kapan dipakai |
|---|---|---|
| 1 `penuh` | `stream_options` + `logprobs` + `chat_template_kwargs` | default |
| 2 `tanpa stream_options/logprobs` | buang `stream_options`, `logprobs`, `top_logprobs` | gateway menolak key itu (400/422) |
| 3 `payload minimal` | buang juga `chat_template_kwargs` | template tidak punya `enable_thinking` (400) |

Status yang memicu penurunan: **400, 404, 422, 500, 501, 502**. Angka 5xx
dimasukkan karena llama.cpp menjawab **HTTP 500** untuk
`logprobs is not supported with tools + stream` — padahal logprobs default
menyala dan agent selalu mengirim tools. Rung yang berhasil **diingat** per
`base_url|model`, jadi turn berikutnya tidak mengulang request yang pasti gagal.

---

## 5. Mode `mock` — demo offline tanpa LLM

```bash
python3 run.py --demo        # atau: ASK_PROVIDER=mock
```

- Tidak ada endpoint, tidak ada key; `POST /api/models` langsung menjawab satu
  model `mock-agent (offline demo)` tanpa menyentuh jaringan.
- Agent loop, tools (`web_search`, `create_diagram`, `calculator`), tracing, dan
  keempat tab Interpreter tetap berfungsi — yang di-emulasi hanya LLM-nya.
- Cocok untuk CI, screenshot dokumentasi, dan demo tanpa internet/GPU.

---

## 6. Memuat daftar model dari endpoint

Dropdown model diisi oleh **`POST /api/models`**:

```bash
curl -s localhost:8000/api/models -H 'Content-Type: application/json' \
     -d '{"provider":"openai","base_url":"https://ai.sumopod.com/v1",
          "api_key":"random_token"}'
```

```json
{"ok": true, "provider": "openai",
 "base_url": "https://ai.sumopod.com/v1",
 "url": "https://ai.sumopod.com/v1/models", "status": 200,
 "models": [{"id": "qwen3.7-flash-2026-07-15",
             "label": "qwen3.7-flash-2026-07-15"}],
 "count": 1, "active_model": "qwen3.7-flash-2026-07-15", "error": null}
```

- `provider` / `base_url` / `api_key` opsional → default ke setting aktif,
  sehingga tombol **Muat model** bisa mengetes konfigurasi **sebelum** Save.
- Bentuk jawaban server yang diterima (semua dinormalkan):

  | Server | Bentuk | Diambil dari |
  |---|---|---|
  | OpenAI / vLLM / TGI | `{"object":"list","data":[{"id":"…"}]}` | `data[].id` |
  | llama.cpp | `{"data":[{"id":"/models/x.gguf"}],"models":[{"model":"…"}]}` | `data[].id`, duplikat dibuang |
  | sebagian gateway | `["model-a","model-b"]` | elemen string |

- `label` adalah nama pendek untuk manusia (path GGUF dipangkas jadi nama
  file); `id` tetap nilai asli yang dikirim ke API.
- Endpoint mati, key salah, atau jawaban bukan JSON **tidak** menghasilkan 500:
  `{"ok": false, "error": "…"}` ditampilkan di UI.

---

## 7. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| Dropdown model kosong / "endpoint tidak memberi daftar" | server belum jalan, base URL salah, atau endpoint tidak punya `/models` | jalankan server; klik **Muat model** lagi; cek pesan di bawah kolom |
| `404` saat chat | base URL ditulis lengkap (`…/v1/chat/completions`) lalu di-*join* manual | sudah ditangani normalisasi; pastikan memakai app versi ini |
| `API key ditolak (401)` di bawah kolom model | key salah / belum di-set | isi key, atau **Hapus** key lama lalu isi yang baru |
| `note: 500 … logprobs is not supported with tools + stream` | llama.cpp menolak `logprobs` + `tools` + `stream` | otomatis turun ke rung 2; bila ingin tanpa `note`, set `ASK_LOGPROBS=false` |
| `note: 400 … template error` | template tidak mengenal `enable_thinking` | matikan **Thinking**, atau biarkan retry ladder menurunkannya |
| Jawaban kosong tanpa pesan | model menghabiskan `ASK_MAX_STEPS` untuk memanggil tool | sekarang diberi pesan eksplisit + event `note` + `stopped_reason: max_steps`; sederhanakan pertanyaan atau naikkan `ASK_MAX_STEPS` |
| Streaming berhenti tepat ±30 detik (produksi/`next start`) | proxy rewrite Next menutup koneksi idle (`experimental.proxyTimeout` default 30000 ms) | sudah di-set 300000 ms; backend juga mengirim SSE keep-alive `: keep-alive` tiap 10 dtk |
| `gguf_init_from_file_impl: GGUFv1 is no longer supported` | file GGUF versi lama (v1) | konversi dulu: `python3 scripts/gguf_v1_to_v3.py lama.gguf baru.gguf` |
| Model menjawab kosong padahal `completion_tokens` > 0 | vocab/metadata GGUF tidak cocok dengan bobot (hasil konversi pihak ketiga) | pakai GGUF resmi repo model tersebut |

---

## 8. Log percobaan nyata

Semua langkah di bawah dijalankan sungguhan (bukan mock) di Linux x86_64,
2 vCPU, RAM 3.9 GB, tanpa GPU, **tanpa akses ke huggingface.co / api.openai.com**
(jaringan sandbox hanya membuka PyPI, npm, dan github.com).

### 8.1 Menyiapkan LLM server asli

```bash
# 1. llama.cpp dibangun dari sumber (rilis biner ada di host yang diblokir)
curl -sSL -o llama.tar.gz https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/b5959
tar xzf llama.tar.gz && cd llama.cpp
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON
cmake --build build --target llama-server -j2          # → build/bin/llama-server

# 2. model GGUF terkecil yang benar-benar bisa menjawab (98.362.432 byte),
#    diambil sebagai git blob lewat api.github.com
gh api "repos/simonw/llm-smollm2/git/blobs/49f8d2e965572d8786696fdc0f921dc499867781" \
   -H "Accept: application/vnd.github.raw" > SmolLM2-135M-Instruct.Q4_1.gguf

# 3. jalankan server OpenAI-compatible (dengan API key, supaya jalur auth ikut teruji)
llama-server -m SmolLM2-135M-Instruct.Q4_1.gguf --host 0.0.0.0 --port 8081 \
             -c 4096 -t 2 --jinja --api-key rahasia-lokal-123 --no-webui
```

Model: **SmolLM2-135M-Instruct Q4_1** (92.10 MiB, 30 layer, ctx 8192,
vocab 49152, GGUF v3) — model instruct terkecil yang jawabannya masih berupa
kalimat bahasa Inggris yang benar.

### 8.2 Jawaban nyata lewat protokol OpenAI

```console
$ curl -s localhost:8081/v1/chat/completions -H "Authorization: Bearer rahasia-lokal-123" \
    -H "Content-Type: application/json" \
    -d '{"model":"/tmp/SmolLM2-135M-Instruct.Q4_1.gguf",
         "messages":[{"role":"user","content":"What is the capital of France? Answer in one short sentence."}],
         "max_tokens":60,"temperature":0.2}'
ANSWER: 'The capital of France is Paris.'
usage:  {'completion_tokens': 8, 'prompt_tokens': 42, 'total_tokens': 50}
```

### 8.3 Jawaban nyata lewat agent (SSE `/api/chat`, UI → proxy Next → backend)

```console
$ # provider huggingface, ASK_LOGPROBS=true, ASK_TEMPERATURE=0.2
Q: What is the capital of Japan? Answer in one short sentence.
  note: 500 dari http://127.0.0.1:8081/v1/chat/completions dengan payload penuh
        — mencoba ulang: tanpa stream_options/logprobs
  ANSWER: 'The capital of Japan is Tokyo.'
  usage:  prompt_tokens=884 completion_tokens=16 latency_ms=509.1 steps=1
          stopped_reason=stop
```

`note` di atas adalah retry ladder bekerja: llama.cpp menolak
`logprobs`+`tools`+`stream` (HTTP 500), provider menurunkan payload, dan jawaban
tetap sampai.

### 8.4 Daftar model terbaca dari endpoint

```console
$ curl -s localhost:8000/api/models -H 'Content-Type: application/json' \
      -d '{"provider":"huggingface"}'
{"ok":true,"url":"http://127.0.0.1:8081/v1/models","status":200,
 "models":[{"id":"/tmp/SmolLM2-135M-Instruct.Q4_1.gguf",
            "label":"SmolLM2-135M-Instruct.Q4_1"}],
 "provider":"huggingface","base_url":"http://127.0.0.1:8081/v1",
 "active_model":"/tmp/SmolLM2-135M-Instruct.Q4_1.gguf","count":1}
```

### 8.5 Stream panjang tidak lagi putus di 30 detik

Turn yang tool-nya menggantung (timeout `fetch_url` 15 dtk, dipanggil berulang):

```console
total 41.7s | keep-alive pada detik [20.7, 37.9] | data events=14
  tool_result: fetch_url gagal: …
  done | steps: 3 | stopped_reason: max_steps
```

Sebelum perbaikan, koneksi yang sama diputus proxy pada **30.06 s** dengan
`transfer closed with outstanding read data remaining`.

### 8.6 Model GGUF versi lama (v1) bisa dipakai lagi

Model pihak ketiga `tinyllamas-stories-15m` ternyata GGUF **v1** dan ditolak
llama.cpp (`GGUFv1 is no longer supported`). Konverter kecil disediakan:

```console
$ python3 scripts/gguf_v1_to_v3.py shady.gguf tinyllama-stories-15M-v3.gguf
src: version=1 tensors=57 kv=18
wrote tinyllama-stories-15M-v3.gguf: 98741952+ bytes
```

Hasilnya termuat llama.cpp dan benar-benar menghasilkan teks:

```console
$ curl -s localhost:8098/v1/completions -d '{"prompt":"Once upon a time, there was a little girl named","max_tokens":40}'
TEXT: ' Lily. She loved to play with her toy ball. One day, she found a big,
dirty ball in the park. She was very happy and wanted to play with it.'
```

### 8.7 Regression test

```console
$ PYTHONPATH=backend python3 -m pytest backend/tests -q
62 passed
```

17 test baru; **14 di antaranya gagal pada commit sebelum perbaikan**
(diverifikasi lewat `git worktree` di `731526f`), jadi masing-masing memagari
bug yang benar-benar terjadi:

| Test | Bug yang dipagari |
|---|---|
| `test_models_api.py` (10 test) | `POST /api/models` belum ada → dropdown model kosong |
| `test_api_key_can_be_cleared` | API key tidak bisa dihapus |
| `test_unknown_provider_is_rejected` | provider salah diterima diam-diam |
| `test_retry_drops_chat_template_kwargs` | retry mengulang key yang ditolak |
| `test_retry_on_500_logprobs_with_tools` | HTTP 500 mematikan seluruh turn |
| `test_max_steps_without_final_answer_is_reported` | jawaban kosong tanpa penjelasan |
| `test_sse_keepalive_is_sent_while_the_llm_thinks` | stream diputus proxy saat diam |

---

## 9. Referensi API

| Method & path | Fungsi |
|---|---|
| `GET /api/settings` | konfigurasi aktif (key di-*mask*, tidak pernah dikembalikan) |
| `POST /api/settings` | ubah runtime: `provider`, `hf_*`, `openai_*`, `thinking`, `temperature`, `max_steps`, `logprobs`. Field yang tidak dikirim tidak berubah; `""` pada field key = hapus key |
| `POST /api/models` | daftar model sebuah endpoint (`provider`, `base_url`, `api_key` opsional) |
| `GET /api/health` | `llm_reachable` hasil `GET <base>/models` provider aktif |
| `GET /api/hf/models` | katalog GGUF offline + status runtime llama.cpp |
| `POST /api/chat` | satu turn agent (SSE; frame `: keep-alive` tiap 10 dtk saat diam) |

Dokumen terkait: [`PANDUAN-PENGGUNA.md`](PANDUAN-PENGGUNA.md) (pemakaian UI),
[`PANDUAN-DEVELOPER.md`](PANDUAN-DEVELOPER.md) (arsitektur & menambah provider),
[`DEPLOY-COOLIFY.md`](DEPLOY-COOLIFY.md) (env produksi).
