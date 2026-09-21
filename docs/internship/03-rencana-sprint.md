# Rencana sprint — proyek chatbot LLM

> Dokumen ini **dihasilkan otomatis** dari `backend/app/internship_plan.py`
> (`python scripts/gen_internship_docs.py`). Jangan disunting manual —
> ubah rencananya, lalu jalankan ulang skripnya.

Total **29 task**, estimasi **41.0 hari kerja**, dipecah menjadi 6 sprint. Papan: `/internship` (id `INT-NNN`).

## Aturan kolom

Hanya task **Sprint 0** yang berada di kolom *To do*; sprint berikutnya
menunggu di *Backlog* dan baru ditarik saat sprint sebelumnya ditutup.
Gerbang Sprint 0: **PRD rampung dan disetujui** sebelum kode fitur ditulis.

## Epic

| Label | Epic |
|---|---|
| `epic-konteks` | Epic 1 — Manajemen Konteks & Memori |
| `epic-tooling` | Epic 2 — Orkestrasi & Tooling |
| `epic-guardrail` | Epic 3 — Keamanan & Guardrails |
| `epic-observability` | Epic 4 — Observability & LLMOps |
| `epic-performa` | Epic 5 — Skalabilitas & Performa |
| `epic-prd` | Epic 0 — Produk & PRD |

## Sprint

### Sprint 0 — PRD & Kerangka

Gerbang: PRD disetujui. Repo, skeleton Streamlit, mock LLM.  
*4 task · 5.0 hari · label `sprint-0`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-001` | PRD bagian A: masalah, persona, user story, non-goals | Epic 0 | 1.5 | critical | - |
| `INT-002` | PRD bagian B: metrik sukses, anggaran token & biaya | Epic 0 | 1 | critical | INT-001 |
| `INT-003` | PRD bagian C: arsitektur prototipe + 5 ADR singkat | Epic 0 | 1 | critical | INT-002 |
| `INT-004` | Kerangka proyek: repo, Streamlit 'hello chat', mock provider | Epic 0 | 1.5 | high | INT-003 |

### Sprint 1 — Chat, Sesi & Token

Epic 1: sesi percakapan, hitung token, sliding window, ringkasan.  
*5 task · 7.0 hari · label `sprint-1`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-005` | Provider LLM: OpenAI-compatible + mock, streaming & retry | Epic 1 | 1.5 | critical | INT-004 |
| `INT-006` | UI chat streaming: bubble, status, dan penanganan error | Epic 1 | 1.5 | high | INT-005 |
| `INT-007` | Sesi percakapan: CRUD thread di SQLite + lanjut percakapan | Epic 1 | 1.5 | critical | INT-004 |
| `INT-008` | Hitung token real-time + indikator pemakaian context window | Epic 1 | 1 | high | INT-007 |
| `INT-009` | Sliding window + ringkasan otomatis riwayat lama | Epic 1 | 1.5 | critical | INT-008 |

### Sprint 2 — RAG, Tool & Router

Epic 2: retrieval, function calling, router hemat biaya, memori panjang.  
*6 task · 9.5 hari · label `sprint-2`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-010` | Ingest dokumen: loader + chunking + status pemrosesan | Epic 2 | 1.5 | critical | INT-004 |
| `INT-011` | Embedding + indeks numpy + retrieval top-k berambang | Epic 2 | 1.5 | critical | INT-010 |
| `INT-012` | Jawaban tergrounding + sitasi yang bisa diklik | Epic 2 | 1.5 | critical | INT-011, INT-009 |
| `INT-013` | Tool registry (function calling) + eksekusi aman | Epic 2 | 2 | critical | INT-011 |
| `INT-014` | Router / intent classifier: langsung, RAG, atau tool | Epic 2 | 1.5 | high | INT-013, INT-012 |
| `INT-015` | Memori jangka panjang: fakta & preferensi pengguna | Epic 1 | 1.5 | high | INT-011, INT-009 |

### Sprint 3 — Guardrail

Epic 3: moderasi input, redaksi PII, validasi output terstruktur.  
*4 task · 5.5 hari · label `sprint-3`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-016` | Guardrail input: prompt injection, jailbreak, dan toksisitas | Epic 3 | 1.5 | critical | INT-013 |
| `INT-017` | Redaksi PII sebelum konteks dikirim ke provider | Epic 3 | 1.5 | critical | INT-016 |
| `INT-018` | Validator output terstruktur + retry otomatis | Epic 3 | 1.5 | high | INT-014 |
| `INT-019` | System prompt terkelola + parameter generasi | Epic 3 | 1 | medium | INT-018 |

### Sprint 4 — Observability

Epic 4: tracing, dasbor biaya & latensi, feedback loop, evaluasi.  
*4 task · 6.0 hari · label `sprint-4`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-020` | Tracing per permintaan: span DB, retrieval, LLM, tool | Epic 4 | 2 | critical | INT-014 |
| `INT-021` | Dasbor biaya & latensi: token, Rupiah, TTFT p50/p95 | Epic 4 | 1.5 | high | INT-020 |
| `INT-022` | Feedback 👍/👎 dengan alasan terstruktur + trace_id | Epic 4 | 1 | high | INT-020 |
| `INT-023` | Set evaluasi 20 soal + skrip eval offline | Epic 4 | 1.5 | high | INT-022, INT-012 |

### Sprint 5 — Performa & Rilis

Epic 5: semantic cache, rate limit, fallback model, deploy & demo.  
*6 task · 8.0 hari · label `sprint-5`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-024` | Semantic cache: jawab pertanyaan berulang tanpa panggil LLM | Epic 5 | 1.5 | high | INT-021 |
| `INT-025` | Rate limit & antrean sederhana per pengguna | Epic 5 | 1.5 | high | INT-024 |
| `INT-026` | Fallback model + timeout: layanan tetap menjawab | Epic 5 | 1 | high | INT-025 |
| `INT-027` | Docker + volume persisten untuk prototipe intern | Epic 5 | 1 | critical | INT-026 |
| `INT-028` | Uji menyeluruh: unit, integrasi pipeline, dan smoke UI | Epic 5 | 1.5 | high | INT-027 |
| `INT-029` | Dokumentasi, runbook, dan demo akhir 10 menit | Epic 5 | 1.5 | critical | INT-028, INT-023 |

## Definisi selesai

Kriteria selesai tiap task ada di papan `/internship` (tab *Kriteria
selesai*) dan harus terpenuhi seluruhnya — lihat
[04-definition-of-done.md](04-definition-of-done.md).
