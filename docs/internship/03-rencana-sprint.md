# Rencana sprint — Internal AI Assistant & RAG Agent

> Dokumen ini **dihasilkan otomatis** dari `backend/app/internship_plan.py`
> (`python scripts/gen_internship_docs.py`). Jangan disunting manual —
> ubah rencananya, lalu jalankan ulang skripnya.

Total **33 task**, estimasi **48.5 hari kerja**, dipecah menjadi 6 sprint. Papan: `/internship` (id `INT-NNN`).

## Aturan kolom

Sprint 0 (PRD A-C + boilerplate monorepo) **sudah selesai** (kolom *Done*);
sprint berikutnya menunggu di *Backlog* dan baru ditarik saat sprint
sebelumnya ditutup. Rencana mengikuti PRD terbaru
([01-template-prd.md](01-template-prd.md)) dan design system beUI
([05-design-system.md](05-design-system.md)). Papan bisa disunting dari UI;
dokumen ini hanya memotret rencana bawaan.

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

Gerbang: PRD disetujui. PRD A–C + boilerplate monorepo Next.js & FastAPI.  
*5 task · 7.5 hari · label `sprint-0`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-001` | PRD bagian A: masalah, persona, user story, non-goals | Epic 0 | 1.5 | critical | - |
| `INT-002` | PRD bagian B: metrik sukses, anggaran token & biaya | Epic 0 | 1 | critical | INT-001 |
| `INT-003` | PRD bagian C: arsitektur prototipe + 5 ADR singkat | Epic 0 | 1 | critical | INT-002 |
| `INT-004` | Kerangka proyek: repo, Streamlit 'hello chat', mock provider | Epic 0 | 1.5 | high | INT-003 |
| `INT-005` | Repo boilerplate: monorepo Clean Architecture, DB, LLM & beUI | Epic 0 | 2.5 | critical | INT-004 |

### Sprint 1 — Chat, Sesi & Token

Epic 1: chat streaming, auth & peran, sesi di PostgreSQL, token, memori multi-turn.  
*5 task · 6.5 hari · label `sprint-1`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-006` | Protokol SSE v1 + UI chat streaming (beUI) | Epic 1 | 1.5 | critical | INT-005 |
| `INT-007` | Autentikasi sesi + peran (karyawan, power user, admin) | Epic 3 | 1 | critical | INT-005 |
| `INT-008` | Sesi percakapan persisten di PostgreSQL + sidebar | Epic 1 | 1.5 | critical | INT-005, INT-007 |
| `INT-009` | Hitung token + anggaran konteks 8k + indikator pemakaian | Epic 1 | 1 | high | INT-008 |
| `INT-010` | Memori multi-turn: sliding window + ringkasan otomatis | Epic 1 | 1.5 | critical | INT-009, INT-008 |

### Sprint 2 — RAG, Tool & Router

Epic 2: ingestion PDF/DOCX/MD, pgvector, sitasi, router, tool, GraphView & chart.  
*9 task · 15.0 hari · label `sprint-2`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-011` | Ingestion dokumen PDF, DOCX, dan Markdown + chunking | Epic 2 | 1.5 | critical | INT-007, INT-005 |
| `INT-012` | Embedding lokal + pgvector (HNSW) + retrieval ambang 0.7 | Epic 2 | 1.5 | critical | INT-011 |
| `INT-013` | Jawaban tergrounding + sitasi CitationBadge | Epic 2 | 1.5 | critical | INT-012, INT-010 |
| `INT-014` | Kelola dokumen: filter saat bertanya + hapus bersih dari vector DB | Epic 2 | 1.5 | high | INT-013 |
| `INT-015` | Tool registry (function calling) + agent loop berbatas | Epic 2 | 2 | critical | INT-013 |
| `INT-016` | Router intent: Q&A dokumen, visualisasi, atau percakapan umum | Epic 2 | 1.5 | high | INT-015 |
| `INT-017` | Visual interaktif: GraphView flowchart & korelasi antardokumen | Epic 2 | 2 | high | INT-016, INT-014 |
| `INT-018` | Visual interaktif: ChartRenderer bar chart dari tabel dokumen | Epic 2 | 1.5 | high | INT-016, INT-011 |
| `INT-033` | Pipeline RAG end-to-end: kontrak antar tahap, integrasi, dan uji golden set | Epic 2 | 2 | critical | INT-011, INT-012, INT-013 |

### Sprint 3 — Guardrail

Epic 3: guardrail input, redaksi PII, validator output, uji red-team.  
*4 task · 5.5 hari · label `sprint-3`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-019` | Guardrail input: panjang, prompt injection, jailbreak, topik terlarang | Epic 3 | 1.5 | critical | INT-016 |
| `INT-020` | Redaksi PII sebelum konteks dikirim ke provider | Epic 3 | 1.5 | critical | INT-019 |
| `INT-021` | Validator output: grounding, ambang 0.7, dan skema visual | Epic 3 | 1.5 | high | INT-018, INT-017, INT-013 |
| `INT-022` | Uji red-team otomatis + laporan guardrail | Epic 3 | 1 | high | INT-021, INT-020 |

### Sprint 4 — Observability

Epic 4: tracing, token & biaya, feedback, evaluasi 20 soal.  
*4 task · 6.0 hari · label `sprint-4`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-023` | Tracing mandiri: span 7 tahap ke tabel PostgreSQL + halaman trace | Epic 4 | 2 | critical | INT-016, INT-007 |
| `INT-024` | Biaya & token: kalkulator Rupiah, inspektur respons, dasbor admin | Epic 4 | 1.5 | high | INT-023, INT-009 |
| `INT-025` | Feedback suka/tidak suka dengan alasan terstruktur + trace_id | Epic 4 | 1 | high | INT-023 |
| `INT-026` | Set evaluasi 20 soal + skrip eval offline (metrik tergrounding) | Epic 4 | 1.5 | high | INT-025, INT-021 |

### Sprint 5 — Performa & Rilis

Epic 5: semantic cache, kuota, fallback provider, deploy persisten & demo.  
*6 task · 8.0 hari · label `sprint-5`*

| Id | Task | Epic | Hari | Prioritas | Prasyarat |
|---|---|---|---|---|---|
| `INT-027` | Semantic cache di PostgreSQL: jawab pertanyaan berulang tanpa LLM | Epic 5 | 1.5 | high | INT-024, INT-014 |
| `INT-028` | Kuota harian 50 pesan / 100.000 token + rate limit per pengguna | Epic 5 | 1.5 | high | INT-027, INT-009 |
| `INT-029` | Rantai provider LLM + fallback dan timeout (mock selalu cadangan) | Epic 5 | 1 | high | INT-028 |
| `INT-030` | Deploy persisten: Docker Compose + volume PostgreSQL/pgvector + Coolify | Epic 5 | 1 | critical | INT-029, INT-012 |
| `INT-031` | Uji menyeluruh: unit, integrasi pipeline, dan e2e smoke | Epic 5 | 1.5 | high | INT-030 |
| `INT-032` | Dokumentasi, runbook, demo 10 menit, dan metrik nyata vs target PRD | Epic 5 | 1.5 | critical | INT-031, INT-026 |

## Definisi selesai

Kriteria selesai tiap task ada di papan `/internship` (tab *Kriteria
selesai*) dan harus terpenuhi seluruhnya — lihat
[04-definition-of-done.md](04-definition-of-done.md).
