# Task Management — papan rencana RAG (`/tasks`)

Papan kerja developer untuk seluruh rencana **RAG × AI Agent**: papan kanban
(atau daftar), detail task dengan checklist & komentar, statistik progres, dan
sinkronisasi otomatis dengan branch/commit GitLab.

Buka **`/tasks`** (tautan “Tasks” ada di sidebar & konsol admin). Papan terisi
sendiri saat backend pertama kali dijalankan: seluruh task rencana dimuat dari
`backend/app/tasks_plan.py`.

---

## 1. Konsep inti: task id = nama branch GitLab

Setiap task punya id berformat **`ASK-NNN`** yang dipakai apa adanya di nama
branch, jadi riwayat GitLab dan papan ini bisa saling dikaitkan tanpa tabel
pemetaan tambahan:

```
ASK-012  →  feat/ASK-012-halaman-task-management-papan-kanban-list
```

* Prefiks mengikuti label task: `bug`/`bugfix` → `fix/`, `docs` → `docs/`,
  `test`/`testing` → `test/`, `performance` → `perf/`, selain itu `feat/`.
* Nama branch disarankan backend (`branch_name`) dan perintah siap salin
  (`git_command`) ditampilkan di kartu task & panel detail.
* URL merge request bisa ditempel di panel detail (`mr_url`) supaya bisa dibuka
  satu klik dari papan.

## 2. Papan & tampilan

| Bagian | Fungsi |
|---|---|
| **Kolom** | `Backlog → To do → In progress → Review → Done` (drag & drop antar kolom, atau tombol `→` pada kartu) |
| **Daftar** | Tabel padat (id, task, fase, status, prioritas, owner, estimasi, terakhir diperbarui) — status bisa diubah langsung dari baris |
| **Filter** | Pencarian (id/judul/label/branch), fase, status (klik chip statistik), assignee, prioritas, label |
| **Kelompokkan per fase** | Melihat enam fase rencana (Platform, Ingest, Retrieval, Agent×RAG, Visual Web, Polish) sebagai bagian terpisah |
| **Statistik** | Progres keseluruhan, jumlah per kolom, total estimasi hari, jumlah task menunggu prasyarat, dan yang siap dikerjakan |
| **Detail task** | Panel bertab supaya tidak ramai — **Ringkasan** (tujuan, checklist kriteria selesai, prasyarat), **Workflow** (alur kerja bernomor: aktor → aksi → hasil), **Wireframe** (sketsa layout/bentuk data + berkas bukti), **Aktivitas** (branch, commit, merge request, komentar & riwayat). Baris kendali (status, prioritas, fase, assignee, estimasi) tetap terlihat di semua tab. |

Kartu menampilkan penanda **⛔ n** bila prasyaratnya belum selesai, dan setiap
pindah status otomatis tercatat sebagai aktivitas di panel detail.

Header papan sengaja dijaga ringkas: progres + jumlah per kolom + pencarian
dalam satu baris, filter lanjutan (fase, assignee, prioritas, label,
kelompokkan per fase) dilipat di balik tombol **Filter** (dengan penghitung
filter aktif), dan aksi admin (Sync git, Muat/Reset rencana, token) berada di
menu **⋯**.

### Detail task: deskripsi, workflow, wireframe

Tiap task rencana ditulis agar bisa langsung dikerjakan tanpa bertanya lagi:

| Bagian | Isi |
|---|---|
| `description` | Konteks + keputusan teknis yang sudah ditetapkan & batasannya |
| `workflow` | Daftar langkah `{actor, action, result}` — siapa melakukan apa, hasilnya apa. Nomor langkah diisi otomatis backend |
| `wireframe` | Sketsa ASCII: layout layar untuk task UI, atau bentuk data/diagram alur untuk task backend |
| `acceptance` | Kriteria selesai yang bisa dicentang dan diuji |
| `evidence` | Berkas yang harus ada (diperiksa `POST /api/tasks/sync`) |
| `depends_on` | Prasyarat, menentukan urutan pengerjaan |

Keduanya bisa diisi saat membuat task (`POST /api/tasks`) atau diubah lewat
`PATCH /api/tasks/{id}`; **member tidak boleh mengubahnya** — rancangan task
adalah keputusan admin.

## 3. Sinkronisasi dengan git & kode

Tombol **⟳ Sync git** (`POST /api/tasks/sync`) menyelaraskan papan dengan
kenyataan repo:

| Bukti | Efek pada task |
|---|---|
| Semua berkas di `evidence` ada di repo | status minimal **Review** |
| Ada branch yang memuat `ASK-NNN` | `branch` diisi, status minimal **In progress** |
| Ada commit yang menyebut `ASK-NNN` | sha + subjek disimpan (maks. 20), status minimal **In progress** |
| Subjek commit memuat kata selesai (`close`, `fix`, `done`, `selesai`, `merge`, …) | status menjadi **Done** |

