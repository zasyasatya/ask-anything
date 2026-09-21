# Definition of Done & checklist review

Satu task dianggap **Done** hanya bila seluruh baris di bawah terpenuhi.
Tidak ada "done sebagian": kalau ada yang belum, task tetap di *In progress*
atau *Review* dengan catatan jelas di komentar.

## 1. Checklist per task

- [ ] Semua **kriteria selesai** di papan tercentang, dan yang berangka
      benar-benar **diukur** (angkanya ditulis di komentar task, bukan ditaksir).
- [ ] Berkas **evidence** yang tercantum di task benar-benar ada di repo.
- [ ] Ada **test** untuk jalur utama task ini, dan `pytest` hijau seluruhnya.
- [ ] Jalan di mesin bersih **tanpa API key** (memakai mock provider).
- [ ] Tidak ada rahasia (API key, token, `.env`, berkas database) ikut commit.
- [ ] README/runbook diperbarui bila cara menjalankan berubah.
- [ ] Merge request dibuka, di-review, dan di-merge.

## 2. Checklist khusus task LLM

- [ ] **Prompt** disimpan di modul prompt, bukan ditempel di tengah logika.
- [ ] Batas **token** dihormati: prompt akhir tidak pernah melewati anggaran.
- [ ] Kegagalan model (timeout, 5xx, JSON rusak) **tidak** membuat aplikasi mati
      — ada retry atau nilai default yang aman.
- [ ] Jalur ini menulis **span trace** sehingga durasinya terlihat.
- [ ] Token & biaya yang dipakai tercatat.
- [ ] Data pribadi tidak pernah dikirim mentah ke provider pihak ketiga.

## 3. Yang membuat review ditolak

| Temuan | Kenapa ditolak |
|---|---|
| "Sudah jalan di laptop saya" tanpa test | Tidak bisa dipertahankan saat kode berubah |
| Kriteria berangka dicentang tanpa angka | Klaim tanpa bukti |
| `except Exception: pass` | Menyembunyikan kegagalan, sulit ditelusuri |
| Prompt ditempel di beberapa tempat | Perubahan perilaku jadi tidak terlacak |
| Menambah dependensi di luar stack terkunci | Perlu ADR dan persetujuan dulu |
| API key atau `data/*.db` ikut commit | Masalah keamanan, wajib rotasi kunci |

## 4. Definition of Done per sprint

Sebuah sprint ditutup bila:

1. Seluruh task sprint itu **Done**, atau yang tersisa sudah dipindahkan ke
   sprint berikutnya secara sadar (bukan dilupakan).
2. Demo 5-10 menit dijalankan ke pembimbing dari aplikasi yang **berjalan**,
   bukan dari tangkapan layar.
3. Angka metrik terkait sprint itu dicatat di `projects/ai-agent/docs/EVAL.md`
   supaya perkembangan antar sprint bisa dibandingkan.

## 5. Gerbang Sprint 0

Sprint 1 tidak dibuka sebelum:

- [ ] `projects/ai-agent/docs/PRD.md` terisi penuh (bagian A, B, C).
- [ ] Pembimbing menandai PRD **approved** di merge request.
- [ ] Kerangka proyek jalan: `streamlit run app.py` menampilkan chat dari mock
      provider, `pytest` hijau.
