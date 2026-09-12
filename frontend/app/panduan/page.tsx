import type { Metadata } from "next";
import {
  C,
  Code,
  DocShell,
  H2,
  H3,
  Note,
  OL,
  P,
  Shot,
  Table,
  UL,
} from "@/components/docs/DocShell";

export const metadata: Metadata = {
  title: "Panduan Pengguna — Ask Anything",
  description:
    "Tata cara lengkap memakai Ask Anything: chat agentic, browsing, diagram, Mechanistic Interpreter, riwayat, dan settings — dengan screenshot aplikasi asli.",
};

const TOC: Array<[string, string]> = [
  ["mulai", "Mulai dalam 1 menit"],
  ["layar", "Mengenal layar utama"],
  ["chat", "Chat pertama Anda"],
  ["jawaban", "Membaca jawaban agent"],
  ["browsing", "Browsing & penanganan error"],
  ["interpreter", "Mechanistic Interpreter"],
  ["riwayat", "Riwayat percakapan"],
  ["settings", "Settings provider"],
  ["tampilan", "Tampilan, aksen & mobile"],
  ["materi", "Materi belajar lanjutan"],
  ["tips", "Tips prompt yang efektif"],
  ["troubleshoot", "Troubleshooting"],
  ["privasi", "Data & privasi"],
];

