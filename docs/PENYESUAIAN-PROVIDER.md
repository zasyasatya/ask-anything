# Penyesuaian Provider per Mode — Ask Anything

> Cara menyetel **provider LLM** untuk tiap mode (`huggingface` = inference
> lokal, `openai`/gateway, `mock`): lewat UI **Settings provider** maupun env,
> cara memuat **daftar model** dari endpoint, cara mendiagnosis endpoint yang
> error, apa yang terjadi di balik layar, dan troubleshooting yang diverifikasi
> terhadap server sungguhan.
>
> Bagian [8. Log percobaan nyata](#8-log-percobaan-nyata) berisi rekaman
> percobaan end-to-end **yang benar-benar dijalankan** (bukan mock): chat lewat
> model lokal, dan chat lewat gateway OpenAI-compatible yang menolak
> `logprobs`/`stream_options`.

---

## Daftar isi

1. [Tiga mode provider](#1-tiga-mode-provider)
2. [Alur penyesuaian (UI → backend → provider)](#2-alur-penyesuaian-ui--backend--provider)
3. [Mode `huggingface` — inference lokal / server OpenAI-compatible](#3-mode-huggingface--inference-lokal--server-openai-compatible)
4. [Mode `openai` — OpenAI API & gateway OpenAI-compatible](#4-mode-openai--openai-api--gateway-openai-compatible)
5. [Mode `mock` — demo offline tanpa LLM](#5-mode-mock--demo-offline-tanpa-llm)
6. [Memuat daftar model + mendiagnosis endpoint](#6-memuat-daftar-model--mendiagnosis-endpoint)
7. [Troubleshooting](#7-troubleshooting)
8. [Log percobaan nyata](#8-log-percobaan-nyata)
9. [Referensi API](#9-referensi-api)

---

## 1. Tiga mode provider

| Mode | Dipakai untuk | Konfigurasi utama | Perlu API key |
|---|---|---|---|
| `huggingface` (default), `hf_mode=local` | **Inference lokal**: model HuggingFace dari folder `models/` dijalankan `transformers` **di proses backend**. Tanpa llama.cpp, tanpa server tambahan. | `ASK_HF_MODEL` (repo id), `ASK_MODELS_DIR`, `ASK_HF_DEVICE`, `ASK_HF_DTYPE`, `ASK_THINKING` | – (token Hub hanya untuk repo gated) |
| `huggingface`, `hf_mode=server` | Server OpenAI-compatible yang Anda jalankan sendiri: vLLM, llama.cpp `llama-server`, LM Studio, TGI | `ASK_HF_BASE_URL`, `ASK_HF_MODEL`, `ASK_HF_API_KEY` | opsional |
| `openai` | **OpenAI API** atau **gateway** OpenAI-compatible apa pun (Sumopod/LiteLLM, OpenRouter, Together, …) | `ASK_OPENAI_BASE_URL`, `ASK_OPENAI_MODEL`, `ASK_OPENAI_API_KEY` | ya (umumnya) |
| `mock` | Demo/offline: agent loop + tools + Interpreter tetap jalan, LLM di-emulasi | – | – |

Mode `hf_mode=server` dan `openai` memakai **protokol yang sama**
(`/chat/completions`), jadi satu klien (`OpenAIProtocolProvider`) menangani
keduanya — bedanya hanya sumber konfigurasi dan `chat_template_kwargs`
(dikirim di mode server).

```
UI Settings provider ──POST /api/settings──► settings singleton (runtime)
                                                    │
                     POST /api/chat ──► build_provider(settings)
                                                    │
        ┌───────────────────────────────┬───────────┴───────────┐
        ▼                               ▼                       ▼
 provider=huggingface            provider=openai          provider=mock
 hf_mode=local │ hf_mode=server        │                       │
      ▼              ▼                 ▼                       ▼
 HFLocalProvider  HuggingFaceProvider  OpenAIProtocolProvider  MockProvider
 (transformers    (URL OpenAI-compat)  (URL OpenAI-compat)     (offline)
  di proses ini)
```

---

## 2. Alur penyesuaian (UI → backend → provider)

1. **Settings provider** memilih mode → `POST /api/settings` → singleton
   `settings` berubah **runtime** (tanpa restart).
2. Setiap `POST /api/chat` memanggil `build_provider(settings)` — jadi pergantian
   mode langsung berlaku pada pesan berikutnya.
3. API key **tidak pernah** dikirim balik ke browser: `/api/settings` hanya
   mengembalikan `*_masked` (`sk-…dDfQ`).
4. Field key yang **tidak dikirim** = tidak disentuh; yang dikirim `""` =
   dihapus. (Sebelumnya key salah tidak bisa dibuang.)
5. `provider` tak dikenal → **HTTP 422**, bukan diam-diam jatuh ke default.
6. Base URL dinormalkan saat disimpan: `https://host/v1/chat/completions` →
   `https://host/v1`.

---

## 3. Mode `huggingface` — inference lokal / server OpenAI-compatible

### 3.1 Inference lokal (default)

Tab **Model offline (HuggingFace)**:

1. **Cari** — ketik repo id (`deepseek-ai/DeepSeek-V4.1-Flash`) atau kata kunci
   (`qwen3`, `gemma`). Repo id yang diketik persis selalu di-resolve langsung ke
   `GET /api/models/{repo}`, jadi tidak bergantung pada peringkat pencarian.
2. **Download** — hanya file yang dibutuhkan: `config.json`,
   `generation_config.json`, tokenizer (`tokenizer*.json`, `*.model`,
   `vocab*`, `merges.txt`, `chat_template.jinja`), `*.safetensors` +
   `*.index.json`, dan `modeling_*.py`/`configuration_*.py` untuk repo
   `trust_remote_code`. Yang dilewati: README, gambar, ONNX/OpenVINO/TensorRT,
   GGUF, `original/`, `*.bin` (bila ada safetensors).
3. File masuk ke **`models/<organisasi>/<nama>/`** + manifest
   `.ask-anything.json` (repo id, jumlah file, parameter, waktu unduh).
   Download **per file** dengan resume (`Range`), dan beberapa repo boleh
   diunduh bersamaan.
4. **Pakai & muat** → `POST /api/hf/models/use` → `hf_provider=huggingface`,
   `hf_mode=local`, `hf_model=<repo>`, lalu engine memuat model **di background**
   (HTTP tidak menunggu); UI mem-poll `GET /api/hf/runtime` sampai `ready`.

Kebutuhan: `pip install -r backend/requirements-local.txt`
(torch + transformers). Tanpa itu backend tetap jalan, mode `openai`/`mock`
tetap bisa dipakai, dan UI menampilkan petunjuk install.

```bash
python3 run.py --install-local            # pasang torch + transformers
python3 run.py --search qwen3             # cari model
python3 run.py --model Qwen/Qwen3-1.7B    # unduh + jadikan aktif + jalankan
```

**Auto-load saat startup** (`app/main.py` lifespan, sebelum `yield`):
urutan pemilihan target load — (1) `ASK_HF_MODEL` bila `models/<repo>` ada
`config.json`, (2) `models/.active.json` (model terakhir yang dipakai —
mencakup folder di luar `models/`), (3) model paling baru yang `complete`
di `models/`. Load berjalan **di background** (`engine.start_load`):
`/api/health` langsung menjawab dengan `local_llm_state: "loading"`, UI
menampilkan loading screen (banner + kartu berdetik), dan chat yang masuk
selama load **menunggu** sampai engine `ready` (bukan error).

**Muat model dari folder mana pun** — `POST /api/hf/models/load`:

```bash
curl -X POST :8000/api/hf/models/load \
  -d '{"path": "/home/user/models/Qwen/Qwen2.5-0.5B-Instruct"}'
```

Mendaftarkan folder (menulis manifest bila belum ada), menyalakan
`provider=huggingface` + `hf_mode=local` + `hf_model`, menyimpan
`models/.active.json`, lalu mulai load. Path boleh absolut, `~/…`, atau
relatif ke root project.

**Robustnes load ("apapun modelnya")**: engine mencoba `dtype` →
`torch_dtype` → tanpa dtype (mencakup semua generasi transformers); di CPU
default dtype `auto` memakai **bfloat16** (bobot asli model Qwen2/3 — RAM
±50% lebih hemat dari fp32); prompt di-truncate ke
`max_position_embeddings` model bila riwayat terlalu panjang; pesan error
load diterjemahkan menjadi petunjuk yang bisa langsung dikerjakan (OOM →
model lebih kecil / `ASK_HF_DTYPE`, dll).

Lewat env:

```bash
ASK_PROVIDER=huggingface ASK_HF_MODE=local \
ASK_HF_MODEL=Qwen/Qwen3-1.7B ASK_MODELS_DIR=$PWD/models \
python3 run.py
```

### 3.2 Server OpenAI-compatible (`hf_mode=server`)

Bila Anda lebih suka menjalankan server sendiri (vLLM, llama.cpp, LM Studio):

```bash
ASK_HF_MODE=server ASK_HF_BASE_URL=http://127.0.0.1:8081/v1 \
ASK_HF_MODEL=Qwen3-4B python3 run.py
```

`ASK_THINKING` diteruskan sebagai `chat_template_kwargs.enable_thinking` — dan
otomatis dibuang oleh retry ladder bila template menjawab HTTP 400.

### 3.3 Tool calling pada inference lokal

Model lokal tidak mengirim `tool_calls` terstruktur; mereka menuliskannya
sebagai teks. `app/local_inference.py` mengirim skema tool ke chat template
(`apply_chat_template(tools=…)`) lalu mem-parse keluarannya:

- blok bertag `tool_call` (Qwen3/Hermes) — tag bisa terpotong antar-token,
  `streamtags.TagStreamParser` menahannya agar tidak bocor ke jawaban;
- JSON polos `[{ "name": …, "arguments": … }]` (gaya Llama-3.1);
- `arguments` berupa string JSON pun di-parse ulang.

Setelah itu agent loop menjalankannya persis seperti tool call dari API.

---

## 4. Mode `openai` — OpenAI API & gateway OpenAI-compatible

### 4.1 Lewat UI

Settings → provider **OpenAI API**:

1. **Base URL** — tempel apa adanya, termasuk URL lengkap dari contoh `curl`
   (`https://ai.sumopod.com/v1/chat/completions`). Dinormalkan ke
   `https://ai.sumopod.com/v1`.
2. **Muat model** — `GET <base>/models` mengisi dropdown; model yang sedang
   dipakai tetap dipertahankan walau tidak ada di daftar, dan ada opsi
   *✎ Ketik nama model lain…*.
3. **API key** — disimpan di backend, hanya tampil sebagai `sk-…dDfQ`.
4. **Test koneksi** — lihat [§6.2](#62-test-koneksi-diagnostik-endpoint).

### 4.2 Lewat env (contoh gateway)

```bash
ASK_PROVIDER=openai \
ASK_OPENAI_BASE_URL="https://ai.sumopod.com/v1/chat/completions" \
ASK_OPENAI_API_KEY="sk-…" \
ASK_OPENAI_MODEL="qwen3.7-flash-2026-07-15" \
python3 run.py --provider openai
```

### 4.3 Retry ladder + fallback non-streaming

Request pertama adalah payload **penuh**:

```json
{"model": "…", "messages": […], "temperature": 0.7, "max_tokens": 2048,
 "stream": true, "stream_options": {"include_usage": true},
 "tools": […], "logprobs": true, "top_logprobs": 4}
```

Bila ditolak, provider turun bertingkat:

| Rung | Payload | Alasan nyata |
|---|---|---|
| 1 | penuh | – |
| 2 | tanpa `stream_options` & `logprobs` | gateway menolak `stream_options` (400/422); server menolak `logprobs`+`tools`+`stream` (**500**) |
| 3 | + tanpa extras (`chat_template_kwargs`) | template tanpa `enable_thinking` menjawab 400 |
| 4 | + tanpa `tools` | gateway yang tidak mendukung function calling |
| 5 | **non-streaming** (bentuk contoh `curl`), lalu tanpa `tools` | semua bentuk streaming ditolak |

Status yang memicu penurunan: `400, 404, 413, 415, 422, 500, 501, 502, 503`.
`401/403/429` **tidak** di-retry — itu masalah key/kuota, bukan bentuk payload,
jadi langsung dilaporkan.

Rung yang berhasil **diingat** per `base_url|model`
(`OpenAIProtocolProvider._payload_memory`), jadi turn berikutnya tidak mengulang
request yang pasti gagal. Setiap penurunan muncul sebagai event `note` di
timeline *Mechanistic Interpreter*.

Tiga kasus yang dulu berakhir sebagai **bubble kosong** kini dilaporkan:

- error yang dikirim **di dalam** stream dengan HTTP 200
  (`data: {"error": {…}}` — LiteLLM/OpenAI melakukannya);
- stream 200 yang isinya kosong (hanya `data: [DONE]`);
- `choices[0].message` kosong pada jawaban non-streaming.

---

## 5. Mode `mock` — demo offline tanpa LLM

```bash
ASK_PROVIDER=mock python3 run.py
```

Agent loop, tools, tracing, dan keempat tab Interpreter tetap berjalan penuh —
hanya LLM-nya yang di-emulasi. Cocok untuk demo tanpa jaringan dan untuk test.

---

## 6. Memuat daftar model + mendiagnosis endpoint

### 6.1 `POST /api/models` — daftar model

`GET <base>/models` di-probe, lalu semua bentuk jawaban dinormalkan:

| Server | Bentuk jawaban | Yang diambil |
|---|---|---|
| OpenAI / vLLM / TGI / LiteLLM | `{"object":"list","data":[{"id":"…"}]}` | `data[].id` |
| llama.cpp | `{"data":[{"id":"/models/x.gguf"}],"models":[{"model":"…"}]}` | `data[].id`, duplikat dibuang |
| sebagian gateway | `["model-a","model-b"]` | item string |

Endpoint mati / key salah / bukan JSON → `{"ok": false, "error": …}` — **bukan**
HTTP 500, jadi UI bisa menampilkannya di samping field.

### 6.2 `POST /api/models/test` — diagnostik endpoint

Inilah jawaban untuk *"kenapa masih error?"*. Endpoint menjalankan tiga request
sungguhan dan melaporkan masing-masing apa adanya:

1. `GET <base>/models` — endpoint hidup? key diterima? model terdaftar?
2. `POST <base>/chat/completions` **non-streaming** — bentuk persis contoh `curl`
3. `POST <base>/chat/completions` **streaming** — yang dipakai aplikasi

Jawabannya per-check: status HTTP, latensi, cuplikan jawaban/pesan server, dan
hint. Contoh keluaran nyata:

```
ok: False | hint: API key ditolak endpoint. Periksa key-nya …
   ✗ GET  http://…/v1/models                 | HTTP 401 | Authentication Error, No api key passed in.
   ✗ POST chat/completions (non-streaming)   | HTTP 401 | Authentication Error, No api key passed in.
   ✗ POST chat/completions (streaming)       | HTTP 401 | Authentication Error, No api key passed in.
```

Hint yang dikenali: key ditolak (401/403), model tidak ada (`model_not_found`),
`logprobs` ditolak, konteks terlalu panjang, rate limit (429), URL salah (404),
`tools` ditolak, error server 5xx.

Bila model yang dikonfigurasi **tidak ada** di daftar `/models`, itu dilaporkan
sebagai kegagalan tersendiri (`Nama model`) — walau chat kebetulan tetap
dijawab, karena yang diminta bukan model yang dikonfigurasi.

---

## 7. Troubleshooting

| Gejala | Sebab | Aksi |
|---|---|---|
| `HTTP 401: Authentication Error, No api key passed in.` | key kosong/salah | isi API key; pastikan key untuk base URL itu (LiteLLM menolak key dari host lain) |
| `HTTP 404 … does not exist` | nama model tidak sama persis | **Muat model** lalu pilih dari daftar |
| `note: 400 … mencoba ulang: tanpa stream_options/logprobs` | gateway menolak sebagian payload | normal — ladder bekerja. Bila ingin tanpa `note`: `ASK_LOGPROBS=false` |
| Jawaban muncul tapi lambat di awal | fallback non-streaming dipakai | normal untuk gateway yang menolak streaming; lihat `note` fallback |
| `endpoint menjawab 200 tetapi tidak mengirim isi apa pun` | stream kosong (model/timeout di sisi gateway) | jalankan **Test koneksi**; perkecil `ASK_MAX_TOKENS` |
| `TLS/SSL connection has been closed` di `/api/health` | backend tidak bisa menjangkau host (DNS/firewall/proxy) | cek dari mesin backend, bukan browser |
| Inference lokal: `PyTorch + transformers belum ter-install` | stack lokal belum dipasang | `python3 run.py --install-local` |
| Inference lokal (Windows): `OSError: [WinError 1114] A dynamic link library (DLL) initialization routine failed … c10.dll` | instalasi PyTorch rusak / setengah jadi (build CPU-CUDA tercampur, file korup oleh antivirus/OneDrive, atau Visual C++ Redistributable hilang) | `python run.py --install-local` — launcher kini *menyeriusi* probe (import + operasi kecil) dan bila torch "ada di pip tapi tidak jalan", otomatis uninstall `torch*` lalu pasang ulang dari CPU wheels `https://download.pytorch.org/whl/cpu`. Bila masih gagal: pasang [VC++ Redistributable 2015-2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe), matikan sementara antivirus/OneDrive, atau hapus `.venv` lalu install ulang |
| Inference lokal: `Memori tidak cukup` | model terlalu besar untuk RAM/VRAM | pilih model lebih kecil, atau `ASK_HF_DEVICE=cpu` + `ASK_HF_DTYPE=bfloat16` |
| Download: `repo privat/gated` | repo butuh persetujuan (mis. DeepSeek) | isi **Token HuggingFace** atau `ASK_HF_TOKEN` |
| Download macet | koneksi putus | klik **Download** lagi — unduhan per file di-resume lewat `Range` |
| `trust_remote_code` diminta | repo memakai kode kustom | `ASK_HF_TRUST_REMOTE_CODE=1` bila Anda mempercayai repo itu |

---

## 8. Log percobaan nyata

Semua keluaran di bawah disalin dari perintah yang benar-benar dijalankan
(backend uvicorn + gateway OpenAI-compatible + model HuggingFace nyata).

### 8.1 Inference lokal: model dimuat di proses backend

```console
$ curl -s localhost:8000/api/hf/models | jq -c '.models, .engine.state, .deps'
[{"repo_id":"ask-anything/TinyLlama-Test","ready":true,"size_bytes":368393}] "idle"
{"available":true,"torch":"2.14.0+cu130","transformers":"5.17.0","device":"cpu"}

$ curl -s -X POST localhost:8000/api/hf/models/use \
      -d '{"repo_id":"ask-anything/TinyLlama-Test","load":true}' -H 'content-type: application/json' | jq -c '.engine.state'
"loading"                      # HTTP tidak menunggu; UI mem-poll

$ curl -s localhost:8000/api/hf/runtime | jq -c '{state,running,device,dtype,params}'
{"state":"ready","running":true,"device":"cpu","dtype":"torch.float32","params":89280}

$ curl -s localhost:8000/api/health
{"status":"ok","provider":"huggingface","hf_mode":"local",
 "model":"ask-anything/TinyLlama-Test","llm_reachable":true,
 "local_llm":true,"local_llm_state":"ready"}
```

Chat lewat SSE (UI → proxy Next → backend):

```console
$ curl -sN -X POST localhost:3000/api/chat -d '{"message":"halo dunia apa kabar"}' | grep -c 'data: '
34

$ # ringkasan event satu turn:
event: {'start': 1, 'meta': 1, 'note': 2, 'delta': 27, 'usage': 1, 'done': 1, 'agent_done': 1}
note : inference lokal: ask-anything/TinyLlama-Test di cpu (torch.float32) — 18 token prompt
done : stopped_reason=stop
```

Tool call dari model lokal benar-benar menjalankan tool (test
`test_local_tool_call_runs_the_tool`): teks `tool_call` di-parse menjadi
`{"name":"web_search","arguments":{"query":"harga emas"}}`, tool dijalankan, dan
blok JSON-nya tidak bocor ke jawaban.

### 8.2 Gateway OpenAI-compatible yang menolak `logprobs`

Gateway tiruan bergaya LiteLLM (mewakili `ai.sumopod.com`): menolak request
tanpa key dengan **401** dan menolak `logprobs`/`stream_options` dengan **400**.

```console
$ curl -s -X POST localhost:8000/api/settings -d '{
    "provider":"openai",
    "openai_base_url":"http://127.0.0.1:9111/v1/chat/completions",
    "openai_api_key":"sk-xW256…",
    "openai_model":"qwen3.7-flash-2026-07-15"}' | jq -c '.openai_base_url'
"http://127.0.0.1:9111/v1"        # URL contoh curl dinormalkan

$ curl -s -X POST localhost:8000/api/models -d '{"provider":"openai"}' | jq -c '.count,.models[0].id'
2
"qwen3.7-flash-2026-07-15"
```

Test koneksi (semua hijau):

```console
$ curl -s -X POST localhost:8000/api/models/test -d '{}'
ok: True | base: http://127.0.0.1:9111/v1
  ✓ GET  /v1/models                        | HTTP 200 |  3 ms | 2 model terdaftar
  ✓ POST chat/completions (non-streaming)  | HTTP 200 |  3 ms | Halo! Semoga harimu menyenangkan. ✨
  ✓ POST chat/completions (streaming)      | HTTP 200 | 12 ms | data: {"id":"chatcmpl-1",…
```

Chat sungguhan — ladder bekerja, jawaban tetap keluar:

```console
$ curl -sN -X POST localhost:8000/api/chat -d '{"message":"Say hello in a creative way"}'
event: {'start': 1, 'meta': 1, 'note': 1, 'delta': 6, 'usage': 1, 'done': 1, 'agent_done': 1}
note : 400 dari http://127.0.0.1:9111/v1/chat/completions dengan payload penuh
       — mencoba ulang: tanpa stream_options/logprobs
jawab: 'Halo! Semoga harimu menyenangkan. ✨'

$ # payload yang benar-benar dilihat gateway:
req1: [max_tokens, messages, model, stream, temperature, tools]              ← 200 (turn sebelumnya sudah di rung 2)
req2: [logprobs, max_tokens, messages, model, stream, stream_options,
       temperature, tools, top_logprobs]                                    ← 400
req3: [max_tokens, messages, model, stream, temperature, tools]             ← 200 ✔
```

Key salah dan model salah dilaporkan berbeda:

```console
$ curl -s -X POST localhost:8000/api/models/test -d '{"provider":"openai","api_key":"sk-palsu"}'
ok: False | hint: API key ditolak endpoint. Periksa key-nya …
   ✗ GET /v1/models | HTTP 401 | Authentication Error, No api key passed in.

$ curl -s -X POST localhost:8000/api/models/test -d '{"provider":"openai","model":"qwen-typo"}'
ok: False | hint: Pilih nama model persis dari daftar (tombol **Muat model**) …
   ✓ GET /v1/models | 2 model terdaftar
   ✗ Nama model     | `qwen-typo` tidak ada di daftar model endpoint

$ curl -s -X POST localhost:8000/api/models/test -d '{"provider":"openai","base_url":"http://127.0.0.1:9999/v1"}'
ok: False | hint: Koneksi putus saat request chat — cek timeout proxy atau nama host.
   ✗ GET http://127.0.0.1:9999/v1/models | ConnectError: All connection attempts failed
```

> Catatan kejujuran: sandbox tempat perubahan ini dibuat **tidak dapat**
> menjangkau `ai.sumopod.com` maupun `huggingface.co` (TLS ditutup di egress),
> jadi percobaan di atas memakai gateway tiruan yang meniru perilaku LiteLLM
> (401 tanpa key, 400 untuk `logprobs`). Terhadap endpoint asli Anda, jalankan
> **Settings → Test koneksi** — keluarannya sama bentuknya dan memakai server
> yang sesungguhnya.

### 8.3 Regression test

```console
$ .venv/bin/python -m pytest backend/tests -q
100 passed

$ cd frontend && npx tsc --noEmit && npm run build
✓ Compiled successfully · ✓ Finished TypeScript · 4 route (/, /panduan, /developer, /_not-found)
```

Test yang menutup perubahan ini antara lain: `test_openai_compat.py` (error di
dalam stream, 401 tanpa retry, `tools` ditolak, fallback non-streaming,
stream kosong), `test_diagnostics.py` (semua bentuk kegagalan endpoint),
`test_hf_models.py` (pemilihan file, resume `Range`, progress, multi-model,
hapus), `test_local_inference.py` (load + generate model nyata, parser tag yang
terpotong antar-token, tool call → tool dijalankan, SSE `/api/chat`).

---

## 9. Referensi API

| Endpoint | Fungsi |
|---|---|
| `POST /api/chat` | satu turn agent, SSE (`start`, `meta`, `prompt`, `thinking`, `delta`, `logprobs`, `note`, `tool_call`, `tool_result`, `usage`, `done`, `error`, `agent_done`) + keep-alive tiap 10 dtk |
| `GET/POST /api/settings` | baca/ubah settings runtime (key hanya dikirim, tak pernah dibaca balik) |
| `POST /api/models` | daftar model endpoint (`{ok, models[], error}`) |
| `POST /api/models/test` | diagnostik endpoint (3 request nyata + hint) |
| `GET /api/hf/search?q=` | cari model di HuggingFace Hub |
| `GET /api/hf/models` | model di `models/` + progres + status engine |
| `GET /api/hf/downloads` | progres semua unduhan (di-poll UI) |
| `POST /api/hf/models/download` | mulai/resume unduhan `{repo_id}` |
| `POST /api/hf/models/cancel` | batalkan unduhan |
| `POST /api/hf/models/use` | jadikan model aktif `{repo_id, thinking, load}` |
| `POST /api/hf/models/delete` | hapus folder model |
| `GET /api/hf/runtime` · `POST /api/hf/runtime/stop` | status engine · lepas dari memori |
| `GET /api/health` | `provider`, `hf_mode`, `model`, `llm_reachable`, `local_llm_state` |
