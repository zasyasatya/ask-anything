# Product Requirement Document (PRD)
## Internal AI Assistant & RAG Agent Prototype

* **Kode Dokumen**: `PRD-INT-001 / PRD-INT-002 / PRD-INT-003`
* **Status**: `Draft (Bagian A, B, & C Selesai - Menunggu Review Pembimbing)`
* **Sprint**: `Sprint 0 — PRD & Kerangka`
* **Author / Assignee**: `verisimb`
* **Target Merge Request**: `docs/INT-003-prd-bagian-c-arsitektur-prototipe-5-adr-si` → `develop`

---

## BAGIAN A: Masalah, Persona, User Story, & Non-Goals

### 1. Pernyataan Masalah (Problem Statement)
Karyawan operasional, analis bisnis, dan administrator internal perusahaan saat ini menghabiskan waktu berjam-jam setiap harinya untuk mencari, membaca, dan memverifikasi informasi dari puluhan dokumen SOP, panduan teknis, dan laporan bisnis multi-halaman yang tersebar, di mana upaya mencari jawaban secara mandiri sering kali terhambat oleh keterbatasan pencarian kata kunci konvensional atau menimbulkan risiko keamanan data jika menggunakan chatbot publik eksternal yang rentan berhalusinasi dan tidak dapat diverifikasi ke sumber aslinya.

---

### 2. Persona Pengguna

#### Persona 1: Karyawan Biasa (Staf Operasional / HR / Umum)
* **Deskripsi**: Staf internal harian yang membutuhkan jawaban cepat terkait prosedur kerja, regulasi perusahaan, dan kebijakan operasional tanpa perlu membuka dan membaca puluhan halaman dokumen PDF/DOCX.
* **Tujuan (Goals)**:
  * Menemukan jawaban pasti dan ringkas atas pertanyaan seputar dokumen perusahaan dalam hitungan detik.
  * Memperoleh tautan sitasi nomor halaman/sumber dokumen yang dapat diverifikasi secara transparan.
  * Mengajukan pertanyaan lanjutan (*follow-up*) secara alami tanpa kehilangan konteks percakapan sebelumnya.
* **Titik Nyeri (Pain Points)**:
  * Kehabisan waktu produktif hanya untuk mencari bab/pasal yang relevan di dokumen pedoman tebal.
  * Khawatir mendapatkan informasi yang salah atau versi dokumen yang sudah usang (*outdated*).
  * Tidak percaya pada jawaban chatbot umum yang kerap mengarang jawaban (*halusinasi*).

#### Persona 2: Power User (Business Analyst / Project Manager / Tim Teknis)
* **Deskripsi**: Pengguna mahir yang sering berinteraksi dengan laporan analisis, data tabel, dan alur proses bisnis yang membutuhkan visualisasi interaktif langsung dari data dokumen.
* **Tujuan (Goals)**:
  * Mengekstraksi struktur alur kerja di dalam SOP menjadi diagram visual/flowchart interaktif yang dapat diinspeksi.
  * Memvisualisasikan korelasi antardokumen (di mana tiap dokumen diwakili sebagai 1 node) untuk memetakan keterkaitan regulasi atau rujukan (misalnya: konteks relasi antardokumen SOP Ketenagakerjaan di PT. XYZ dengan dokumen SK Menteri Ketenagakerjaan).
  * Mengubah data tabel yang tertanam di dokumen menjadi grafik (chart) dan tabel interaktif yang dapat diurutkan/difilter.
  * Membatasi ruang pencarian asisten hanya pada dokumen tertentu agar analisis data terfokus dan akurat.
* **Titik Nyeri (Pain Points)**:
  * Kesulitan dalam mencari dan melacak konteks klausul antardokumen yang saling berelasi (misalnya korelasi aturan ketenagakerjaan antara dokumen internal kantor dengan SK Kementerian Ketenagakerjaan).
  * Harus menggambar ulang diagram proses secara manual di aplikasi pihak ketiga untuk presentasi atau dokumentasi.
  * Mengetik ulang angka-angka tabel dari file PDF/DOCX ke spreadsheet yang memakan waktu dan rentan salah input.
  * Kesulitan membedakan konteks dokumen antar divisi jika semua dokumen tercampur dalam satu pencarian.

