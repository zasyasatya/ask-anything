# Panduan Pengguna — Ask Anything

> Tata cara lengkap memakai **Ask Anything**: chat AI agentic dengan browsing,
> diagram, kalkulasi, dan panel **Mechanistic Interpreter** yang memperlihatkan
> seluruh proses LLM. Semua gambar di dokumen ini adalah **screenshot aplikasi
> sungguhan** yang diambil otomatis oleh [`scripts/capture_screenshots.py`](../scripts/capture_screenshots.py)
> (Playwright/Chromium) dari stack yang berjalan — bukan mockup.
>
> Versi interaktif halaman ini tersedia di dalam aplikasi: **`/panduan`**.

---

## Daftar isi

1. [Mulai dalam 1 menit](#1-mulai-dalam-1-menit)
2. [Mengenal layar utama](#2-mengenal-layar-utama)
3. [Chat pertama Anda](#3-chat-pertama-anda)
4. [Membaca jawaban agent](#4-membaca-jawaban-agent)
5. [Browsing & penanganan error](#5-browsing--penanganan-error)
6. [Mechanistic Interpreter](#6-mechanistic-interpreter)
7. [Riwayat percakapan](#7-riwayat-percakapan)
8. [Settings provider](#8-settings-provider)
9. [Tampilan, aksen & mobile](#9-tampilan-aksen--mobile)
10. [Materi belajar lanjutan](#10-materi-belajar-lanjutan)
11. [Tips prompt yang efektif](#11-tips-prompt-yang-efektif)
12. [Troubleshooting](#12-troubleshooting)
13. [Data & privasi](#13-data--privasi)

---

## 1. Mulai dalam 1 menit

Ask Anything bukan chatbot biasa: ia **agent** yang bisa mencari di web,
membaca isi halaman, menghitung dengan aman, dan menggambar diagram
(flowchart / graph / mindmap) — sambil menyiarkan seluruh proses berpikirnya
ke panel Interpreter.

Prasyarat: **Python ≥ 3.10** dan **Node ≥ 18**. Sisanya diurus launcher.

```bash
# Linux / macOS
python3 run.py            # atau: ./run.sh

# Windows
run.bat

# Mode demo tanpa GPU / tanpa download model (LLM di-emulasi)
python3 run.py --demo

# Cari model di HuggingFace, lalu unduh + jadikan model aktif
python3 run.py --search qwen3
python3 run.py --model Qwen/Qwen3-1.7B
```

- UI: <http://localhost:3000> · Swagger API: <http://localhost:8000/docs>
- Launcher mencetak checklist dependensi (`python`, `node`, `npm`, backend,
  frontend) plus status keterjangkauan server LLM.
- Halaman dokumentasi in-app: `/panduan` (halaman ini) dan `/developer`
  (arsitektur & kontribusi).

> **Tidak punya server LLM lokal?** Klik tombol **“Pakai mode mock”** pada
> banner peringatan — seluruh fitur UI (termasuk Interpreter & diagram) tetap
> bisa dicoba secara offline dan deterministik.

## 2. Mengenal layar utama

![Layar awal](images/01-hero-landing.png)
*Layar awal: sidebar riwayat (kiri), header status (atas), composer pertanyaan
(tengah), chip contoh prompt, dan galeri Explore.*

| Bagian | Fungsi |
|---|---|
| **Sidebar kiri** | Tombol `New chat`, riwayat percakapan berkelompok tanggal (`Today`, `Yesterday`, …), indikator status LLM (hijau/merah), tombol `Settings provider`. |
| **Header** | Judul percakapan aktif, chip provider+model (mis. `huggingface · Qwen/Qwen3-1.7B`), tautan `Panduan`, `Developer`, `Docs & Slides`, dan tombol `Mechanistic Interpreter →`. |
| **Composer** | Kotak pertanyaan. Kirim dengan `Enter` atau tombol `Ask`; `Shift+Enter` untuk baris baru. Saat agent bekerja tombol menjadi `Thinking…`. |
| **Badge `4 tools`** | Daftar tool aktif: `web_search`, `fetch_url`, `create_diagram`, `calculator` (hover untuk tooltip). |
| **Chip contoh & Explore** | Prompt siap pakai per kategori (Browsing / Diagram / Tools); klik untuk mengisi composer. |

![Galeri Explore](images/02-hero-explore.png)
*Galeri Explore dengan tab kategori. Klik kartu untuk memakai promptnya.*

## 3. Chat pertama Anda

1. Klik chip contoh (mis. `Diagram alir →`) atau ketik pertanyaan sendiri.
2. Periksa badge `4 tools` dan pilihan aksen warna di baris bawah composer.
3. Tekan `Enter` / `Ask`. Tombol berubah menjadi `Thinking…`.
4. Jawaban mengalir bertahap (streaming); panel **Mechanistic Interpreter**
   otomatis terbuka di kanan memperlihatkan prosesnya.

![Composer terisi](images/03-composer-filled.png)
*Composer terisi prompt contoh setelah klik chip.*

![Chat diagram + interpreter](images/04-chat-diagram-interpreter.png)
*Satu run lengkap: chip tool `create_diagram ✓`, jawaban teks, diagram yang
dirender live, dan Interpreter (kanan) yang merekam semua event.*

## 4. Membaca jawaban agent

| Elemen UI | Artinya |
|---|---|
| Kotak `💭 thinking` | Reasoning mentah model sebelum memutuskan langkah (saat streaming). |
| Chip tool (`web_search ✓`, `create_diagram ✓`, …) | Agent memanggil tool tersebut; ✓ = selesai. Hover untuk ringkasan hasil. |
| Kartu `graph interaktif` | Diagram alir / graph / mindmap hasil tool, dirender sebagai graph HTML yang bisa di-zoom, digeser, dan diklik (default). Toggle ke mode `mermaid diagram` tersedia di kartu yang sama. |
| Teks markdown | Jawaban final: list, tabel, tautan sumber, dan blok kode dirender otomatis. |

### 4.1 Mode diagram: Graph interaktif vs Mermaid

Setiap kartu diagram punya dua mode render (preferensi tersimpan otomatis di
browser):

| Mode | Perilaku |
|---|---|
| **Graph** (default) | Sumber Mermaid diterjemahkan menjadi komponen HTML: node adalah elemen asli yang bisa **diklik** (menyorot relasi + panel detail), **di-drag** untuk menata ulang, latar bisa di-**drag** (pan) dan di-**scroll** (zoom), tombol `− / + / fit`, serta toggle arah layout `↓ TD` / `→ LR`. Parser bersifat toleran: baris Mermaid yang rusak dilewati dan dicatat sebagai badge “N baris dilewati”, bukan error seluruh diagram. |
| **Mermaid** | Renderer Mermaid asli (SVG statis). Bila sumber rusak dan Mermaid gagal, muncul banner kuning dengan tombol **“Pakai mode Graph”** sebagai fallback satu klik. |

Interaksi cepat mode Graph: klik node = lihat relasi masuk/keluar (klik chip
relasi untuk lompat ke node tersebut); klik latar / `Esc` = tutup panel;
dobel-klik latar = pas-ke-layar; keyboard: `Tab` berpindah node, `Enter`
memilih.

![Percakapan kalkulator](images/10-chat-calculator.png)
*Tool `calculator`: ekspresi dikirim sebagai argumen tool, hasilnya dikutip
agent pada jawaban final.*

## 5. Browsing & penanganan error

Untuk informasi terkini agent memanggil `web_search` (DuckDuckGo lite tanpa
API key; Serper/Tavily opsional via env), dan dapat melanjutkan dengan
`fetch_url` untuk membaca satu halaman penuh (teks diekstrak, ≤ 12k karakter).

Bila jaringan gagal, error **tidak** mematikan percakapan: status error
dikembalikan ke model sebagai data (`tool_result` berstatus error), dan model
menjawab dengan jujur menyebutkan keterbatasannya — pola *graceful
degradation* yang sengaja dirancang.

![Browsing error graceful](images/09-chat-browsing-error.png)
*Contoh: `web_search` gagal di lingkungan offline; error tampil sebagai
tool_result dan agent tetap merangkum dengan menyebut kegagalannya.*

## 6. Mechanistic Interpreter

Panel kanan (tombol `Mechanistic Interpreter →`) merekam **semua** event satu
run, dan tersimpan di SQLite sehingga riwayat bisa di-**replay** penuh.

| Tab | Isi | Kapan dipakai |
|---|---|---|
| **Timeline** | Urutan event `meta → thinking → tool_call → tool_result → … → done`; tiap baris bisa dibentangkan menjadi JSON mentah. | Memeriksa langkah agent & argumen tool. |
| **Prompt** | Prompt assembly persis seperti dikirim ke LLM: system prompt, messages, schema tools. | Debug perilaku model. |
| **Tokens** | Logprobs streaming per token: token terpilih, bar probabilitas, alternatif teratas. | Melihat keyakinan model per token. |
| **Metrics** | Provider/model, temperature, steps, latensi, token usage, jumlah event/error. | Mengukur performa run. |

![Timeline expanded](images/05-interpreter-timeline-expanded.png)
*Tab Timeline dengan baris event dibentangkan (JSON mentah per event).*

![Tab Prompt](images/06-interpreter-prompt.png)
*Tab Prompt: system prompt + messages + tools persis seperti diterima LLM.*

![Tab Tokens](images/07-interpreter-tokens.png)
*Tab Tokens: logprobs per token dengan bar probabilitas & alternatif
(tersedia pada mode openai/server yang mendukung dan mode mock; inference lokal tidak mengirim logprobs).*

![Tab Metrics](images/08-interpreter-metrics.png)
*Tab Metrics: ringkasan run — provider, model, temperature, steps, latensi, usage.*

## 7. Riwayat percakapan

Setiap percakapan tersimpan otomatis di SQLite lokal **beserta trace
event-nya**. Klik judul di sidebar untuk membuka kembali pesan *dan* replay
Interpreter-nya (Timeline/Prompt/Tokens/Metrics tetap lengkap).

![Sidebar riwayat](images/13-sidebar-history.png)
*Riwayat dikelompokkan per tanggal; indikator “LLM server terhubung”; tombol
Settings provider di bawah.*

## 8. Settings provider

Tombol `Settings provider` membuka dialog pemilihan LLM — berlaku runtime
tanpa restart:

| Provider | Kapan dipakai |
|---|---|
| `huggingface` | Model offline dari folder `models/` yang dijalankan **langsung di backend** (transformers, tanpa llama.cpp). Bila `hf_mode=server`, memakai server OpenAI-compatible yang Anda jalankan sendiri. |
| `openai` | API OpenAI / Azure / proxy kompatibel (isi API key & base URL). |
| `mock` | Demo offline deterministik untuk uji UI & dokumen ini. |

![Settings provider](images/11-settings-provider.png)
*Dialog settings: tab **Provider & endpoint**, tab **Model offline
(HuggingFace)**, dan slider temperature.*

Base URL boleh ditulis dalam bentuk apa pun yang Anda temukan di dokumentasi
API — termasuk URL endpoint lengkap dari contoh curl:

```
https://ai.sumopod.com/v1/chat/completions   →   https://ai.sumopod.com/v1
```

Aplikasi menormalkannya sendiri lalu menambahkan `/chat/completions`, jadi tidak
pernah terjadi 404 karena path ganda. Isikan **API key** (Bearer token) bila
gateway Anda memerlukannya; key yang sudah tersimpan hanya ditampilkan sebagai
`ran…oken`. Tombol **Hapus** di samping kolom key menghapus key yang tersimpan.

### 8.0 Memilih model dari daftar endpoint

Tombol **Muat model** di samping kolom Base URL memanggil
`GET <base>/models` dan mengisi **dropdown Model** — jadi Anda tidak perlu
mengingat/mengetik nama model:

- Sebagian server melaporkan model sebagai path file (`/models/x.gguf`);
  dropdown menampilkan nama pendeknya tetapi tetap mengirim id asli ke API.
- Bila endpoint tidak terjangkau atau menolak key, pesannya muncul di bawah
  kolom (mis. `API key ditolak (401)`) — bukan dropdown kosong tanpa sebab.
- Model yang sedang aktif tetapi tidak ada di daftar tetap dipertahankan, dan
  opsi **✎ Ketik nama model lain…** selalu tersedia untuk gateway yang tidak
  menyediakan `/models`.

### 8.0.1 Test koneksi — mengetahui penyebab error API

Tombol **Test koneksi** menjalankan tiga request sungguhan ke endpoint yang
sedang diisi: `GET /models`, chat **non-streaming** (bentuk persis contoh
`curl`), dan chat **streaming** (yang dipakai aplikasi). Hasilnya ditampilkan
per-request: status HTTP, latensi, cuplikan jawaban atau pesan server apa
adanya, plus petunjuk. Dengan itu “API error” tidak lagi misterius — key
ditolak (401), nama model tidak terdaftar, dan payload yang ditolak gateway
terlihat berbeda.

Langkah penyetelan lengkap tiap mode (lokal / OpenAI+gateway / mock) ada di
[`PENYESUAIAN-PROVIDER.md`](PENYESUAIAN-PROVIDER.md).

### 8.1 Model offline langsung dari HuggingFace

Tab **Model offline (HuggingFace)** mencari model **berdasarkan namanya** di
HuggingFace Hub — tidak ada katalog tetap, jadi model baru apa pun bisa dipakai:

1. **Cari** — ketik repo id lengkap (`deepseek-ai/DeepSeek-V4.1-Flash`) atau
   kata kunci (`qwen3`, `gemma`). Hasilnya menampilkan jumlah parameter,
   perkiraan ukuran, dan popularitas.
2. **Download** — file diunduh ke folder project `models/<organisasi>/<nama>/`
   dengan progress bar (persen, MiB, kecepatan, file ke-berapa). Boleh
   mengunduh **beberapa model sekaligus**; bila koneksi putus, klik **Download**
   lagi untuk melanjutkan (resume per file).
3. **Pakai & muat** — model menjadi model aktif **dan** dimuat ke memori proses
   backend. Tidak ada server tambahan yang perlu dijalankan.

Kartu **Inference lokal (transformers)** di bagian bawah menampilkan status
engine: model yang termuat, device (cpu/cuda/mps), dtype, dan jumlah parameter,
plus tombol **Lepas dari memori**. Toggle **Thinking (reasoning)** meneruskan
`enable_thinking` ke chat template model.

Repo **gated/privat** (mis. DeepSeek) membutuhkan token: buka *Token
HuggingFace* di tab yang sama dan tempel token dari
`huggingface.co/settings/tokens`.

Butuh PyTorch + transformers sekali di awal:

```bash
python3 run.py --install-local          # pasang torch + transformers
python3 run.py --search qwen3           # cari model
python3 run.py --list-models            # yang sudah terunduh
python3 run.py --model Qwen/Qwen3-1.7B  # unduh + jadikan aktif + jalankan
```

Folder `models/` masuk `.gitignore` — bobot model tidak pernah ikut ter-commit.

![Banner LLM offline](images/12-banner-llm-offline.png)
*Bila model lokal belum dimuat (atau endpoint tidak terjangkau), banner kuning
muncul dengan tombol “Buka Settings” dan sekali-klik “Pakai mode mock”.*

## 9. Tampilan, aksen & mobile

Empat aksen warna (indigo, violet, orange, zinc) tersedia di composer — klik
titik warna untuk mengganti aksen seluruh UI seketika. Layout responsif sampai
layar ponsel (sidebar disembunyikan, composer tetap penuh).

![Aksen orange](images/16-accent-orange.png)
*Aksen orange diterapkan ke tombol, chip, dan ring.*

![Mobile](images/15-mobile-hero.png)
*Tampilan mobile 390×844.*

## 10. Materi belajar lanjutan

- **Slide interaktif** “cara kerja agent”: tombol `Docs & Slides →` di header
  atau `/slides/slides-cara-kerja.html` (navigasi `←`/`→`).
- **Metodologi** lengkap: [`docs/METODOLOGI.md`](METODOLOGI.md).
- **Developer**: [`docs/PANDUAN-DEVELOPER.md`](PANDUAN-DEVELOPER.md) atau
  halaman in-app `/developer`.

![Slides](images/14-slides-cara-kerja.png)
*Slide interaktif disajikan backend di `/slides` dan diproxy frontend.*

## 11. Tips prompt yang efektif

- Sebutkan kata kunci kemampuan: `cari/berita` → browsing,
  `diagram/alur/graph/mindmap` → diagram, `hitung` → calculator.
- Minta sumber eksplisit: *“…lengkap dengan link sumber”*.
- Untuk graph relasi, sebutkan node: *“graph relasi antar microservice:
  gateway, auth, billing, catalog, notification”*.
- Gabungkan tugas: *“Jelaskan cara kerja DNS lalu buat diagram alurnya”*.
- Lanjutkan percakapan untuk merevisi diagram — riwayat dikirim sebagai
  konteks langkah berikutnya.

## 12. Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| Banner kuning “Belum ada model offline yang dimuat” | Provider `huggingface` mode lokal belum punya model. | Settings → Model offline → cari → **Download** → **Pakai & muat**. |
| Indikator sidebar merah “LLM server offline” | Base URL provider tidak reachable. | Periksa Settings provider → base URL, atau ganti provider. |
| Tool `web_search` berstatus error | Tidak ada akses internet dari backend. | Normal di lingkungan offline (graceful). Konfigurasi Serper/Tavily bila punya key. |
| Tab Tokens kosong | Provider tidak mengirim logprobs. | Pakai mode `openai`/server yang mendukung, atau mode mock. |
| “API error” tanpa penjelasan | Key salah, nama model tidak ada, atau payload ditolak gateway. | Settings → **Test koneksi**; status + pesan server ditampilkan per-request. |
| Diagram tidak muncul | Model tidak menghasilkan Mermaid valid. | Ulangi dengan prompt eksplisit “diagram alir”; validasi server-side akan menolak Mermaid rusak dan memberikannya kembali ke model. Mode **Graph** tetap merender bagian sumber yang terbaca; tombol “salin” di kartu memudahkan menempelkan sumber ke editor Mermaid eksternal. |
| UI tampil tapi tidak interaktif | Dev-server Next 16 memblokir resource cross-origin. | Tambahkan host ke `allowedDevOrigins` di `next.config.ts` (sudah disetel untuk 127.0.0.1 & *.e2b.app), lalu restart. |

## 13. Data & privasi

- Semua percakapan + trace tersimpan **lokal** di SQLite
  (`data/ask_anything.db`, lokasi bisa diubah via `ASK_DB_PATH`).
- Tidak ada telemetri dari aplikasi; permintaan LLM hanya menuju provider yang
  Anda pilih.
- Hapus riwayat: `DELETE /api/conversations/{id}` atau hapus file DB saat
  aplikasi mati.

---

*Screenshot di dokumen ini dapat di-generate ulang kapan pun:*

```bash
python3 run.py --demo                     # stack + emulator LLM
pip install playwright brotli             # sekali
BASE_URL=http://127.0.0.1:3000 python3 scripts/capture_screenshots.py main
python3 scripts/capture_screenshots.py pages
```
