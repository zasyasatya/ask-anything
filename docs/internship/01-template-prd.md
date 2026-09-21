# Template PRD — chatbot LLM internal

Target Sprint 0: dokumen ini **terisi penuh dan disetujui pembimbing** sebelum
kode fitur ditulis. Salin isi berkas ini ke `projects/ai-agent/docs/PRD.md`,
lalu isi setiap bagian. Bagian yang belum diisi ditulis `TBD — <siapa> <kapan>`,
tidak dihapus.

Task terkait: **INT-001** (bagian A), **INT-002** (bagian B), **INT-003**
(bagian C).

---

## A. Produk (INT-001)

### A1. Pernyataan masalah
> Maksimal satu paragraf. Sebutkan siapa yang dirugikan hari ini dan berapa
> besar kerugiannya (waktu/uang/kesalahan).

### A2. Persona

| Persona | Peran | Tujuan | Titik nyeri |
|---|---|---|---|
| Karyawan umum | | | |
| Power user | | | |
| Admin | | | |

### A3. User story (tepat 10)

| Id | Story | Cara uji |
|---|---|---|
| US-01 | Sebagai … saya ingin … supaya … | |
| … | | |

### A4. Non-goals (minimal 5)

Contoh yang sudah disepakati — tambahkan milik sendiri:

1. Tidak ada input/output suara.
2. Tidak multi-tenant (satu organisasi saja).
3. Tidak ada fine-tuning model.
4. Tidak ada aplikasi mobile.
5. Tidak ada integrasi SSO perusahaan.

### A5. Risiko & asumsi

| Risiko | Dampak | Mitigasi |
|---|---|---|

---

## B. Metrik & anggaran (INT-002)

### B1. Metrik sukses

| Metrik | Target | Cara ukur (sumber data) |
|---|---|---|
| Jawaban tergrounding (punya sitasi valid) | ≥ 80% dari 20 soal eval | `eval.py` + `evalset.yaml` |
| p95 Time To First Token | ≤ 3 dtk (mock) / ≤ 6 dtk (nyata) | span `llm_stream` di tabel `traces` |
| Rasio 👍 | ≥ 70% | tabel `feedback` |
| Biaya per percakapan | ≤ Rp500 | token × harga per 1k token |
| Cache hit-rate (pertanyaan berulang) | ≥ 20% | tabel `cache` |

### B2. Anggaran token

| Pos | Batas |
|---|---|
| Context window terpakai | 8.000 token |
| Jawaban maksimum | 1.024 token |
| Konteks RAG | 2.500 token |
| Ringkasan riwayat | 200 token |
| Memori jangka panjang | 300 token |

### B3. Kuota per pengguna

| Batas | Nilai |
|---|---|
| Pesan per menit | 10 |
| Pesan per hari | 50 |
| Token per hari | 100.000 |

### B4. Rumus biaya

```
biaya = (prompt_tokens / 1000 × harga_prompt) + (completion_tokens / 1000 × harga_completion)
```

Contoh perhitungan satu percakapan nyata (isi dengan angka sungguhan): …

---

## C. Arsitektur & keputusan (INT-003)

### C1. Alur satu jawaban

```
UI (Streamlit)
  -> guardrail input (injection, PII, panjang)
  -> router (langsung | dokumen | tool)
  -> retrieval / tool
  -> penyusun konteks (anggaran token)
  -> LLM (streaming, fallback model)
  -> validator output
  -> trace + akuntansi biaya
  -> UI (jawaban + sitasi + 👍/👎)
```

### C2. ADR (5 keputusan)

Untuk tiap ADR tulis: **Konteks** (apa masalahnya) → **Keputusan** (apa yang
dipilih) → **Konsekuensi** (apa yang jadi lebih mudah, apa yang jadi lebih
sulit, kapan keputusan ini perlu ditinjau ulang).

| # | Keputusan |
|---|---|
| ADR-1 | UI prototipe memakai Streamlit, bukan React/Next.js |
| ADR-2 | SQLite satu berkas sebagai satu-satunya database |
| ADR-3 | Embedding lokal + numpy cosine, bukan vector database |
| ADR-4 | Tracing sendiri ke tabel `traces`, bukan layanan pihak ketiga |
| ADR-5 | Mock provider wajib ada supaya demo & test jalan tanpa kuota API |

### C3. Struktur folder

Lihat [02-arsitektur-prototipe.md](02-arsitektur-prototipe.md) — salin ke sini
apa adanya bila tidak ada perubahan.

---

## D. Persetujuan

| Peran | Nama | Tanggal | Status |
|---|---|---|---|
| Intern | | | |
| Pembimbing | | | ☐ approved |