#### Persona 3: Admin (IT Administrator / Compliance & Operations Lead)
* **Deskripsi**: Penanggung jawab teknis dan operasional yang bertugas mengelola repositori dokumen, mengawasi kepatuhan, serta memantau efisiensi biaya pemakaian API LLM.
* **Tujuan (Goals)**:
  * Mengunggah, memperbarui, dan menghapus dokumen dari repositori knowledge base dan vector store dengan mudah.
  * Memantau transparansi penggunaan token (prompt & completion) serta estimasi biaya (*cost tracking*) dari setiap pemanggilan model.
  * Memastikan sistem hanya memberikan jawaban grounded berdasarkan dokumen yang diunggah dan tidak membocorkan data di luar konteks.
* **Titik Nyeri (Pain Points)**:
  * Ketakutan lonjakan biaya tak terduga akibat penggunaan API LLM tanpa adanya logging kuota atau estimasi biaya per sesi.
  * Risiko residu data atau dokumen lama yang sudah kedaluwarsa tetap tersimpan di database vektor dan menghasilkan jawaban usang.
  * Ketiadaan visibilitas mengenai apakah asisten benar-benar memanggil tool yang tepat atau hanya berhalusinasi.

---

### 3. Tepat 10 User Story Baku & Cara Uji

Format: *Sebagai `<persona>`, saya ingin `<aksi>`, supaya `<manfaat>`.*

1. **US-01: Q&A Dokumen Internal Berbasis Konteks (Grounded)**
   * **Story**: Sebagai *karyawan biasa*, saya ingin menanyakan pertanyaan dalam bahasa alami mengenai SOP atau regulasi perusahaan, supaya saya mendapatkan jawaban akurat yang bersumber langsung dari dokumen internal tanpa rekayasa.
   * **Cara Uji**: Ajukan pertanyaan "Berapa hari jatah cuti tahunan?", verifikasi sistem menjawab "12 hari" sesuai isi file SOP dan tidak mengarang informasi di luar teks.

2. **US-02: Transparansi Sitasi Sumber Terverifikasi**
   * **Story**: Sebagai *karyawan biasa*, saya ingin melihat badge sitasi sumber `[1]` pada setiap poin jawaban, supaya saya dapat memeriksa keabsahan kutipan langsung ke nama dokumen dan nomor halaman aslinya.
   * **Cara Uji**: Klik badge sitasi `[1]` pada balasan chat, verifikasi muncul rujukan nama file dokumen sumber dan nomor halaman yang sesuai.

3. **US-03: Penanganan Query di Luar Konteks (Anti-Halusinasi)**
   * **Story**: Sebagai *karyawan biasa*, saya ingin asisten menyatakan tidak tahu secara sopan jika informasi yang ditanyakan tidak tercantum dalam dokumen, supaya saya tidak disesatkan oleh jawaban halusinasi.
   * **Cara Uji**: Tanyakan hal di luar isi dokumen yang diunggah (misal: "Aturan perjalanan dinas ke luar angkasa"), verifikasi asisten menjawab bahwa informasi tidak ditemukan dalam dokumen internal.

4. **US-04: Ingatan Percakapan Multi-Turn (Conversation Memory)**
   * **Story**: Sebagai *karyawan biasa*, saya ingin asisten mengingat riwayat pesan dalam sesi percakapan yang sama, supaya saya dapat mengajukan pertanyaan klarifikasi lanjutan tanpa harus mengulang konteks dari awal.
   * **Cara Uji**: Tanyakan "Siapa penanggung jawab persetujuan cuti?", lalu tanyakan "Berapa lama dia harus meresponnya?", verifikasi asisten memahami kata "dia" merujuk pada penanggung jawab persetujuan cuti.

5. **US-05: Ingestion Dokumen Multi-Format (PDF, DOCX, MD)**
   * **Story**: Sebagai *power user*, saya ingin mengunggah dokumen pedoman dengan format PDF, DOCX, dan Markdown, supaya basis pengetahuan asisten dapat diperkaya dengan berbagai tipe dokumen kerja.
   * **Cara Uji**: Unggah berturut-turut satu file PDF, satu file DOCX, dan satu file MD melalui antarmuka upload, verifikasi ketiga file berhasil diparsing dan tercatat di daftar dokumen.

