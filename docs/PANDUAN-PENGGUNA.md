# Panduan Pengguna — Ask Anything

> **Titik masuk dokumentasi pengguna.** Ask Anything dipakai oleh dua peran dengan
> kebutuhan yang sangat berbeda, jadi panduannya dipecah: mulailah dari panduan
> peran Anda. Keduanya **berdiri sendiri** — tidak perlu membaca yang lain.
>
> | Peran | Panduan | Versi in-app |
> | --- | --- | --- |
> | Peserta internship | [**PANDUAN-MEMBER.md**](PANDUAN-MEMBER.md) | `/panduan/member` |
> | Pengelola platform | [**PANDUAN-ADMIN.md**](PANDUAN-ADMIN.md) | `/panduan/admin` |
>
> Semua gambar di dokumen-dokumen ini adalah **screenshot aplikasi sungguhan**
> yang diambil otomatis oleh [`scripts/capture_screenshots.py`](../scripts/capture_screenshots.py)
> (Playwright/Chromium) dari stack yang berjalan — bukan mockup.
>
> Versi interaktif halaman ini tersedia di dalam aplikasi: **`/panduan`**.

---

## Daftar isi

1. [Mulai dalam 1 menit](#1-mulai-dalam-1-menit)
2. [Dua peran: member & admin](#2-dua-peran-member--admin)
3. [Pilih panduan Anda](#3-pilih-panduan-anda)
4. [Yang sama untuk semua peran](#4-yang-sama-untuk-semua-peran)
5. [Troubleshooting umum](#5-troubleshooting-umum)
6. [Data & privasi](#6-data--privasi)

---

## 1. Mulai dalam 1 menit

Ask Anything adalah chatbot AI **agentic**: ia bisa mencari di web, membaca isi
halaman, menghitung, dan menggambar diagram — sambil memperlihatkan seluruh
proses berpikirnya di panel **Mechanistic Interpreter**. Di atas itu ada **papan
task** untuk mengelola pekerjaan platform (`ASK-NNN`) dan proyek internship
(`INT-NNN`).

![Halaman login](images/30-login.png)

*Halaman `/login`. Semua orang masuk lewat pintu yang sama; peran akun Anda yang
menentukan apa yang terlihat setelahnya.*

---

## 2. Dua peran: member & admin

Pembatasan peran ditegakkan **di server**, bukan sekadar disembunyikan di UI.
Menebak URL halaman admin tidak akan berhasil — backend membalas `403`.

| | **Member** (peserta internship) | **Admin** (pengelola) |
| --- | --- | --- |
| Chat | Mode teks, diagram, RAG — provider OpenAI | Semua mode: teks, gambar, diagram, PPT, RAG, deep research |
| Papan task | Hanya task yang ditugaskan kepadanya; boleh ubah status, checklist, komentar | Semua task di kedua papan; buat, hapus, tugaskan, seed, sync git |
| Pengaturan provider | Tidak (`403`) | Ya, termasuk model offline |
| Konsol `/admin` | Tidak (`403`) | Ya: akun, peran, pipeline, analitik |
| Akun | Ganti nama & password sendiri | Buat akun, atur peran, reset password |

---

## 3. Pilih panduan Anda

### → [Panduan Member](PANDUAN-MEMBER.md) · in-app `/panduan/member`

Untuk peserta internship yang mengerjakan task dan memakai playground.

- Masuk & mengenal playground
- Chat: mode teks, diagram, dan RAG
- Membaca task: deskripsi, **workflow**, dan **wireframe**
- Memindahkan status & melapor lewat komentar
- Alur kerja harian dengan branch git

### → [Panduan Admin](PANDUAN-ADMIN.md) · in-app `/panduan/admin`

Untuk pengelola platform: akun, peran, pipeline, dan kedua papan task.

- Mengelola akun & peran (konsol `/admin`)
- Pipeline: mode, tool, dan akses per peran
- Settings provider & model offline
- Papan platform + internship, seed & sync git
- Mechanistic Interpreter untuk menelusuri jawaban

> **Belum tahu peran Anda?** Lihat pojok kiri bawah sidebar setelah login — nama
> akun beserta labelnya (**Admin** atau **Member**) tertulis di sana.

---

## 4. Yang sama untuk semua peran

- **Login & sesi** — cookie `HttpOnly` (`ask_session`), bukan localStorage.
  Tombol **Keluar** di sidebar benar-benar mencabut sesi.
- **Ganti password sendiri** — ikon ⚙ di sidebar → Profil. Admin tidak bisa
  melihat password Anda; ia hanya bisa me-reset-nya.
- **Papan task** — kartu, kolom, dan panel detail bertab (Ringkasan, Workflow,
  Wireframe, Aktivitas) sama untuk kedua peran; yang berbeda adalah cakupan task
  dan field mana yang boleh diubah.
- **Aksen warna & mobile** — pemilih warna ada di composer, dan seluruh layar
  tetap bisa dipakai pada lebar 390 px.

---

## 5. Troubleshooting umum

| Gejala | Penyebab biasanya | Tindakan |
| --- | --- | --- |
| Diarahkan kembali ke `/login` terus | Sesi kedaluwarsa atau cookie diblokir | Masuk ulang; pastikan cookie pihak pertama tidak diblokir browser |
| Tombol/halaman membalas `403` | Fitur itu memang khusus admin | Minta admin mengubah izin di Admin → Pipeline → Akses per peran |
| Banner "Belum ada model offline yang dimuat" | Provider huggingface aktif tetapi model belum diunduh | Klik **Pakai mode mock**, atau minta admin memuat model |
| Papan task kosong | Belum ada task yang ditugaskan kepada Anda | Minta admin menugaskan task di papan yang sesuai |
| Jawaban menyebut browsing tidak menghasilkan apa pun | Tidak ada akses internet dari server | Itu perilaku jujur — agent menolak mengarang sitasi |

Troubleshooting yang lebih spesifik ada di masing-masing panduan peran.

---

## 6. Data & privasi

- Percakapan, task, dan komentar disimpan di database lokal aplikasi (SQLite) —
  tidak dikirim ke pihak ketiga selain provider LLM yang dikonfigurasi admin.
- Password disimpan sebagai **hash**, tidak pernah dalam bentuk asli.
- Sesi memakai cookie `HttpOnly` sehingga tidak bisa dibaca JavaScript halaman.
- Bila provider yang aktif adalah layanan cloud (mis. OpenAI), isi percakapan
  dikirim ke sana — tanyakan ke admin provider mana yang sedang dipakai;
  indikatornya terlihat di header chat.

---

## Dokumen terkait

| Dokumen | Isi |
| --- | --- |
| [PANDUAN-MEMBER.md](PANDUAN-MEMBER.md) | Panduan lengkap peserta internship |
| [PANDUAN-ADMIN.md](PANDUAN-ADMIN.md) | Panduan lengkap pengelola platform |
| [PANDUAN-DEVELOPER.md](PANDUAN-DEVELOPER.md) | Menjalankan & mengembangkan kode |
| [TASK-MANAGEMENT.md](TASK-MANAGEMENT.md) | Model data task, workflow & wireframe |
| [TEKNIS.md](TEKNIS.md) | Arsitektur teknis mendalam |
