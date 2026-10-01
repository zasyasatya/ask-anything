# Dokumen Evaluasi Teknis: Kandidat Design System Frontend

* **Kode Dokumen**: `DOCS-FE-001`
* **Status**: `Draf Rekomendasi (Menunggu Keputusan Tech Lead)`
* **Author / Assignee**: `verisimb`
* **Target Modul**: `frontend/` (Next.js 14 Clean Architecture)

---

## 1. Latar Belakang & Kebutuhan Antarmuka

Menindaklanjuti arahan Tech Lead untuk menyiapkan kandidat design system bagi implementasi antarmuka pengguna frontend, dokumen ini menyajikan perbandingan faktual berbasis riset terhadap pustaka antarmuka AI-Native yang relevan dengan spesifikasi PRD AI Assistant & RAG Agent.

Kebutuhan antarmuka inti yang harus didukung oleh design system:
1. **Status Alur Agen (Agent Reasoning & Activity)**: Menampilkan visualisasi saat model sedang memproses (*thinking/shimmering*), tahapan perencanaan (*todo/steps*), dan eksekusi alat (*tool calling*).
2. **Keluaran Terstruktur & Sitasi**: Penanda sitasi rujukan dokumen ([1], [2]), drawer rujukan sumber (*sources*), dan tampilan hasil eksekusi tool yang dapat dilipat (*collapsible*).
3. **Kompatibilitas Arsitektur**: Kompatibel dengan Next.js 14 App Router, Tailwind CSS, dan pola Clean Architecture tanpa menimbulkan isu hidrasi atau overhead runtime CSS-in-JS.
4. **Dukungan Tema**: Dukungan terintegrasi untuk mode terang (*light*) dan mode gelap (*dark*).

---

## 2. Analisis Faktual Kandidat Design System

Berdasarkan penelusuran terhadap sumber resmi masing-masing pustaka, berikut adalah data temuan faktual:

### Kandidat 1: beUI — Agents Components (Pilihan Utama yang Direkomendasikan)
* **Sumber URL**: `https://beui.dev/components/agents`
* **Definisi**: Pustaka komponen React dan Next.js sumber terbuka yang dirancang khusus untuk memvisualisasikan penalaran agen (*agent reasoning*), progres, aktivitas pemanggilan alat (*tool activity*), dan status percakapan.
* **Teknologi**: React, Next.js, Motion / Animasi.
* **Katalog Komponen (17 Modul Spesifik Agen)**:
  * **Status & Berpikir (Thinking & Status)**: *Agent Loading States* (teks shimmering, indikator real-time, dan frasa penalaran berulang / *cycling reasoning phrases*).
  * **Perencanaan & Langkah (Steps & Planning)**: *Todo List* (agenda bertahap yang dapat dilipat, transformasi status, dan penghitung progres).
  * **Pemanggilan Alat & Jejak Eksekusi (Tool Calls & Execution Traces)**: *Agent Activity* (umpan terpadu untuk penalaran, pencarian dokumen, panggilan alat, jejak eksekusi terstruktur) dan *Tool Result* (tampilan keluaran perintah dan respons yang dapat diciutkan).
  * **Human-in-the-Loop**: *Tool Approval* (kontrol untuk mengizinkan, mengingat, atau memblokir eksekusi alat) dan *Approval Card* (kartu keputusan evaluasi multi-tahap).
  * **Dialog & Output**: *Prompt Input*, *Message*, *Message Bubble*, *Message Scroller*, *Streaming Response*, *Citations*, *Code Block*, *File Diff*, *AI Sidebar*, dan *Chat App*.
* **Evaluasi**:
  * Merupakan **opsi yang paling disukai / preferensi utama** untuk antarmuka pengguna proyek ini karena kualitas visual tinggi, transisi gerak halus, dan fokus mendalam pada komponen representasi aktivitas agen yang langsung menjawab kebutuhan interaksi RAG/Agent.

---

### Kandidat 2: Shadcn AI Elements
* **Sumber URL**: `https://elements.ai-sdk.dev/`
* **Definisi**: Pustaka komponen dan custom registry yang dibangun langsung di atas konvensi **shadcn/ui** untuk mempercepat pembangunan aplikasi AI-native.
* **Teknologi**: Next.js, shadcn/ui, Tailwind CSS, terintegrasi mendalam dengan Vercel AI SDK.
* **Katalog Komponen**:
  * **Chatbot**: *Prompt Input*, *Model Selector*, *Reasoning*, *Chain of Thought*, *Tool*, *Inline Citation*, *Sources*, *Message*, *Conversation*, *Attachments*, *Checkpoint*, *Confirmation*, *Context*, *Plan*, *Queue*, *Shimmer*, *Suggestion*, *Task*.
  * **Kode & Artefak**: *Agent*, *Artifact*, *Code Block*, *Commit*, *Environment Variables*, *File Tree*, *JSX Preview*, *Package Info*, *Sandbox*, *Schema Display*, *Snippet*, *Stack Trace*, *Terminal*, *Test Results*, *Web Preview*.
  * **Alur Kerja (Workflow / Canvas)**: *Canvas*, *Connection*, *Controls*, *Edge*, *Node*, *Panel*, *Toolbar*.
