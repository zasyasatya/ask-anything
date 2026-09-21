# Arsitektur prototipe (sudah dikunci)

Tujuan magang ini adalah **kualitas lapisan LLM**, bukan kerumitan
infrastruktur. Karena itu stack di bawah sudah ditetapkan — tidak perlu
dibandingkan ulang, tidak perlu ditambah tanpa ADR yang disetujui.

## 1. Stack

| Lapisan | Pilihan | Catatan |
|---|---|---|
| Bahasa | Python 3.11 | satu bahasa untuk seluruh proyek |
| UI | **Streamlit** | prototipe tampilan, `streamlit run app.py` |
| Database | **SQLite** (`sqlite3` stdlib) | satu berkas `data/agent.db` |
| Vektor | `numpy` + cosine similarity, disimpan `data/index.npy` | bukan vector DB |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` | fallback TF-IDF bila model gagal dimuat |
| Token | `tiktoken` (`cl100k_base`) | fallback perkiraan `len/4` |
| LLM | endpoint OpenAI-compatible + **mock provider** | mock wajib jalan tanpa API key |
| Validasi | `pydantic` | skema output terstruktur |
| Test | `pytest` (+ `pytest-cov`) | satu perintah, tanpa API key |
| Kemasan | Docker + named volume | seluruh state di `/app/data` |

### Yang sengaja TIDAK dipakai

PostgreSQL, Redis, Milvus/Qdrant/FAISS server, Kafka/RabbitMQ, Kubernetes,
LangChain/LlamaIndex, LangSmith/Datadog/Phoenix, React/Next.js.

Alasan: semuanya memindahkan waktu magang dari "membuat LLM berperilaku benar"
ke "mengurus infrastruktur". Kalau nanti produk ini naik ke produksi nyata,
ADR di PRD bagian C sudah mencatat kapan keputusan ini perlu ditinjau ulang.

## 2. Struktur folder

```
projects/ai-agent/
  app.py                 UI Streamlit: chat, riwayat, pengetahuan, dasbor, trace
  eval.py                penjalan set evaluasi (INT-023)
  evalset.yaml           20 soal uji
  requirements.txt
  Dockerfile
  docker-compose.yml
  core/
    config.py            baca env (AGENT_*)
    db.py                koneksi + skema SQLite
    providers.py         LLMProvider: OpenAI-compatible + mock
    llm.py               pemanggilan + fallback model + retry
    session.py           CRUD sesi & pesan
    tokens.py            hitung token (tiktoken + fallback)
    context.py           anggaran token, sliding window, ringkasan
    memory.py            memori jangka panjang (fakta & preferensi)
    ingest.py            loader dokumen + chunking
    embed.py             embedding + index.npy
    rag.py               pencarian top-k + ambang skor
    prompts.py           template prompt + aturan sitasi
    tools.py             registry function calling
    agent.py             loop panggil-tool (maks 3 iterasi)
    router.py            klasifikasi rute (langsung | dokumen | tool)
    guardrail.py         moderasi input
    pii.py               redaksi data pribadi
    structured.py        parse JSON + retry berpesan error
    schemas.py           model pydantic
    tracing.py           span + tabel traces
    analytics.py         agregasi token, biaya, latensi
    feedback.py          👍/👎 + alasan
    cache.py             semantic cache
    quota.py             rate limit & kuota harian
    settings_store.py    system prompt & parameter generasi
  tests/
  data/                  (diabaikan git; di Docker = volume /app/data)
    agent.db  index.npy  docs/
```

## 3. Alur satu jawaban

```
pertanyaan
  1  guardrail input      tolak injection / PII mentah / terlalu panjang
  2  router               langsung? butuh dokumen? butuh tool?
  3  cache lookup         cosine >= 0.92 & umur < 24 jam -> jawab, selesai
  4  retrieval / tool     top-k chunk (ambang 0.35) atau panggilan tool
  5  penyusun konteks     system + memori + ringkasan + konteks + riwayat <= 8k
  6  LLM                  streaming; gagal -> model cadangan -> mock
  7  validator output     JSON valid? sitasi ada di konteks?
  8  simpan               pesan, token, biaya, span trace
  9  UI                   jawaban + sitasi + 👍/👎 + trace_id
```

## 4. Variabel lingkungan

| Env | Default | Arti |
|---|---|---|
| `AGENT_PROVIDER` | `mock` | `mock` atau `openai` |
| `AGENT_BASE_URL` | — | endpoint OpenAI-compatible |
| `AGENT_API_KEY` | — | kunci API (jangan pernah di-commit) |
| `AGENT_MODELS` | `mock` | daftar model berurut: utama, cadangan, `mock` |
| `AGENT_DB_PATH` | `data/agent.db` | di Docker: `/app/data/agent.db` |
| `AGENT_INDEX_PATH` | `data/index.npy` | di Docker: `/app/data/index.npy` |
| `AGENT_DOCS_DIR` | `data/docs` | di Docker: `/app/data/docs` |

## 5. Aturan persistensi

Semua yang harus selamat dari redeploy berada di bawah **satu** folder
(`/app/data` di container, `data/` di lokal): database, indeks vektor, dokumen
mentah, dan model embedding yang terunduh. Tidak ada state yang ditulis ke
dalam layer image. Ini diuji di **INT-027**: build ulang image, deploy ulang,
percakapan dan dokumen lama harus tetap ada.