6. **US-06: Generasi Flowchart Alur Kerja Interaktif dan Konteks Antardokumen (GraphView)**
   * **Story**: Sebagai *power user*, saya ingin meminta asisten membuatkan diagram alir proses dari teks prosedur dokumen maupun diagram korelasi konteks antardokumen (1 node per dokumen), supaya rangkaian tahapan birokrasi dan relasi regulasi dapat dipahami secara visual dalam bentuk grafik interaktif.
   * **Cara Uji**: Ketik "Gambarkan flowchart pengajuan cuti dan korelasi regulasinya dengan SK Kementerian", verifikasi asisten memanggil tool visualisasi dan merender komponen diagram berbasis node (GraphView) yang dapat digeser (*drag*) dan dizoom.

7. **US-07: Visualisasi Tabel Menjadi Bar Chart Interaktif**
   * **Story**: Sebagai *power user*, saya ingin mengubah ringkasan data tabel dalam dokumen menjadi grafik batang (bar chart), supaya perbandingan data numerik lebih cepat dipahami dan siap dipresentasikan.
   * **Cara Uji**: Tanyakan "Visualkan tabel evaluasi kinerja dalam bentuk grafik batang", verifikasi asisten mengekstrak baris data tabel dan merender komponen chart web interaktif.

8. **US-08: Filter Dokumen Knowledge Base Tertentu**
   * **Story**: Sebagai *power user*, saya ingin memilih dokumen acuan tertentu saat mengajukan pertanyaan, supaya pencarian jawaban terfokus hanya pada domain atau berkas yang relevan.
   * **Cara Uji**: Pilih filter dokumen "SOP_Keuangan.pdf", ajukan query umum, verifikasi chunk konteks yang digunakan sistem hanya berasal dari berkas tersebut.

9. **US-09: Pencatatan Penggunaan Token dan Estimasi Biaya (Cost Tracking)**
   * **Story**: Sebagai *admin*, saya ingin melihat pencatatan jumlah token input, token output, dan estimasi biaya per percakapan, supaya anggaran pemakaian model AI dapat terpantau secara transparan dan akuntabel.
   * **Cara Uji**: Lakukan satu kali interaksi chat, periksa metadata/panel inspektur respons dan verifikasi terdapat metrik prompt tokens, completion tokens, serta kalkulasi nominal biaya rupiah.

10. **US-10: Manajemen dan Penghapusan Dokumen dari Vector DB**
    * **Story**: Sebagai *admin*, saya ingin menghapus dokumen yang sudah tidak relevan dari sistem, supaya data vektor dokumen lama tersebut bersih dan tidak lagi muncul dalam hasil pencarian jawaban.
    * **Cara Uji**: Hapus salah satu dokumen melalui menu kelola dokumen, ajukan pertanyaan terkait dokumen yang baru dihapus, verifikasi sistem tidak lagi mengambil referensi dari dokumen tersebut.

---

### 4. Non-Goals Eksplisit (Scope Guardrails)
Untuk menjaga agar ruang lingkup proyek tetap fokus, realistis, dan tidak melar (*scope creep*) hingga akhir masa magang, hal-hal berikut secara eksplisit **BUKAN** merupakan tujuan dari produk ini:

1. **Tanpa Antarmuka Suara (No Voice / Speech Processing)**: Sistem tidak menyediakan fitur input pengenalan suara (*Speech-to-Text*) maupun output pembaca suara (*Text-to-Speech*). Seluruh interaksi dibatasi pada teks dan antarmuka web grafis.
2. **Tanpa Multi-Tenancy Kompleks (Single Organization Only)**: Sistem tidak mendukung arsitektur multi-tenant terisolasi untuk banyak perusahaan atau penagihan langganan terpisah; sistem dirancang murni untuk lingkungan internal satu entitas organisasi.
3. **Tanpa Fine-Tuning Model LLM (RAG & In-Context Learning Only)**: Sistem tidak melakukan penyesuaian bobot (*weight fine-tuning*) pada model dasar LLM. Seluruh adaptasi pengetahuan baru dikelola melalui *ingestion pipeline*, *vector indexing*, dan *context prompt engineering*.
4. **Tanpa Aplikasi Mobile Native (Desktop/Web Responsive Focus)**: Tidak ada pengembangan aplikasi mobile berbasis native (iOS/Android menggunakan Swift/Kotlin/Flutter). Antarmuka difokuskan pada web desktop/tablet modern.
5. **Tanpa Eksekusi Perintah Sistem Bebas (No Arbitrary OS/Bash Execution)**: Agent AI tidak memiliki akses untuk menjalankan command shell/terminal bebas di server atau web-scraping tanpa izin di luar internet terbuka. Tool agent dibatasi secara aman pada pengambilan pengetahuan (*retrieval*) dan perenderan komponen visual terdaftar.
6. **Tanpa Kolaborasi Pengeditan Dokumen Real-Time**: Sistem bukan platform authoring dokumen interaktif kolaboratif seperti Google Docs atau Notion. Dokumen yang diunggah bersifat *read-only* untuk dijadikan sumber acuan pengetahuan.