* **Evaluasi**:
  * Memiliki cakupan katalog komponen terluas dan terlengkap untuk ekosistem shadcn/ui. Sangat kuat pada komponen pendukung seperti *Inline Citation*, *Sources Drawer*, dan komponen grafik berbasis *Node/Canvas* (relevan untuk visualisasi korelasi antardokumen pada PRD US-06).

---

### Kandidat 3: AICSS
* **Sumber URL**: `https://www.aicss.dev/`
* **Definisi**: Pustaka blok antarmuka komponen siap salin (*copy-paste*) untuk agen AI yang berfokus menampilkan elemen saat agen memproses di tengah percakapan.
* **Teknologi**: Mendukung React, Vue, dan Svelte.
* **Katalog Komponen**: Indikator penalaran (*reasoning*), eksekusi alat (*tool execution*), pembentukan teks langsung (*live text generation*), tampilan data terstruktur, dan kartu persetujuan pengguna (*user approval cards*).
* **Evaluasi**:
  * Alternatif fungsional untuk visualisasi proses tengah percakapan, namun sebagian komponen tingkat lanjut memerlukan lisensi berbayar dan pendekatannya lintas-framework sehingga kurang dioptimasi khusus untuk Next.js.

---

### Kandidat 4: Beautiful UI
* **Sumber URL**: `https://www.beautifului.dev/`
* **Definisi**: Koleksi komponen web modern berbasis React dan Tailwind CSS untuk tampilan antarmuka web umum.
* **Evaluasi**:
  * Bagus sebagai referensi penataan layout umum, kartu informasi, dan tombol navigasi, namun tidak menyediakan blok logika spesifik untuk streaming token LLM, pelacakan proses agen, maupun sitasi dokumen.

---

## 3. Matriks Perbandingan Fitur

| Kriteria Evaluasi | beUI (beui.dev) | Shadcn AI Elements | AICSS (aicss.dev) | Beautiful UI |
| :--- | :---: | :---: | :---: | :---: |
| **Fokus Desain Agen (Agent Activity & Tool Calling)** | Sangat Tinggi (17 modul) | Tinggi | Sedang-Tinggi | Rendah (General UI) |
| **Kualitas Visual & Animasi (Micro-Interactions)** | Unggul / Paling Halus | Standar / Bersih | Standar | Rapi |
| **Komponen Sitasi Dokumen (RAG Citations)** | Tersedia | Lengkap (*Inline + Sources*) | Terbatas | Tidak Ada |
| **Komponen Visualisasi Node / Flowchart** | Tersedia (Activity Feed) | Lengkap (*Canvas/Node/Edge*) | Terbatas | Tidak Ada |
| **Integrasi Shadcn / Tailwind / Next.js 14** | Native Next.js & React | Native Shadcn Registry | Multi-framework | Native Tailwind |
| **Status Lisensi** | Sumber Terbuka | Sumber Terbuka | Parsial (Sebagian Pro) | Sumber Terbuka |

---

## 4. Kesimpulan & Rekomendasi Implementasi

Berdasarkan hasil evaluasi faktual di atas:

1. **Arah Desain Utama (User Preferred Direction)**:
   * Menggunakan **`beUI (https://beui.dev/components/agents)`** sebagai acuan utama pengalaman antarmuka (*look-and-feel*), khususnya pada:
     * *Agent Loading States* (tampilan teks berbayang / shimmering saat model melakukan reasoning).
     * *Agent Activity & Tool Result* (kartu pelacakan proses alat yang terstruktur dan rapi).
     * *Message & Dialogue bubbles* dengan interaksi yang mulus dan modern.

2. **Dukungan Fungsional RAG Tambahan**:
   * Komponen sitasi rujukan dokumen (*Inline Citation* dan *Sources Drawer*) serta visualisasi simpul relasi dokumen (*Canvas/Node*) dapat mengadopsi spesifikasi modular dari **Shadcn AI Elements** yang selaras dengan komponen shadcn dasar yang sudah terpasang pada proyek.
