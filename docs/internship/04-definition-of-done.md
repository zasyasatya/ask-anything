# Definition of Done & checklist review

Satu task dianggap **Done** hanya bila seluruh baris di bawah terpenuhi.
Tidak ada "done sebagian": kalau ada yang belum, task tetap di *In progress*
atau *Review* dengan catatan jelas di komentar.

## 1. Checklist per task

- [ ] Semua **kriteria selesai** di papan tercentang, dan yang berangka
      benar-benar **diukur** (angkanya ditulis di komentar task, bukan ditaksir).
- [ ] Berkas **evidence** yang tercantum di task benar-benar ada di repo.
- [ ] Ada **test** untuk jalur utama task ini; `pytest backend/tests` dan
      `npm test` hijau seluruhnya.
- [ ] Jalan di mesin bersih **tanpa API key** (Mock Provider + embedder stub).
- [ ] Tidak ada rahasia (API key, token, `.env`, dump database) ikut commit.
- [ ] README/runbook diperbarui bila cara menjalankan berubah.
- [ ] Merge request dibuka, di-review, dan di-merge.

## 2. Checklist khusus task LLM

- [ ] **Prompt** disimpan di modul prompt (`application/prompts`), bukan ditempel di tengah logika.
- [ ] Batas **token** dihormati: prompt akhir tidak pernah melewati anggaran.
- [ ] Kegagalan model (timeout, 5xx, JSON rusak) **tidak** membuat aplikasi mati
      — ada retry atau nilai default yang aman.
- [ ] Jalur ini menulis **span trace** (`traces`) sehingga durasinya terlihat.
- [ ] Token & biaya yang dipakai tercatat di `token_usage_logs`.
- [ ] Ambang retrieval (similarity >= 0.7) dan anggaran token (8.192 / 1.024) dihormati.
- [ ] Data pribadi tidak pernah dikirim mentah ke provider pihak ketiga.
- [ ] Tool agent hanya dari registry (tanpa shell/OS bebas — non-goal #5).

## 2b. Checklist khusus task UI (design system beUI)

- [ ] Komponen berasal dari registri beUI (`npx shadcn add @beui/<slug>`),
      bukan komponen kustom yang menduplikasi fungsinya.
- [ ] Ikon hanya dari `lucide-react`; **tidak ada emoji** di kode, teks UI,
      maupun copywriting (cek dengan `grep`).
- [ ] Warna memakai token CSS (`bg-background`, `text-foreground`, ...), bukan
      kode heksa; tampil benar di light mode (default) **dan** dark mode.
- [ ] Elemen interaktif punya ring fokus; status streaming memakai
      `role="status"` / `aria-live="polite"`; `prefers-reduced-motion` dihormati.
- [ ] Komponen hanya presentasi: tidak memanggil `fetch`/SSE langsung (lewat
      `interface-adapters/controllers` dan `infrastructure/`).

## 3. Yang membuat review ditolak

| Temuan | Kenapa ditolak |
|---|---|
| "Sudah jalan di laptop saya" tanpa test | Tidak bisa dipertahankan saat kode berubah |
| Kriteria berangka dicentang tanpa angka | Klaim tanpa bukti |
| `except Exception: pass` | Menyembunyikan kegagalan, sulit ditelusuri |
| Prompt ditempel di beberapa tempat | Perubahan perilaku jadi tidak terlacak |
| Menambah dependensi di luar stack terkunci | Perlu ADR dan persetujuan dulu |
| API key, `.env`, atau dump database ikut commit | Masalah keamanan, wajib rotasi kunci |
| Emoji atau ikon di luar lucide-react | Melanggar design system |

## 4. Definition of Done per sprint

Sebuah sprint ditutup bila:

1. Seluruh task sprint itu **Done**, atau yang tersisa sudah dipindahkan ke
   sprint berikutnya secara sadar (bukan dilupakan).
2. Demo 5-10 menit dijalankan ke pembimbing dari aplikasi yang **berjalan**,
   bukan dari tangkapan layar.
3. Angka metrik terkait sprint itu dicatat di `docs/EVAL.md` repo prototipe
   (`ai-assistant-prototype`) supaya perkembangan antar sprint bisa dibandingkan.

## 5. Gerbang Sprint 0 (sudah terlewati)

Sprint 1 dibuka setelah:

- [x] PRD terisi penuh (bagian A, B, C) di `docs/internship/01-template-prd.md`.
- [x] Pembimbing menyetujui PRD lewat merge request (INT-001..003).
- [x] Boilerplate monorepo jalan: `python run.py` menjalankan FastAPI + Next.js,
      `pytest backend/tests` hijau, deploy Docker/Coolify terdokumentasi (INT-005).