---

## BAGIAN B: Metrik Sukses, Anggaran Token & Biaya

### 1. Tabel 5 Metrik Target & Cara Ukur

| Metrik | Target | Cara Ukur | Sumber Data |
| :--- | :--- | :--- | :--- |
| **Jawaban Tergrounding** | $\ge 80\%$ | (Jumlah jawaban dengan sitasi valid $\div$ 20 soal uji) $\times$ 100% | Set evaluasi 20 soal benchmark (`data/eval/grounding_20.json`) |
| **p95 Time To First Token (TTFT)** | $\le 3\text{ detik (mock)} / \le 6\text{ detik (nyata)}$ | Persentil ke-95 durasi waktu dari pengiriman request chat hingga token respons pertama diterima klien | Tabel `traces` (log telemetri latensi backend) |
| **Rasio Kepuasan Pengguna (👍)** | $\ge 70\%$ | (Total respons bernilai 👍 $\div$ (Total respons 👍 + Total respons 👎)) $\times$ 100% | Tabel `feedback` (database audit interaksi pengguna) |
| **Biaya Rata-Rata per Percakapan** | $\le \text{Rp}500\text{ per sesi}$ | Total akumulasi biaya token (prompt + completion) $\div$ Total sesi percakapan | Tabel `token_usage_logs` (log transaksi token backend) |
| **Cache Hit-Rate Pertanyaan Berulang** | $\ge 20\%$ | (Jumlah request terlayani dari cache $\div$ Total request pertanyaan berulang) $\times$ 100% | Tabel `cache` (telemetri cache hit/miss) |

### 2. Anggaran Token & Kuota Harian

* **Batas Context Window**: $8.192\text{ token (8k)}$ per satu pemanggilan model (mencakup system prompt, chunk dokumen hasil retrieval, dan riwayat percakapan).
* **Maksimum Token Jawaban**: $1.024\text{ token}$ per satu respons keluaran model (*completion limit*).
* **Kuota Harian per Pengguna**: $50\text{ pesan per hari}$, atau batas konsumsi $100.000\text{ token per hari}$ per pengguna.

### 3. Rumus Biaya per 1k Token & Contoh Perhitungan

#### A. Tarif Dasar Model Acuan (OpenAI gpt-4o-mini, Kurs \$1 = Rp16.000)
* Tarif Token Masukan (Prompt): $\$0,00015\text{ per } 1.000\text{ token} = \text{Rp}2,4\text{ per } 1.000\text{ token}$.
* Tarif Token Keluaran (Completion): $\$0,00060\text{ per } 1.000\text{ token} = \text{Rp}9,6\text{ per } 1.000\text{ token}$.

#### B. Rumus Perhitungan Biaya
$$\text{Biaya Pesan (Rp)} = \left( \frac{\text{Token Masukan}}{1.000} \times \text{Tarif Masukan per 1k} \right) + \left( \frac{\text{Token Keluaran}}{1.000} \times \text{Tarif Keluaran per 1k} \right)$$

#### C. Contoh Perhitungan Numerik
1. **Skenario Konsumsi Rata-Rata (1.200 Token Masukan, 300 Token Keluaran)**:
   * Biaya Masukan: $(1.200 \div 1.000) \times \text{Rp}2,4 = \text{Rp}2,88$
   * Biaya Keluaran: $(300 \div 1.000) \times \text{Rp}9,6 = \text{Rp}2,88$
   * **Total Biaya Skenario Rata-Rata**: $\text{Rp}2,88 + \text{Rp}2,88 = \text{Rp}5,76\text{ per pesan}$ (memenuhi target $\le \text{Rp}500$).

