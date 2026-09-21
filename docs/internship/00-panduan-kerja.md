# Panduan kerja internship — chatbot LLM

Dokumen ini menjawab "bagaimana cara bekerja di sini". Rincian *apa* yang
dikerjakan ada di papan `/internship` (task `INT-NNN`) dan di
[03-rencana-sprint.md](03-rencana-sprint.md).

## 1. Ritme harian & mingguan

| Kapan | Apa | Berapa lama |
|---|---|---|
| Setiap hari, pagi | Tulis 3 baris di komentar task: kemarin, hari ini, hambatan | 5 menit |
| Setiap hari, sore | Push branch (walau belum selesai) | 5 menit |
| Akhir sprint | Demo hasil sprint ke pembimbing + tarik task sprint berikutnya | 30 menit |

Satu sprint = 1 minggu kerja. Task sprint berikutnya **tetap di kolom Backlog**
sampai sprint sebelumnya ditutup — kolom *To do* sengaja dijaga pendek supaya
fokus tidak pecah.

## 2. Alur satu task

1. Buka task di papan `/internship`, baca tab **Deskripsi**, **Workflow**,
   **Wireframe**, dan **Kriteria selesai**.
2. Pindahkan ke **In progress**, lalu buat branch persis seperti yang tertera di
   detail task:

   ```bash
   git checkout -b feat/INT-007-sesi-percakapan
   ```

3. Kerjakan sampai **semua** kriteria selesai bisa dicentang — bukan sampai
   "kira-kira jalan". Kriteria yang berangka wajib diukur, bukan ditaksir.
4. Tulis test-nya di task yang sama, bukan "nanti di akhir".
5. Push, buka merge request, pindahkan task ke **Review**, tag pembimbing.
6. Task pindah ke **Done** hanya setelah MR di-merge.

Commit memakai format `feat(INT-007): ringkasan singkat` supaya papan bisa
mencocokkan commit ke task secara otomatis.

## 3. Kalau tersangkut

Aturan **30 menit**: sudah 30 menit tidak maju? Tulis di komentar task apa yang
sudah dicoba dan apa pesan errornya, lalu tanya pembimbing. Tersangkut bukan
masalah; tersangkut diam-diam selama dua hari adalah masalah.

Yang harus ditulis saat bertanya:

* apa yang ingin dicapai (1 kalimat),
* perintah/kode yang dijalankan,
* pesan error **lengkap** (bukan "errornya banyak"),
* dua hal yang sudah dicoba.

## 4. Yang dinilai

Penilaian magang bertumpu pada empat hal, berurut kepentingannya:

1. **Kriteria selesai terpenuhi dan terukur** — angka, bukan perasaan.
2. **Kode bisa dijalankan orang lain** dari README tanpa bertanya.
3. **Ada test** untuk jalur yang penting.
4. **Dokumentasi & demo** yang bisa dipakai orang berikutnya.

Kecepatan menulis kode ada di urutan kelima. Pekerjaan yang selesai separuh
tetapi jujur tercatat lebih berharga daripada klaim selesai yang tidak bisa
diperagakan.

## 5. Batasan penting

* Jangan menyalin kode `ask-anything` mentah-mentah. Boleh dibaca sebagai
  contoh pola, lalu ditulis ulang dengan versi yang jauh lebih sederhana.
* Jangan menambah teknologi di luar daftar yang sudah dikunci di
  [02-arsitektur-prototipe.md](02-arsitektur-prototipe.md). Ingin menambah?
  Ajukan lewat ADR dan tunggu persetujuan.
* Jangan pernah meng-commit API key, `.env`, atau berkas database.
* Semua data pengguna dan dokumen uji berada di folder `data/` yang diabaikan
  git dan di-mount sebagai volume saat dijalankan lewat Docker.
