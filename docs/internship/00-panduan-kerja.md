# Panduan kerja internship — Internal AI Assistant & RAG Agent

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
   git checkout -b feat/INT-008-sesi-percakapan-persisten
   ```

3. Kerjakan sampai **semua** kriteria selesai bisa dicentang — bukan sampai
   "kira-kira jalan". Kriteria yang berangka wajib diukur, bukan ditaksir.
4. Tulis test-nya di task yang sama, bukan "nanti di akhir".
5. Push, buka merge request, pindahkan task ke **Review**, tag pembimbing.
6. Task pindah ke **Done** hanya setelah MR di-merge.

Commit memakai format `feat(INT-008): ringkasan singkat` supaya papan bisa
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
* Jangan pernah meng-commit API key, `.env`, atau dump database.
* Semua data pengguna, dokumen, dan vektor berada di PostgreSQL + volume Docker
  (`pgdata`, `uploads`, `hf_cache`), bukan di dalam image dan bukan di git.
* Ikuti [design system beUI](05-design-system.md): komponen lewat
  `npx shadcn add @beui/<slug>`, ikon hanya `lucide-react`, **tanpa emoji**,
  tema terang sebagai default, dan komponen UI hanya presentasi (logika stream
  dan pemanggilan API ada di `infrastructure/` + `interface-adapters/`).
* Sumber kebenaran produk adalah [PRD](01-template-prd.md) (bagian A user story,
  B metrik & anggaran, C arsitektur + ADR). Ingin mengubah angka atau stack?
  Ubah PRD lewat merge request, bukan diam-diam di kode.

## 6. Mengubah papan task

Papan `/internship` bukan rencana beku — tim boleh menyesuaikannya:

| Aksi | Siapa | Cara |
|---|---|---|
| Tambah task | admin | tombol **+ Task** (nomor `INT-NNN` terisi otomatis) |
| Ubah judul, deskripsi, prioritas, fase, estimasi, assignee | admin | panel detail task |
| Ubah kriteria selesai, prasyarat, label | admin | tab *Ringkasan* |
| Ubah alur kerja | admin | tab *Workflow* -> **Ubah alur kerja** |
| Ubah wireframe & berkas bukti | admin | tab *Wireframe* -> **Ubah wireframe** |
| Pindah kolom, centang kriteria, komentar | admin & member (task sendiri) | drag kartu / panel detail |
| Hapus task | admin | tombol **Hapus task** di panel detail |

Semua perubahan **tersimpan permanen** di database (volume data), dan pembaruan
rencana tidak menimpanya:

* task yang isinya sudah Anda ubah ditandai **disunting** dan tidak ditulis ulang;
* task rencana yang Anda hapus **tidak muncul lagi** (dan nomornya tidak dipakai
  ulang) — menu **Pulihkan yang dihapus** mengembalikannya bila perlu;
* task yang sudah **Done** dibekukan;
* task buatan sendiri tidak pernah disentuh;
* **Reset rencana** (menu `...`) adalah satu-satunya aksi yang membuang
  suntingan dan memulihkan seluruh task rencana ke kondisi awal.