2. **Skenario Batas Maksimum (8.000 Token Masukan, 1.024 Token Keluaran)**:
   * Biaya Masukan: $(8.000 \div 1.000) \times \text{Rp}2,4 = \text{Rp}19,20$
   * Biaya Keluaran: $(1.024 \div 1.000) \times \text{Rp}9,6 = \text{Rp}9,83$
   * **Total Biaya Skenario Maksimum**: $\text{Rp}19,20 + \text{Rp}9,83 = \text{Rp}29,03\text{ per pesan}$ (memenuhi target $\le \text{Rp}500$).

---

## BAGIAN C: Arsitektur Scalable & Production-Ready (Clean Architecture Monorepo)

### 1. Diagram Alur Data Satu Jawaban (7 Tahap End-to-End)

Diagram berikut memetakan perjalanan data satu request chat pengguna dari awal hingga akhir dengan arsitektur decoupled berstandar produksi (Next.js 14+ Presentation & FastAPI Backend):

```text
+---------------------------------------------------------------------------------------------------+
|                        ALUR DATA SATU REQUEST JAWABAN (CLEAN ARCHITECTURE RAG)                    |
+---------------------------------------------------------------------------------------------------+

[ Tahap 1: Next.js Presentation & Controllers (Frameworks Layer) ]
  • Pengguna menginput pesan & memilih filter dokumen pada UI Next.js (App Router).
  • ChatController memvalidasi input klien dan menginisiasi request streaming SSE (Server-Sent Events).
  • Mengirimkan HTTP POST ke endpoint backend: /api/v1/chat/stream.
         │
         ▼
[ Tahap 2: Input Guardrail (FastAPI Presentation / Middleware) ]
  • Memvalidasi panjang input (1 s.d. 2.000 karakter), otentikasi sesi pengguna, dan kuota harian.
  • Sanitasi prompt injection, deteksi jailbreak, dan penyaringan PII sebelum masuk ke domain layer.
         │ (Input Lolos Validasi)
         ▼
[ Tahap 3: Router & Intent Classification Use Case (Application Layer) ]
  • RouterUseCase mengklasifikasikan intensi masukan pengguna secara terarah:
    a. Q&A Grounded Dokumen -> Dispatch ke RetrieveKnowledgeUseCase.
    b. Visualisasi Data (Flowchart / Bar Chart / GraphView) -> Dispatch ke GenerateVisualUseCase.
    c. Percakapan Umum / Klarifikasi -> Dispatch langsung ke AgentStreamUseCase.
         │
         ▼
[ Tahap 4: Vector Retrieval & Tool Execution (Infrastructure Layer - pgvector) ]
  • Query di-embed melalui EmbedderService menggunakan model lokal (all-MiniLM-L6-v2).
  • PgVectorRepository mengeksekusi pencarian kemiripan kosinus berindeks HNSW di PostgreSQL on-premise.
  • Mengambil top-k chunk relevan (skor similarity >= 0.7) beserta metadata sitasi dokumen rujukan.
         │ (Konteks & Argumen Tool Terkumpul)
         ▼
[ Tahap 5: LLM Orchestration & Streaming (Domain & Infrastructure Adapters) ]
  • AgentUseCase menyusun System Prompt ter-grounding + riwayat percakapan (maks 8k) + chunk dokumen.
  • ILLMProvider mengeksekusi inferensi model (dukungan Real Provider API dan Mock Provider untuk demo).
  • Menghasilkan aliran token respons secara asinkron (maksimum 1.024 token jawaban).
         │
         ▼
[ Tahap 6: Output & Grounding Validation (Domain Business Rules) ]
  • GroundingValidator memverifikasi keberadaan dan keabsahan sitasi dokumen rujukan ([1], [2]).
  • Validasi schema JSON untuk payload visualisasi interaktif (GraphView / BarChart).
  • Penerapan threshold: Jika skor similarity < 0.7, paksa respons fallback "informasi tidak ditemukan".
         │ (Output Terverifikasi)
         ▼
[ Tahap 7: Tracing, Cost Accounting, & SSE Push to Next.js Presenter ]
  • TracerService mencatat metrik latensi p95 TTFT, konsumsi token, dan estimasi biaya ke PostgreSQL.
  • FastAPI memancarkan stream Server-Sent Events (SSE) ke frontend Next.js.
  • Next.js ChatPresenter memformat payload dan merender teks streaming beserta komponen visual interaktif.
```

---

### 2. Lima Architecture Decision Records (ADR) Singkat