export default function PanduanPage() {
  return (
    <DocShell
      active="panduan"
      title="Panduan Pengguna"
      subtitle="Semua yang perlu Anda ketahui untuk memakai Ask Anything sehari-hari — disertai screenshot aplikasi sungguhan (di-generate otomatis dari UI yang berjalan, bukan mockup)."
      toc={TOC}
    >
      <section className="space-y-4">
        <H2 id="mulai">1. Mulai dalam 1 menit</H2>
        <P>
          Ask Anything adalah chatbot AI <b>agentic</b>: ia tidak hanya menjawab dari memori, tetapi
          bisa mencari di web, mengambil isi halaman, menghitung, dan menggambar diagram — sambil
          memperlihatkan seluruh proses berpikirnya. Jalankan dengan satu perintah:
        </P>
        <Code>{`# Linux / macOS
python3 run.py            # atau: ./run.sh

# Windows
run.bat

# Mode demo tanpa GPU / tanpa download model
python3 run.py --demo

# Model GGUF asli dari HuggingFace (butuh llama.cpp)
python3 run.py --gguf ~/models/qwen3-8b-q4_k_m.gguf`}</Code>
        <UL
          items={[
            <>UI terbuka di <C>http://localhost:3000</C>, dokumentasi API di <C>http://localhost:8000/docs</C>.</>,
            <>Launcher menampilkan checklist dependensi (<C>python</C>, <C>node</C>, <C>npm</C>, backend, frontend) dan status server LLM.</>,
            <>Prasyarat: Python ≥ 3.10 dan Node ≥ 18. Sisanya diurus launcher.</>,
          ]}
        />
        <Note>
          Tidak punya server LLM lokal? Pilih <b>mode mock</b> dari banner peringatan (lihat bagian{" "}
          <a className="underline" href="#settings">Settings</a>) — seluruh fitur UI, termasuk
          Mechanistic Interpreter, tetap bisa dicoba offline.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="layar">2. Mengenal layar utama</H2>
        <Shot
          src="/docs-images/01-hero-landing.png"
          alt="Layar awal Ask Anything"
          caption="Layar awal: sidebar riwayat (kiri), header status (atas), composer pertanyaan (tengah), chip contoh prompt, dan galeri Explore."
        />
        <UL
          items={[
            <>
              <b>Sidebar kiri</b> — tombol <C>New chat</C>, daftar riwayat percakapan dikelompokkan
              per tanggal (<C>Today</C>, <C>Yesterday</C>, …), indikator status LLM, dan tombol{" "}
              <C>Settings provider</C>.
            </>,
            <>
              <b>Header</b> — judul percakapan aktif, chip provider+model yang sedang dipakai
              (mis. <C>huggingface · Qwen/Qwen3-8B-GGUF</C>), tautan <C>Docs &amp; Slides</C>, dan
              tombol <C>Mechanistic Interpreter →</C>.
            </>,
            <>
              <b>Composer</b> — kotak tempat Anda menulis pertanyaan; kirim dengan tombol <C>Ask</C>{" "}
              atau tekan <C>Enter</C> (<C>Shift+Enter</C> untuk baris baru).
            </>,
            <>
              <b>Chip contoh</b> &amp; galeri <b>Explore</b> — klik untuk mengisi composer dengan
              prompt siap pakai per kategori (Browsing / Diagram / Tools).
            </>,
          ]}
        />
        <Shot
          src="/docs-images/02-hero-explore.png"
          alt="Galeri Explore"
          caption="Galeri Explore berisi prompt contoh berkelompok tab: All, Browsing, Diagram, Tools. Klik kartu untuk memakai promptnya."
        />
      </section>

      <section className="space-y-4">
        <H2 id="chat">3. Chat pertama Anda</H2>
        <OL
          items={[
            <>Klik chip contoh (mis. <C>Diagram alir →</C>) atau ketik pertanyaan sendiri di composer.</>,
            <>Periksa baris bawah composer: badge <C>4 tools</C> menunjukkan tool yang aktif untuk agent, dan titik warna adalah pilihan aksen tampilan.</>,
            <>Tekan <C>Enter</C> / tombol <C>Ask</C>. Tombol berubah menjadi <C>Thinking…</C> selama agent bekerja.</>,
            <>Jawaban muncul bertahap (streaming). Panel Mechanistic Interpreter otomatis terbuka memperlihatkan prosesnya.</>,
          ]}
        />
        <Shot
          src="/docs-images/03-composer-filled.png"
          alt="Composer terisi prompt contoh"
          caption="Composer terisi prompt contoh setelah klik chip. Badge '4 tools' = web_search, fetch_url, create_diagram, calculator."
        />
        <Shot
          src="/docs-images/04-chat-diagram-interpreter.png"
          alt="Chat dengan diagram mermaid dan interpreter"
          caption="Hasil permintaan diagram: chip tool create_diagram ✓, jawaban teks, diagram Mermaid yang dirender live, dan panel Interpreter (kanan) yang merekam seluruh event."
        />
      </section>

      <section className="space-y-4">
        <H2 id="jawaban">4. Membaca jawaban agent</H2>
        <P>Satu balasan agent bisa memuat beberapa lapisan informasi:</P>
        <Table
          head={["Elemen UI", "Artinya"]}
          rows={[
            [
              <C>💭 kotak thinking</C>,
              "Reasoning mentah model sebelum memutuskan langkah (muncul saat streaming).",
            ],
            [
              <>Chip tool, mis. <C>create_diagram ✓</C></>,
              "Agent memanggil tool tersebut; ✓ berarti selesai. Arahkan kursor untuk melihat ringkasan hasilnya.",
            ],
            [
              <>Kartu <C>mermaid diagram</C></>,
              "Diagram alir / graph / mindmap yang dirender live dari kode Mermaid hasil tool.",
            ],
            [
              <>Teks markdown</>,
              "Jawaban final: daftar, tabel, tautan sumber, dan blok kode dirender otomatis.",
            ],
          ]}
        />
        <Shot
          src="/docs-images/10-chat-calculator.png"
          alt="Percakapan kalkulator"
          caption="Contoh tool calculator: argumen ekspresi dikirim ke tool, hasilnya (132) dikutip agent di jawaban final."
        />
      </section>

      <section className="space-y-4">
        <H2 id="browsing">5. Browsing &amp; penanganan error</H2>
        <P>
          Untuk informasi terkini agent memanggil <C>web_search</C> (DuckDuckGo lite tanpa API key;
          Serper/Tavily opsional) dan bisa melanjutkan dengan <C>fetch_url</C> untuk membaca satu
          halaman penuh. Bila jaringan gagal, error <b>tidak</b> mematikan percakapan: status error
          diberikan ke model sebagai data, dan model menjawab jujur menyebutkan kegagalannya.
        </P>
        <Shot
          src="/docs-images/09-chat-browsing-error.png"
          alt="Tool web_search gagal jaringan ditangani graceful"
          caption="Contoh graceful degradation: tool web_search gagal (lingkungan offline), error tampil sebagai tool_result, dan agent tetap merangkum dengan menyebutkan keterbatasannya."
        />
      </section>

      <section className="space-y-4">
        <H2 id="interpreter">6. Mechanistic Interpreter</H2>
        <P>
          Panel kanan (tombol <C>Mechanistic Interpreter →</C>) adalah pembeda utama aplikasi ini:
          semua yang dilakukan LLM &amp; agent terekam per-event dan bisa direplay dari riwayat.
          Empat tabnya:
        </P>
        <Table
          head={["Tab", "Isi", "Kapan dipakai"]}
          rows={[
            ["Timeline", "Urutan event meta → thinking → tool_call → tool_result → … → done; tiap baris bisa dibentangkan menjadi JSON mentah.", "Memeriksa langkah agent & argumen tool."],
            ["Prompt", "Prompt assembly persis seperti dikirim ke LLM: system prompt, messages, daftar tools.", "Debug kenapa model berperilaku tertentu."],
            ["Tokens", "Logprobs streaming per token: token terpilih, bar probabilitas, dan alternatif teratas.", "Melihat keyakinan model per token."],
            ["Metrics", "Provider/model, temperature, jumlah steps, latensi, token usage, jumlah event & error.", "Mengukur performa satu run."],
          ]}
        />
        <Shot
          src="/docs-images/05-interpreter-timeline-expanded.png"
          alt="Tab Timeline dengan event dibentangkan"
          caption="Tab Timeline: baris event dibentangkan menampilkan JSON mentah (argumen tool_call, isi tool_result, dll)."
        />
        <Shot
          src="/docs-images/06-interpreter-prompt.png"
          alt="Tab Prompt"
          caption="Tab Prompt: system prompt + messages + schema tools persis seperti yang diterima LLM."
        />
        <Shot
          src="/docs-images/07-interpreter-tokens.png"
          alt="Tab Tokens"
          caption="Tab Tokens: logprobs per token dengan bar probabilitas dan alternatif (tersedia bila provider mendukung, mis. llama.cpp)."
        />
        <Shot
          src="/docs-images/08-interpreter-metrics.png"
          alt="Tab Metrics"
          caption="Tab Metrics: ringkasan run — provider, model, temperature, steps, latensi, dan usage token."
        />
      </section>

      <section className="space-y-4">
        <H2 id="riwayat">7. Riwayat percakapan</H2>
        <P>
          Setiap percakapan tersimpan otomatis di SQLite lokal beserta seluruh trace event-nya.
          Klik judul di sidebar untuk membuka kembali pesan <b>dan</b> replay Interpreter-nya
          (Timeline, Prompt, Tokens, Metrics tetap lengkap).
        </P>
        <Shot
          src="/docs-images/13-sidebar-history.png"
          alt="Sidebar riwayat percakapan"
          caption="Sidebar: riwayat dikelompokkan per tanggal (Today / Yesterday / …), indikator 'LLM server terhubung', dan tombol Settings provider."
        />
      </section>

      <section className="space-y-4">
        <H2 id="settings">8. Settings provider</H2>
        <P>
          Tombol <C>Settings provider</C> (bawah sidebar) membuka dialog pemilihan LLM: provider{" "}
          <C>huggingface</C> (server lokal OpenAI-compatible, mis. llama.cpp), <C>openai</C> (API
          key), atau <C>mock</C> (demo offline deterministik). Base URL, model, dan temperature
          bisa diubah runtime tanpa restart.
        </P>
        <Shot
          src="/docs-images/11-settings-provider.png"
          alt="Dialog settings provider"
          caption="Dialog Settings provider: pilihan provider, base URL, model, dan slider temperature."
        />
        <Shot
          src="/docs-images/12-banner-llm-offline.png"
          alt="Banner LLM offline"
          caption="Bila provider huggingface dipilih tetapi server lokal tidak terjangkau, banner kuning muncul dengan tombol sekali-klik 'Pakai mode mock'."
        />
      </section>

      <section className="space-y-4">
        <H2 id="tampilan">9. Tampilan, aksen &amp; mobile</H2>
        <P>
          Empat aksen warna (indigo, violet, orange, zinc) tersedia di composer — klik titik warna
          untuk mengganti seluruh aksen UI secara instan. Layout responsif hingga layar ponsel.
        </P>
        <Shot
          src="/docs-images/16-accent-orange.png"
          alt="Aksen oranye"
          caption="Aksen orange: tombol, chip, dan ring mengikuti variabel aksen yang dipilih."
        />
        <Shot
          src="/docs-images/15-mobile-hero.png"
          alt="Tampilan mobile"
          caption="Tampilan mobile (390×844): sidebar disembunyikan, composer dan Explore tetap nyaman dipakai."
        />
      </section>

      <section className="space-y-4">
        <H2 id="materi">10. Materi belajar lanjutan</H2>
        <P>
          Ingin memahami cara kerja agent secara mendalam? Buka slide interaktif{" "}
          <C>Docs &amp; Slides →</C> di header (atau <C>/slides/slides-cara-kerja.html</C>,
          navigasi <C>←</C>/<C>→</C>) dan dokumen metodologi di repo{" "}
          <C>docs/METODOLOGI.md</C>. Untuk developer, baca{" "}
          <a className="underline" href="/developer">Docs Developer</a>.
        </P>
        <Shot
          src="/docs-images/14-slides-cara-kerja.png"
          alt="Slide cara kerja agent"
          caption="Slide interaktif 'cara kerja agent' disajikan oleh backend di /slides dan diproxy frontend."
        />
      </section>

      <section className="space-y-4">
        <H2 id="tips">11. Tips prompt yang efektif</H2>
        <UL
          items={[
            <>Sebutkan kata kunci kemampuan: <C>cari/berita</C> memicu browsing, <C>diagram/alur/graph/mindmap</C> memicu pembuatan diagram, <C>hitung</C> memicu calculator.</>,
            <>Minta sumber: “lengkap dengan link sumber” membuat agent menyertakan URL hasil search.</>,
            <>Untuk diagram relasi, sebutkan node-nya: “graph relasi antar microservice: gateway, auth, billing…”.</>,
            <>Gabungkan: “Jelaskan cara kerja DNS lalu buat diagram alurnya” — penjelasan + visual dalam satu run.</>,
            <>Lanjutkan percakapan untuk memperbaiki diagram: riwayat dikirim sebagai konteks langkah berikutnya.</>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="troubleshoot">12. Troubleshooting</H2>
        <Table
          head={["Gejala", "Penyebab umum", "Solusi"]}
          rows={[
            ["Banner kuning 'LLM lokal tidak terjangkau'", "Server llama.cpp belum jalan di port 8081.", "Jalankan llama-server / run.py --demo, atau klik 'Pakai mode mock'."],
            ["Indikator sidebar merah 'LLM server offline'", "Base URL provider tidak reachable.", "Periksa Settings provider → base URL; atau ganti provider."],
            ["Tool web_search berstatus error", "Tidak ada akses internet / backend diblokir jaringan.", "Normal di lingkungan offline; agent tetap menjawab dengan menyebut error. Konfigurasi Serper/Tavily bila punya key."],
            ["Tab Tokens kosong", "Provider tidak mengirim logprobs (mis. OpenAI API default).", "Pakai llama.cpp lokal atau mode mock untuk melihat logprobs."],
            ["Diagram tidak muncul", "Model tidak emit Mermaid valid.", "Ulangi dengan prompt eksplisit 'diagram alir'; validasi server-side menolak Mermaid rusak dan memberikannya kembali ke model."],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="privasi">13. Data &amp; privasi</H2>
        <UL
          items={[
            <>Semua percakapan & trace tersimpan lokal di SQLite (<C>data/ask_anything.db</C>, bisa diubah via <C>ASK_DB_PATH</C>).</>,
            <>Tidak ada telemetri dari aplikasi; permintaan LLM hanya menuju provider yang Anda pilih.</>,
            <>Hapus riwayat: DELETE <C>/api/conversations/&#123;id&#125;</C> atau hapus file DB saat aplikasi mati.</>,
          ]}
        />
        <H3>Catatan screenshot</H3>
        <P>
          Seluruh gambar di halaman ini adalah screenshot aplikasi yang benar-benar berjalan
          (backend + frontend + LLM demo), diambil otomatis lewat{" "}
          <C>scripts/capture_screenshots.py</C> (Playwright/Chromium) sehingga dokumen tidak pernah
          kedaluwarsa secara diam-diam: jalankan ulang scriptnya setiap UI berubah.
        </P>
      </section>
    </DocShell>
  );
}
