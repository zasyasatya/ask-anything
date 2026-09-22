# Deploy ke Coolify (Docker) — Ask Anything

> Panduan men-deploy **Ask Anything** ke VPS dengan [Coolify](https://coolify.io)
> memakai `Dockerfile` di root repo: satu image, satu container, dua proses
> (FastAPI + Next.js production). Lengkap dengan env var, persistence SQLite,
> health check, uji lokal, dan troubleshooting.
> Pendamping: [`PANDUAN-DEVELOPER.md`](PANDUAN-DEVELOPER.md) ·
> [`PANDUAN-PENGGUNA.md`](PANDUAN-PENGGUNA.md).

---

## Daftar isi

1. [Yang dibangun image ini](#1-yang-dibangun-image-ini)
2. [Arsitektur di dalam container](#2-arsitektur-di-dalam-container)
3. [Langkah deploy di Coolify](#3-langkah-deploy-di-coolify)
4. [Environment variables](#4-environment-variables)
5. [Persistence — data di disk server](#5-persistence--data-di-disk-server-bukan-di-container)
6. [Uji image di lokal dulu](#6-uji-image-di-lokal-dulu)
7. [Troubleshooting](#7-troubleshooting)
8. [Catatan desain Dockerfile](#8-catatan-desain-dockerfile)

---

## 1. Yang dibangun image ini

| Berkas | Fungsi |
|---|---|
| `Dockerfile` | Multi-stage build: `frontend-builder` (npm ci + `next build`) → `backend-builder` (venv Python + requirements) → `runtime`. |
| `.dockerignore` | Buang `.git`, `node_modules`, `.next`, `.venv`, `data/`, `.env*`, `scripts/` dari build context. |
| `docker/entrypoint.sh` | Supervisor mini: start uvicorn + `next start`, teruskan sinyal `TERM`/`INT`, probe LLM, **gerbang persistensi** (tolak start bila `/app/data` bukan mount), backup SQLite tiap start. |

Base image `node:22-bookworm-slim` untuk **semua** stage — jadi interpreter
Python (3.11 Debian) di stage builder identik dengan runtime, dan venv hasil
`python3 -m venv` bisa di-copy apa adanya.

## 2. Arsitektur di dalam container

```
                       ┌──────────────── container (1 image) ───────────────┐
  Internet ──► Traefik │  Next.js prod server          FastAPI (uvicorn)    │
  (Coolify)   :443 ───►│  0.0.0.0:$PORT (3000)  ─────► 127.0.0.1:8000       │
                       │  UI + Mermaid    rewrite:      agent loop + tools   │
                       │                  /api/*        providers hf/openai/ │
                       │                  /slides/*     mock  ──► LLM server │
                       │                  /docs-images/*      (eksternal)    │
                       │                                    │                │
                       │  tini (PID 1) ── docker/entrypoint.sh               │
                       │                     /app/data/*  (mount disk server) │
                       └─────────────────────────────────────────────────────┘
```

- **Hanya satu port publik** (`$PORT`, default `3000`) — sesuai model Coolify
  yang me-route satu domain ke satu container port.
- Backend bind ke `127.0.0.1` sehingga **tidak** terekspos langsung ke internet;
  browser bicara same-origin ke Next, lalu Next me-rewrite `/api`, `/slides`,
  `/docs-images` ke backend (kontrak yang sama seperti `next.config.ts` dev).
- Streaming **SSE** `/api/chat` lolos lewat proxy Next production (sudah diuji:
  event `start → meta → thinking → tool_call → …` mengalir utuh).
- `PORT` & `HOST` sengaja tidak di-hardcode: Coolify meng-inject
  `PORT` = exposed port pertama dan `HOST` = `0.0.0.0`.

## 3. Langkah deploy di Coolify

1. **New Resource → New Application**, hubungkan repo Git
   (`zasyasatya/ask-anything`), branch `main`.
2. **Build Pack: `Dockerfile`** — *Dockerfile Location* `/Dockerfile`,
   *Build Context* `.` (default sudah benar).
3. **Configuration → Ports**: `3000` (container port). Kalau diganti, Coolify
   otomatis meng-inject `PORT` dengan nilai itu dan entrypoint mengikuti.
4. **Domains**: isi domain Anda atau pakai *Generate Domain* untuk uji cepat.
5. **Environment Variables**: minimal `ASK_PROVIDER` + kredensial LLM
   (lihat [§4](#4-environment-variables)). Default aplikasi adalah
   `huggingface` (mode `local`) butuh model di `models/` + torch/transformers,
   yang **tidak ada** di image — jadi di VPS set `ASK_PROVIDER=openai`.
6. **Storages → Directory Mount**: Source `/opt/ask-anything/data` (disk
   server, `chown 1000:1000`) → Destination `/app/data`
   (lihat [§5](#5-persistence--data-di-disk-server-bukan-di-container)).
   **Wajib**: tanpa mount ini container sengaja menolak start, karena semua
   data (akun, password, chat, task) akan hilang tiap redeploy.
7. **Health Checks** (opsional tapi disarankan): `GET /api/health` pada port
   `3000`, *Start Period* ≥ `40s`, *Interval* `30s`. `Dockerfile` juga sudah
   membawa `HEALTHCHECK` sendiri.
8. **Deploy**. Log build memakai BuildKit; bila log terasa terlalu ringkas,
   tambahkan env build `BUILDKIT_PROGRESS=plain`.

> Butuh resource ≥ 2 GB RAM untuk build (`next build` + `npm ci`). Setelah
> pertama kali berhasil, layer deps ter-cache sehingga redeploy jauh lebih cepat.

## 4. Environment variables

Semua variabel backend ber-prefix `ASK_` (dibaca `pydantic-settings`), sisanya
dipakai `docker/entrypoint.sh`.

### LLM provider (paling penting di VPS)

| Variabel | Default | Keterangan |
|---|---|---|
| `ASK_PROVIDER` | `huggingface` | `openai` \| `huggingface` \| `mock`. Di Coolify biasanya `openai`. |
| `ASK_OPENAI_API_KEY` | – | Wajib bila provider `openai`. Simpan sebagai *secret* (Build: off, Runtime: on). |
| `ASK_OPENAI_MODEL` | `gpt-4o-mini` | Model yang dipakai. |
| `ASK_OPENAI_BASE_URL` | `https://api.openai.com/v1` | Bisa diarahkan ke API OpenAI-compatible lain (gateway LiteLLM, OpenRouter, vLLM, dsb). Boleh ditulis lengkap `…/v1/chat/completions` — otomatis dinormalkan. |
| `ASK_HF_MODE` | `local` | `local` = inference di proses backend (butuh torch + model di `models/`) · `server` = URL OpenAI-compatible. Di Coolify umumnya tidak dipakai. |
| `ASK_HF_BASE_URL` | `http://127.0.0.1:8081/v1` | Hanya untuk `hf_mode=server`, bila ada server OpenAI-compatible yang terjangkau container (mis. `http://172.17.0.1:8081/v1` ke host, atau service lain di network Coolify). |
| `ASK_HF_MODEL`, `ASK_HF_API_KEY` | –, – | Repo id/label & key untuk mode `huggingface`. |

### Generasi, tools, storage

| Variabel | Default | Keterangan |
|---|---|---|
| `ASK_TEMPERATURE` / `ASK_MAX_TOKENS` / `ASK_MAX_STEPS` | 0.7 / 2048 / 6 | Parameter generasi & batas loop agent. |
| `ASK_LOGPROBS` / `ASK_TOP_LOGPROBS` | true / 4 | Data tab *Tokens* di Mechanistic Interpreter. |
| `ASK_SEARCH_BACKEND` | `ddg` | `ddg` \| `serper` \| `tavily`. |
| `ASK_SERPER_API_KEY` / `ASK_TAVILY_API_KEY` | – | Wajib bila memakai backend search tersebut. |
| `ASK_DATA_DIR` | `/app/data` | **Satu** direktori untuk seluruh state (SQLite, artifact, RAG, model, backup). Harus jadi titik mount disk server — kalau bukan mount, container menolak start. |
| `ASK_DB_PATH` | *(ikut `ASK_DATA_DIR`)* | Isi hanya bila SQLite harus pindah ke disk lain. |
| `ASK_ARTIFACTS_DIR` | *(ikut `ASK_DATA_DIR`)* | Idem, untuk file biner artifact. |
| `ASK_RAG_DIR` | *(ikut `ASK_DATA_DIR`)* | Idem, untuk arsip PDF mentah RAG. |
| `ASK_MODELS_DIR` | `/app/data/models` | Model offline terunduh (bisa GB-an). |
| `ASK_ALLOW_EPHEMERAL_DATA` | *(kosong)* | `1` = lewati gerbang mount (uji coba/CI). **Jangan** diisi di produksi: data akan hilang tiap redeploy. |
| `PORT` | `3000` | Di-inject Coolify; port publik Next. |
| `HOST` | `0.0.0.0` | Di-inject Coolify; bind address Next. |
| `BACKEND_HOST` / `BACKEND_PORT` | `127.0.0.1` / `8000` | Internal saja. ⚠️ `BACKEND_PORT` ikut ter-bake saat build — kalau diubah, rebuild dengan `--build-arg BACKEND_PORT=<port>` **dan** set env runtime yang sama. |

> Dari IP datacenter, DuckDuckGo (`ddg`) sering rate-limit. Untuk produksi
> sebaiknya `ASK_SEARCH_BACKEND=serper` atau `tavily` + API key; tanpa itu tool
> `web_search` tetap *graceful error* dan agent melanjutkan tanpa browsing.

Contoh set env di Coolify (Developer view):

```dotenv
ASK_PROVIDER=openai
ASK_OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
ASK_OPENAI_MODEL=gpt-4o-mini
ASK_SEARCH_BACKEND=serper
ASK_SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
ASK_DATA_DIR=/app/data
```

## 5. Persistence — data di DISK SERVER, bukan di container

Seluruh state aplikasi tinggal di **satu direktori**, `ASK_DATA_DIR`
(default `/app/data` di dalam container):

| Isi | Keterangan |
|---|---|
| `ask_anything.db` | SQLite: riwayat chat, pesan, trace interpreter, **users & password**, sesi, tasks, memori, artifact registry, feedback, index RAG. Satu file (journal `DELETE`), jadi salinannya selalu konsisten. |
| `artifacts/` | File biner artifact (gambar, PPTX, diagram). Registry-nya di SQLite, isinya di sini — keduanya harus ikut mount yang sama. |
| `rag/` | Arsip PDF mentah yang di-upload (indeks vektornya di SQLite). |
| `models/` | Model offline yang diunduh via Hub (bisa GB-an). |
| `backups/` | Salinan `ask_anything.db` otomatis tiap container start (7 terakhir, `ask_anything-YYYYMMDD-HHMMSS.db`) + hasil tombol backup manual. |

Container itu **ephemeral**: setiap redeploy membuat container baru dari image,
dan apa pun yang ditulis ke lapisan tulis container ikut dibuang. Itulah sebab
klasik "password yang sudah direset balik lagi setelah redeploy". Yang membuat
data selamat bukan image, melainkan **mount** dari direktori disk server ke
`/app/data`.

### 5.1 Coolify — Directory Mount ke disk server

1. Siapkan direktorinya di server (uid 1000 = user `node` di dalam image):

   ```bash
   sudo mkdir -p /opt/ask-anything/data
   sudo chown -R 1000:1000 /opt/ask-anything/data
   ```

2. Di resource Coolify → **Storages** → *Add* → **Directory Mount**:

   | Field | Isi |
   |---|---|
   | Source (host) | `/opt/ask-anything/data` |
   | Destination (container) | `/app/data` |

3. **Redeploy**. Log deploy harus memuat baris:

   ```
   [ask-anything] persistensi: /app/data ter-mount (sumber: /opt/ask-anything/data) - OK
   [storage] data persisten di /app/data (sumber: /opt/ask-anything/data, boot ke-3, db 148 KB)
   ```

   `boot ke-N` yang terus naik = direktori data yang sama dipakai lintas
   redeploy. Kalau angkanya selalu `1`, mount-nya belum benar.

> *Volume* (named volume Docker) juga persisten dan boleh dipakai, tapi isinya
> tersembunyi di `/var/lib/docker/volumes/…` dan ikut terhapus kalau resource
> di-delete atau `docker volume prune` dijalankan. **Directory Mount ke disk
> server** membuat data bisa dilihat, di-backup, dan di-rsync langsung.

### 5.2 Gerbang anti-kehilangan data

`docker/entrypoint.sh` memeriksa `ASK_DATA_DIR` **sebelum** aplikasi start:

* bukan mount point → container **menolak start** dengan instruksi perbaikan di
  log (dulu: start normal, data diam-diam ephemeral);
* tidak writable → berhenti dengan pesan `chown 1000:1000 …`;
* sengaja ephemeral (uji coba/CI) → set `ASK_ALLOW_EPHEMERAL_DATA=1`.

Backend melaporkan hal yang sama lewat API, jadi statusnya bisa dicek tanpa SSH:

```bash
curl -s https://<domain>/api/health | jq .storage
# {"data_dir":"/app/data","persistent":true,"writable":true,
#  "db_bytes":151552,"boots":3,"warning":""}

curl -s https://<domain>/api/admin/storage -H 'X-Admin-Token: …' | jq
# + mount_source, free_bytes, daftar backup
```

`persistent: false` = data sedang **tidak** aman. Backup manual kapan saja:
`POST /api/admin/storage/backup` (salinan konsisten via API backup SQLite).

### 5.3 Pindah dari named volume lama ke direktori disk server

Kalau deployment sebelumnya memakai named volume `ask-anything-data` dan isinya
masih dibutuhkan, salin dulu **sebelum** mengganti mount:

```bash
sudo mkdir -p /opt/ask-anything/data
docker run --rm \
  -v ask-anything-data:/from \
  -v /opt/ask-anything/data:/to \
  alpine sh -c 'cp -a /from/. /to/'
sudo chown -R 1000:1000 /opt/ask-anything/data
```

Lalu ubah mount-nya di Coolify (§5.1) dan redeploy. Volume lama boleh dihapus
setelah aplikasi terbukti jalan dengan data yang benar.

### 5.4 Backup & restore

```bash
# backup manual (host): satu file, aman disalin saat app jalan
sudo sqlite3 /opt/ask-anything/data/ask_anything.db ".backup '/root/ask-$(date +%F).db'"
# atau lewat API: POST /api/admin/storage/backup  -> /app/data/backups/…

# restore: stop app, timpa, start lagi
sudo cp /opt/ask-anything/data/backups/ask_anything-20260101-030000.db \
        /opt/ask-anything/data/ask_anything.db
sudo chown 1000:1000 /opt/ask-anything/data/ask_anything.db
```

Jadwalkan `rsync -a /opt/ask-anything/data <tujuan>` (atau snapshot VPS) untuk
backup off-site — mount hanya melindungi dari redeploy, bukan dari disk rusak.

Jaminan anti-reset yang sudah terpasang di kode:

1. **Satu variabel, satu mount** — `ASK_DATA_DIR` menentukan letak SQLite,
   artifact, RAG, model, dan backup sekaligus; tidak ada lagi path yang
   diam-diam tertinggal di lapisan container.
2. **Fail-fast** — container menolak start bila direktori itu bukan mount
   (§5.2), dan `VOLUME` di Dockerfile sengaja dihapus supaya Docker tidak
   menutupi kesalahan konfigurasi dengan *anonymous volume*.
3. **Penanda boot** — `<data>/.persistence.json` menghitung berapa kali app
   start di direktori yang sama: bukti langsung data lintas redeploy.
4. **Migrasi sekali-jalan** — data dari layout lama (`/app/backend/data/…`,
   `/app/models`) disalin ke direktori data saat start pertama.
5. **Backup tiap start** + endpoint backup manual (§5.4).
6. **Path absolut deterministik** — path relatif di-resolve terhadap root
   proyek, bukan CWD proses.

## 6. Uji image di lokal dulu

```bash
# build (dari root repo)
docker build -t ask-anything .

# jalankan: UI di http://localhost:3000, data di direktori host
mkdir -p "$PWD/data-server" && sudo chown -R 1000:1000 "$PWD/data-server"
docker run --rm -p 3000:3000 \
  -e ASK_PROVIDER=mock \
  -v "$PWD/data-server:/app/data" \
  --name ask-anything ask-anything
# tanpa -v container sengaja berhenti:
#   ERROR: /app/data bukan volume/bind mount.

# verifikasi (dari terminal lain)
curl -s localhost:3000/api/health        # {"status":"ok","provider":"mock",...}
curl -s localhost:3000/api/health | jq .storage   # persistent:true, boots naik tiap start
curl -sI localhost:3000/ | head -1       # HTTP/1.1 200 OK
curl -sI localhost:3000/docs-images/01-hero-landing.png | head -1
curl -sN -X POST localhost:3000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"halo","conversation_id":null}' | head -5   # SSE mengalir
```

Dengan `ASK_PROVIDER=openai` + `-e ASK_OPENAI_API_KEY=sk-…` Anda bisa uji
jawaban LLM sungguhan sebelum menyentuh Coolify. `docker stop ask-anything`
harus berhenti rapi (tini + trap → exit 0), bukan hang.

## 7. Troubleshooting

| Gejala | Penyebab | Fix |
|---|---|---|
| Deploy "failed" padahal image jadi | Health check Coolify < waktu start app | Naikkan *Start Period* ke 40–60 s; endpoint `/api/health`. |
| `502` dari Traefik, log container kosong | Port Coolify ≠ port listen app | Pastikan *Ports* = `3000` (atau biarkan Coolify inject `PORT`). |
| `ERROR: /app/data tidak bisa ditulis` | Direktori host milik root | `sudo chown -R 1000:1000 <direktori host>` (§5.1). |
| `ERROR: /app/data bukan volume/bind mount` | Storage belum di-mount di Coolify | Tambah *Directory Mount* `/opt/ask-anything/data` -> `/app/data` (§5.1). Container sengaja menolak start agar data tidak hilang diam-diam. |
| Akun/password hasil reset & chat balik ke kondisi awal tiap redeploy | Direktori data bukan mount, isinya cuma di lapisan container | §5.1; verifikasi `/api/health` -> `storage.persistent: true` dan `storage.boots` naik tiap redeploy. |
| Log `[storage] EPHEMERAL disengaja` | `ASK_ALLOW_EPHEMERAL_DATA=1` masih terpasang | Hapus env itu di produksi. |
| UI jalan, tapi `llm_reachable: false` | Provider default `huggingface` menunjuk `127.0.0.1:8081` yang tidak ada di VPS | Set `ASK_PROVIDER=openai` + key, atau `mock`, atau arahkan `ASK_HF_BASE_URL` ke LLM server yang hidup. |
| Build OOM / sangat lambat | `next build` butuh RAM & CPU | Server ≥ 2 GB RAM; tambahkan swap; build pertama memang paling lama. |
| `/api`, `/slides`, `/docs-images` 404 | `BACKEND_URL` saat build ≠ runtime | Jangan ubah `BACKEND_PORT` tanpa rebuild `--build-arg BACKEND_PORT=…`. |
| Chat terasa macet di tengah stream | Proxy di depan melakukan buffering | Pastikan tidak ada reverse proxy tambahan dengan `proxy_buffering on`; Traefik bawaan Coolify sudah streaming. |
| Container restart terus | Salah satu proses mati → entrypoint mematikan container (by design) | Baca log: baris `[ask-anything] proses anak berhenti (exit N)` menunjuk proses yang gagal. |

## 8. Catatan desain Dockerfile

- **Kenapa satu container, bukan dua?** Coolify paling mulus dengan satu app =
  satu port. Menyatukan backend+frontend menjaga kontrak *same-origin* yang
  sudah dipakai UI (tanpa perlu CORS/domain API terpisah) dan membuat deploy
  cukup satu resource. Bila kelak ingin dipisah, jalankan stage `runtime`
  dengan `BACKEND_HOST=0.0.0.0` + `EXPOSE 8000` untuk service API, dan build
  frontend dengan `--build-arg BACKEND_PORT`/`BACKEND_URL` menunjuk service API.
- **`npm prune --omit=dev`** setelah `next build` membuang tailwind/typescript/
  postcss dari image runtime; `.next/cache` juga dihapus karena tidak dipakai
  `next start`.
- **`--chown=node:node` per-COPY** (bukan `RUN chown -R`) supaya metadata
  `node_modules` tidak diduplikasi menjadi layer ekstra ratusan MB.
- **`tini` sebagai PID 1** + `trap TERM/INT` di entrypoint: `docker stop`
  (Coolify *Stop/Redeploy*) mematikan uvicorn & next secara graceful.
- **Non-root** (`USER node`, uid 1000): praktik aman untuk app yang
  terekspos publik; konsekuensinya direktori data di host harus dimiliki
  uid 1000 (§5.1).
- **Tanpa `VOLUME /app/data`**: instruksi itu membuat Docker diam-diam
  membuatkan *anonymous volume* saat mount lupa dipasang — app tetap jalan,
  data terlihat tersimpan, lalu hilang saat redeploy. Sekarang salah
  konfigurasi langsung gagal di entrypoint (§5.2).
- **Build cache ramah**: layer `npm ci` dan `pip install` hanya invalid bila
  `package-lock.json` / `requirements.txt` berubah.