#### ADR-01: Monorepo Decoupled dengan Pola Clean Architecture (Next.js & FastAPI)
**Konteks**: Dibutuhkan arsitektur proyek enterprise yang modular, scalable, dan siap pakai langsung di proyek aktual perusahaan, dengan pemisahan tegas antara antarmuka pengguna interaktif dan orkestrasi AI. **Keputusan**: Mengadopsi struktur monorepo dengan frontend Next.js (TypeScript) dan backend FastAPI (Python asynchronous), keduanya menerapkan pola Clean Architecture (*Domain, Application, Infrastructure, Presentation/Adapters*). **Konsekuensi**: Arsitektur sangat modular, bebas ketergantungan erat ke framework (*framework-independent*), mudah diuji (*testable*), dan siap dideploy sebagai container terpisah, namun memerlukan disiplin tim dalam menjaga batasan antar layer (misal via lint boundaries / dependency injection).

#### ADR-02: PostgreSQL On-Premise sebagai Single Unified Database
**Konteks**: Sistem enterprise membutuhkan penyimpanan persisten untuk master dokumen, metadata chunk, riwayat sesi percakapan, audit telemetri, dan logging biaya pada satu infrastruktur on-premise yang aman tanpa server database pihak ketiga yang terpisah-pisah. **Keputusan**: Menggunakan PostgreSQL on-premise sebagai satu-satunya sistem basis data terpusat aplikasi. **Konsekuensi**: Menjamin integritas transaksional ACID secara terpadu, keamanan data on-premise terjamin penuh, dan proses backup terpusat, namun membutuhkan konfigurasi connection pooling (PgBouncer/SQLAlchemy async connection pool) yang terukur pada beban konkurensi tinggi.

#### ADR-03: Ekstensi `pgvector` dengan Indeks HNSW untuk Vector Store Terintegrasi
**Konteks**: Penggunaan vector database terpisah (seperti Chroma/Qdrant standalone) menambah beban operasional, risiko kegagalan sinkronisasi metadata dokumen, dan latensi jaringan antar-service. **Keputusan**: Mengaktifkan ekstensi `pgvector` pada PostgreSQL on-premise dengan indeks HNSW (*Hierarchical Navigable Small World*) untuk penyimpanan dan pencarian vektor embedding dokumen. **Konsekuensi**: Mengizinkan query relasional dan pencarian kemiripan vektor dilakukan dalam satu transaksi SQL (`JOIN` antara tabel chunk dan master dokumen untuk korelasi regulasi), menyederhanakan arsitektur, namun memerlukan alokasi RAM yang cukup untuk pemeliharaan indeks HNSW di database server.

#### ADR-04: Tracing Telemetri Mandiri ke Tabel PostgreSQL Terindeks Alih-alih SaaS
**Konteks**: Pengukuran latensi p95 Time To First Token (TTFT), pemakaian token, dan audit eksekusi RAG harus terpantau transparan tanpa biaya langganan SaaS eksternal (LangSmith/Datadog) dan tanpa risiko kebocoran data internal perusahaan keluar. **Keputusan**: Mengembangkan modul *in-house tracing* pada layer infrastruktur backend yang mencatat data waktu eksekusi, metadata token, dan biaya langsung ke tabel `traces` di PostgreSQL secara asynchronous. **Konsekuensi**: Biaya infrastruktur tracing Rp0, privasi data on-premise 100% terjaga, dan data telemetri dapat di-query langsung via SQL, namun antarmuka pelaporan performa perlu dibangun secara internal pada UI aplikasi.

#### ADR-05: Mock Provider Wajib di Samping Real Provider (OpenAI/Ollama)
**Konteks**: Pengujian otomatis (CI/CD), demonstrasi akhir, dan proses evaluasi benchmark 20 soal rawan terganggu apabila kuota API LLM komersial habis, latensi jaringan publik lambat, atau koneksi eksternal terputus. **Keputusan**: Mewajibkan implementasi abstraksi antarmuka `ILLMProvider` pada layer domain/interfaces dengan dukungan *Mock Provider* deterministik yang dapat diaktifkan melalui konfigurasi lingkungan (*toggle config*). **Konsekuensi**: Pipeline pengujian otomatis dan demo interaktif dijamin 100% selalu berfungsi stabil tanpa biaya API dan tanpa ketergantungan internet, namun respon mock terbatas pada skenario terprogram sehingga pengujian eksploratif tetap memerlukan Real Provider.