Status **tidak pernah turun otomatis** — pekerjaan yang sudah dipindah manual
ke Done tidak akan dikembalikan. Pesan perubahan dicatat sebagai aktivitas,
dan laporan sync menampilkan berapa task berubah + berapa branch/commit
diperiksa. Bila folder kerja bukan repo git (mis. dijalankan dari zip), pesannya
diberitahukan dan hanya pemeriksaan berkas `evidence` yang berjalan.

## 4. Seed & reset

* Saat backend start dan tabel task masih kosong, `ASK_TASKS_AUTOSEED=1`
  (default) memuat seluruh rencana lalu menjalankan sync sekali agar papan
  langsung mencerminkan kondisi repo.
* Tombol **Muat rencana RAG** (`POST /api/tasks/seed`) bersifat idempoten:
  task yang id-nya sudah ada **tidak ditimpa**, jadi perubahan tangan developer
  aman.
* Tombol **Reset rencana** (`POST /api/tasks/seed?reset=true`) menghapus hanya
  task hasil seed (`seeded=1`) lalu membuatnya ulang; task buatan sendiri
  beserta komentarnya tetap ada.

## 5. HTTP API

Semua endpoint memakai pengaman yang sama dengan konsol admin: **sesi role
admin** (login `/login`), atau header `X-Admin-Token` bila `ASK_ADMIN_TOKEN`
diset (di UI: tombol 🔑). **Member** mendapat jalur terbatas: `GET /api/tasks`
otomatis disaring ke task yang ditugaskan kepadanya (`tasks_scope=assigned`)
dan hanya boleh memindahkan status/mengomentari task itu — membuat,
menghapus, seed, dan sync tetap khusus admin.

Papan punya **dua trek** (`track=platform` → `ASK-NNN`, `track=internship` →
`INT-NNN`) dengan statistik dan seeder terpisah; ringkasan trek internship juga
tersedia lewat `GET /api/internship/overview` (otomatis menyesuaikan peran).

```text
GET    /api/tasks?track=&status=&phase=&assignee=&priority=&label=&q=&seeded=
       → { tasks, stats, plan, statuses, repo, track, scope }
GET    /api/tasks/plan
GET    /api/tasks/{id}                 → task + komentar + prasyarat + dependen
POST   /api/tasks                      buat task (id otomatis ASK-NNN)
PATCH  /api/tasks/{id}                 ubah field apa pun (title, status, …)
DELETE /api/tasks/{id}
POST   /api/tasks/{id}/move            { status, before_id }  (drag & drop)
POST   /api/tasks/{id}/comments        { body, author }
DELETE /api/tasks/comments/{comment_id}
POST   /api/tasks/{id}/acceptance      { index, done } | { text } | { index, remove }
POST   /api/tasks/seed?reset=true|false&track=…
POST   /api/tasks/sync                 → { changed, branches, commits, tasks, stats }
```

Field task: `id, title, description, phase, status, priority, assignee,
estimate, labels[], acceptance[{text,done}], depends_on[], evidence[], source,
workflow[{step,actor,action,result}], wireframe, branch, mr_url,
commits[{sha,subject}], position, seeded, created_at, updated_at, completed_at` + turunan `branch_name, git_command, progress,
acceptance_done/total, blocked_by, ready`.

## 6. Struktur kode

| Berkas | Isi |
|---|---|
| `backend/app/tasks_plan.py` | Data rencana platform (6 fase, 54 task) + fase/status/prioritas yang dikenal |
| `backend/app/internship_plan.py` | Data rencana **chatbot AI agent production-ready** (6 fase `i0`–`i5`, 36 task `INT-NNN` ±54 hari kerja, penugasan round-robin peserta). Tiap task memuat deskripsi, workflow, dan wireframe |
| `backend/app/tasks.py` | Logika: CRUD, kolom & posisi, checklist, komentar, statistik, seeder, `sync()` git, `branch_name()` |
| `backend/app/api/tasks.py` | Router `/api/tasks/*` (Pydantic + guard `X-Admin-Token`) |
| `backend/app/startup.py` | Catatan startup (dipakai juga oleh `/api/health` & `run.py`) |
| `frontend/app/tasks/page.tsx` | Halaman `/tasks` |
| `frontend/components/tasks/` | `TasksConsole`, `TaskBoard`, `TaskCard`, `TaskList`, `TaskDetail`, `TaskForm` |
| `frontend/lib/tasks.ts` | Tipe, pemanggilan API, helper filter/slug/branch |
| `backend/tests/test_tasks_api.py` | 14 test API + aturan seed/sync |

## 7. Menambah task rencana baru

1. Tambahkan entri di `TASKS` (`backend/app/tasks_plan.py`) dengan **id baru**
   (`ASK-055`, …) — jangan mengubah id lama karena sudah dipakai nama branch.
2. Isi `acceptance` (checklist) dan, bila ada, `evidence` (berkas penanda
   implementasi) supaya sync bisa menandai progres.
3. Jalankan `python -m pytest tests/test_tasks_api.py` (test menjaga id unik,
   fase valid, dan setiap task punya kriteria selesai).
4. `POST /api/tasks/seed` pada instance yang sudah jalan akan menambahkan task
   baru tanpa menyentuh yang lama.