---

### 3. Struktur Folder Monorepo Final Berbasis Clean Architecture

Struktur folder ini mengunci pembagian modul teknis monorepo sesuai standar Clean Architecture di backend FastAPI dan frontend Next.js 14+:

```text
ai-assistant-prototype/
├── backend/                           # Backend FastAPI Latest (Clean Architecture)
│   ├── app/
│   │   ├── domain/                    # Layer 1: Entities & Domain Logic (Pure Python)
│   │   │   ├── entities/              # Document, Chunk, Message, Session, Trace, Cost
│   │   │   └── errors.py              # Custom domain exceptions
│   │   ├── application/               # Layer 2: Use Cases & Interfaces/Contracts
│   │   │   ├── use_cases/
│   │   │   │   ├── chat_stream.py     # Use case orkestrasi chat & agent loop
│   │   │   │   ├── ingest_doc.py      # Use case parsing & vectorization dokumen
│   │   │   │   ├── retrieve_rag.py    # Use case retrieval RAG ber-threshold
│   │   │   │   └── generate_visual.py # Use case pembuatan visual GraphView & chart
│   │   │   └── interfaces/            # Abstract contracts (Repositories, Services, LLM)
│   │   ├── infrastructure/            # Layer 3: Concrete Implementations & Adapters
│   │   │   ├── db/
│   │   │   │   ├── session.py         # PostgreSQL connection pool & SQLAlchemy engine
│   │   │   │   └── repositories/      # PgVectorRepo, DocumentRepo, TraceRepo
│   │   │   ├── parsers/               # PyMuPDF, python-docx, markdown-it
│   │   │   ├── embeddings/            # Sentence-Transformers all-MiniLM-L6-v2
│   │   │   └── llm/                   # RealLLMAdapter & MockLLMAdapter
│   │   ├── presentation/              # Layer 4: Frameworks & Drivers (FastAPI)
│   │   │   ├── api/v1/
│   │   │   │   ├── endpoints/         # /chat/stream, /documents, /traces
│   │   │   │   └── router.py          # API router setup
│   │   │   ├── schemas/               # Pydantic v2 DTOs (Request/Response)
│   │   │   └── middlewares/           # Guardrail & CORS middlewares
│   │   ├── config.py                  # Environment settings & configuration
│   │   └── main.py                    # FastAPI entrypoint
│   ├── tests/                         # Unit & integration tests backend
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                          # Frontend Next.js Latest (Clean Architecture)
│   ├── src/
│   │   ├── entities/                  # Layer 1: Domain Models (Message, Document, Citation, Visual)
│   │   ├── application/               # Layer 2: Use Cases & Service Contracts
│   │   │   ├── use_cases/             # sendMessageUseCase, uploadDocumentUseCase
│   │   │   └── contracts/             # IChatService, IDocumentService
│   │   ├── interface-adapters/        # Layer 3: Controllers & Presenters
│   │   │   ├── controllers/           # ChatController, DocumentController
│   │   │   └── presenters/            # ChatPresenter, VisualPresenter
│   │   ├── infrastructure/            # Layer 4: Concrete Implementations (SSE client, HTTP API)
│   │   └── di/                        # Inversion of Control (IoC) Dependency Injection
│   ├── app/                           # Next.js Framework & UI Layer (App Router)
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # Main chat & interactive visual interface
│   │   └── documents/page.tsx         # Document management interface
│   ├── components/                    # Reusable UI Components
│   │   ├── ChatContainer.tsx          # Chat thread & message stream display
│   │   ├── GraphView.tsx              # Interactive DOM node/flowchart visualizer
│   │   ├── ChartRenderer.tsx          # Interactive bar/line chart renderer
│   │   ├── DocumentUploader.tsx       # Drag-and-drop document uploader
│   │   └── CitationBadge.tsx          # Interactive citation popup [1]
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docs/
│   └── internship/01-template-prd.md  # Dokumen PRD utama
└── README.md
```

---

## BAGIAN D: Rencana Rilis & Kriteria Uji Verifikasi *(Roadmap Sprint)*

* **Sprint 0 — PRD & Kerangka**
* **Sprint 1 — Chat, Sesi & Token**
* **Sprint 2 — RAG, Tool & Router**
* **Sprint 3 — Guardrail**
* **Sprint 4 — Observability**
* **Sprint 5 — Performa & Rilis**
