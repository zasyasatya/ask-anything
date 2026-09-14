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
  ["tata-letak", "Navbar collapsible & ruang lega"],
  ["chat", "Chat pertama Anda"],
  ["jawaban", "Provenance & sitasi"],
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

# Cari model di HuggingFace
python3 run.py --search qwen3

# Unduh model ke ./models + pasang torch/transformers + jadikan aktif
python3 run.py --model Qwen/Qwen3-1.7B

# Mode demo tanpa download model (server OpenAI-compatible tiruan)
python3 run.py --demo`}</Code>
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
              <b>Navbar kiri</b> — bisa <b>di-collapse</b> jadi rail ikon (64px) atau
              <b>di-expand</b> (268px) lewat tombol <C>‹</C> atau <C>Ctrl/Cmd+B</C>; berisi{' '}
              <C>New chat</C>, riwayat per tanggal (<C>Today</C>, <C>Yesterday</C>, …),
              indikator status LLM, dan <C>Settings provider</C>. Pilihan Anda tersimpan.
            </>,
            <>
              <b>Header</b> — judul percakapan aktif, chip provider+model yang sedang dipakai
              (mis. <C>huggingface · Qwen/Qwen3-1.7B</C>), tautan <C>Docs &amp; Slides</C>, dan
              tombol <C>Mechanistic Interpreter →</C>.
            </>,
            <>
              <b>Ruang chat</b> — kolom percakapan <b>lebar</b> (maks 1180px + padding longgar)
              yang otomatis memanfaatkan ruang saat navbar di-collapse.
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
        <H2 id="tata-letak">3. Navbar collapsible &amp; ruang chat lega</H2>
        <P>
          Navbar kiri bisa diperkecil jadi <b>rail ikon 64px</b> atau dibuka penuh{' '}
          <b>268px</b> — lewat tombol <C>‹</C> di kepalanya atau pintasan{' '}
          <C>Ctrl+B</C> (<C>Cmd+B</C> di macOS). Ruang yang dilepaskan langsung dipakai
          ulang oleh ruang chat dan kanvas diagram. Keadaannya disimpan di
          <C>localStorage</C>, jadi bertahan setelah refresh.
        </P>
        <Shot
          src="/docs-images/19-sidebar-collapsed.png"
          alt="Navbar dalam keadaan collapsed"
          caption="Navbar collapsed: merek, New chat, riwayat sebagai rail titik (judul muncul sebagai tooltip dan tetap bisa dipilih dengan keyboard), status LLM, dan Settings sebagai ikon."
        />
        <Table
          head={["Layout", "Kapan enak dipakai"]}
          rows={[
            ["Navbar expand + chat + Interpreter", "Membaca log per langkah; tiga panel muat di layar ≥1600px."],
            ["Navbar collapse + chat + Interpreter", "Laptop: diagram dan log tetap lebar."],
            ["Navbar collapse saja", "Fokus pada jawaban / kanvas visual."],
          ]}
        />
        <H3>Kanvas visualisasi: lebar &amp; layar penuh</H3>
        <P>
          Kartu diagram memakai tinggi fleksibel <C>min(66vh, 620px)</C> (minimum 380px) dan
          punya tombol <b>Layar penuh</b>. Bila browser menolak Fullscreen API (mis. aplikasi
          dibuka di iframe tanpa izin), kartu otomatis pindah ke <b>focus mode</b> — overlay
          <C>fixed inset-0</C> yang hasilnya sama, dan strip kecil di kartu <i>menyebutkan
          alasannya</i>, tidak diam-diam. Kanvas juga men-<i>refit</i> sendiri saat kontainernya
          berubah ukuran (navbar di-collapse, panel di-drag, layar diputar).
        </P>
        <div className="grid gap-3 lg:grid-cols-2">
          <Shot
            src="/docs-images/20-canvas-diagram.png"
            alt="Kartu diagram dengan badge provenance"
            caption="Kartu diagram: mode Graph/Mermaid, ringkasan node & edge, badge asal konten, dan tombol Layar penuh."
          />
          <Shot
            src="/docs-images/21-canvas-fullscreen.png"
            alt="Kanvas diagram dalam layar penuh"
            caption="Layar penuh: satu kartu menjadi seluruh layar; Esc atau tombol Keluar untuk kembali."
          />
        </div>
        <Shot
          src="/docs-images/28-wide-room-plus-interpreter.png"
          alt="Ruang chat lebar berdampingan dengan Interpreter"
          caption="Ruang chat (maks 1180px) dan Interpreter berdampingan; kartu diagram mengisi seluruh kolom teks."
        />
        <Shot
          src="/docs-images/29-wide-room-navbar-collapsed.png"
          alt="Ruang chat setelah navbar di-collapse"
          caption="Setelah Ctrl+B: kolom chat dan kanvas melebar sekitar 200px."
        />
      </section>

      <section className="space-y-4">
        <H2 id="chat">4. Chat pertama Anda</H2>
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
          caption="Hasil permintaan diagram: chip tool create_diagram ✓, jawaban teks, diagram yang dirender live sebagai graph interaktif, dan panel Interpreter (kanan) yang merekam seluruh event."
        />
      </section>

      <section className="space-y-4">
        <H2 id="jawaban">5. Membaca jawaban agent: provenance &amp; sitasi</H2>
        <P>Satu balasan agent bisa memuat beberapa lapisan informasi:</P>
        <Table
          head={["Elemen UI", "Artinya"]}
          rows={[
            [
              <C>💭 kotak thinking</C>,
              "Reasoning mentah model sebelum memutuskan langkah (muncul saat streaming).",
            ],
            [
              <>Chip tool + lencana asal, mis. <C>🔀 create_diagram · Tool diagram</C></>,
              "Agent memanggil tool itu. Lencana menyatakan asalnya: 🌐 Browser (bukti web, wajib disitasi), 🔀 Tool diagram (konten dibuat alat, bukan sumber), 🧮 Kalkulator. Arahkan kursor untuk ringkasan; status 0 hasil / gagal / durasi ikut tampil.",
            ],
            [
              <>Marker sitasi <C>[1]</C> + bar <C>Sitasi</C></>,
              "Setiap klaim dari browser menaut ke sumber bernomor; bar di bawah jawaban mendaftar URL, tool asal, dan status dikutip — nomor yang tak ada di daftar ditandai tidak valid.",
            ],
            [
              <>Kartu <C>graph interaktif</C></>,
              "Diagram alir / graph / mindmap dirender sebagai graph HTML: zoom, pan, drag node, klik untuk relasi; toggle ke mode Mermaid tersedia.",
            ],
            [
              <>Teks markdown</>,
              "Jawaban final: daftar, tabel, tautan sumber, dan blok kode dirender otomatis.",
            ],
          ]}
        />
        <Shot
          src="/docs-images/24-chat-browsing-cited.png"
          alt="Jawaban browsing dengan sitasi"
          caption="Satu run browsing: chip `web_search · Browser`, marker [1] yang bisa diklik, daftar `## Sumber`, bar Sitasi “1/3 klaim bersitasi”, dan panel kanan yang mencatat `sumber 3` + `citations → cited`."
        />
        <div className="grid gap-3 lg:grid-cols-2">
          <Shot
            src="/docs-images/25-citation-bar.png"
            alt="Detail bar sitasi"
            caption="Bar Sitasi: nomor, judul tertaut URL, tool asal, lencana browser, status dikutip per sumber."
          />
          <Shot
            src="/docs-images/10-chat-calculator.png"
            alt="Percakapan kalkulator"
            caption="Tool calculator: argumen ekspresi dikirim ke tool, hasilnya dikutip agent di jawaban final (lencana 🧮 Kalkulator, bukan bukti web)."
          />
        </div>
      </section>

      <section className="space-y-4">
        <H2 id="browsing">6. Browsing &amp; penanganan error</H2>
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
        <H2 id="interpreter">7. Mechanistic Interpreter</H2>
        <P>
          Panel kanan (tombol <C>Mechanistic Interpreter →</C>) adalah pembeda utama aplikasi ini:
          semua yang dilakukan LLM &amp; agent terekam per-event dan bisa direplay dari riwayat.
          Empat tabnya:
        </P>
        <Table
          head={["Tab", "Isi", "Kapan dipakai"]}
          rows={[
            [
              "Log",
              "Satu baris per langkah: t+ relatif, actor, aksi, status (ok / 0 hasil / gagal), lencana provenance, detail teknis, durasi. Delta & thinking diringkas jadi hitungan (mis. 89 delta · 625 B); tiap baris bisa dibuka jadi JSON mentah. Ada tombol copy log.",
              "Melihat urutan eksekusi & mencari langkah yang lambat atau gagal.",
            ],
            [
              "LLM",
              "Blackbox per langkah: messages persis yang dikirim, schema tools, raw completion, chain-of-thought, tool_calls yang diminta model, finish_reason — plus chip logprob per token bila provider mengirimnya.",
              "Debug perilaku model; melihat apa yang sebenarnya keluar.",
            ],
            [
              "Tools",
              "Tiap pemanggilan: argumen JSON dari model, payload hasil mentah, ok/error/0 hasil, durasi, provenance, jumlah sumber terdaftar, dan catatan provider.",
              "Mengecek tool benar-benar menjalankan itu, bukan sekadar menyebutnya.",
            ],
            [
              "Sumber",
              "Tabel sitasi bernomor: asal (browser + tool), judul/URL, status dikutip, hasil verifikasi (cited / appended / no-evidence), dan penanda nomor tak valid.",
              "Memastikan klaim punya dasar yang bisa diklik.",
            ],
            [
              "Metrik",
              "Provider/model, temperature, max_tokens, steps terpakai, stopped_reason, latensi, token usage, jumlah tool/browser/sumber/error/notes.",
              "Mengukur biaya & performa.",
            ],
          ]}
        />
        <Shot
          src="/docs-images/22-interpreter-log.png"
          alt="Tab Log dengan baris eksekusi"
          caption="Tab Log: setiap langkah satu baris — timestamp relatif, actor, aksi, status, provenance, durasi."
        />
        <Shot
          src="/docs-images/05-interpreter-timeline-expanded.png"
          alt="Satu baris log dibentangkan"
          caption="Satu baris dibuka: payload JSON mentah event itu, apa adanya."
        />
        <Shot
          src="/docs-images/06-interpreter-prompt.png"
          alt="Tab LLM"
          caption="Tab LLM: system prompt, messages persis yang diterima model, raw completion, dan tool_calls yang diminta."
        />
        <Shot
          src="/docs-images/07-interpreter-tokens.png"
          alt="Tab Tools"
          caption="Tab Tools: argumen dari model, payload hasil mentah, status, dan durasi tiap eksekusi (logprob kini tampil sebagai chip di tab LLM)."
        />
        <Shot
          src="/docs-images/08-interpreter-metrics.png"
          alt="Tab Metrik"
          caption="Tab Metrik: angka mentah run — provider, model, temperature, steps, latensi, usage."
        />
        <Shot
          src="/docs-images/23-interpreter-sources.png"
          alt="Tab Sumber"
          caption="Tab Sumber: registri sitasi bernomor + status verifikasi. Bila browser belum menghasilkan apa pun, tab ini mengatakannya — bukan menampilkan tabel kosong."
        />
      </section>

      <section className="space-y-4">
        <H2 id="riwayat">8. Riwayat percakapan</H2>
        <P>
          Setiap percakapan tersimpan otomatis di SQLite lokal beserta seluruh trace event-nya.
          Klik judul di sidebar untuk membuka kembali pesan <b>dan</b> replay Interpreter-nya
          (Log, LLM, Tools, Sumber, Metrik tetap lengkap — trace menyimpan event yang sama
          seperti saat run berlangsung).
        </P>
        <Shot
          src="/docs-images/13-sidebar-history.png"
          alt="Sidebar riwayat percakapan"
          caption="Sidebar: riwayat dikelompokkan per tanggal (Today / Yesterday / …), indikator 'LLM server terhubung', dan tombol Settings provider."
        />
      </section>

      <section className="space-y-4">
        <H2 id="settings">9. Settings provider</H2>
        <P>
          Tombol <C>Settings provider</C> (bawah sidebar) membuka dialog pemilihan LLM: provider{" "}
          <C>huggingface</C> (model offline dari folder <C>models/</C>, inference lokal dengan
          transformers — atau server OpenAI-compatible bila <C>hf_mode=server</C>), <C>openai</C>{" "}
          (API/gateway OpenAI-compatible), atau <C>mock</C> (demo offline deterministik). Base URL,
          model, dan temperature bisa diubah runtime tanpa restart. Tombol <C>Test koneksi</C>{" "}
          menjalankan request sungguhan ke endpoint lalu menampilkan status + pesan server apa
          adanya — cara tercepat mengetahui kenapa sebuah API error.
        </P>
        <Shot
          src="/docs-images/11-settings-provider.png"
          alt="Dialog settings provider"
          caption="Dialog Settings provider: pilihan provider, base URL, model, dan slider temperature."
        />
        <Shot
          src="/docs-images/12-banner-llm-offline.png"
          alt="Banner LLM offline"
          caption="Bila model lokal belum dimuat atau endpoint tidak terjangkau, banner kuning muncul dengan tombol 'Buka Settings' dan sekali-klik 'Pakai mode mock'."
        />
      </section>

      <section className="space-y-4">
        <H2 id="tampilan">10. Tampilan, aksen &amp; mobile</H2>
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
        <H2 id="materi">11. Materi belajar lanjutan</H2>
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
        <H2 id="tips">12. Tips prompt yang efektif</H2>
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
        <H2 id="troubleshoot">13. Troubleshooting</H2>
        <Table
          head={["Gejala", "Penyebab umum", "Solusi"]}
          rows={[
            ["Banner kuning 'Belum ada model offline yang dimuat'", "Provider huggingface mode lokal belum punya model.", "Settings → Model offline (HuggingFace) → cari → Download → Pakai & muat."],
            ["Indikator sidebar merah 'LLM server offline'", "Base URL provider tidak reachable.", "Periksa Settings provider → base URL; atau ganti provider."],
            ["Tool web_search berstatus error", "Tidak ada akses internet / backend diblokir jaringan.", "Normal di lingkungan offline; agent tetap menjawab dengan menyebut error. Konfigurasi Serper/Tavily bila punya key."],
            ["Chip token di tab LLM kosong", "Provider tidak mengirim logprobs (inference lokal & sebagian API).", "Pakai mode openai/server yang mendukung logprobs, atau mode mock."],
            ["Tidak ada yang bisa disitasi", "Tool browser dipanggil tapi menghasilkan 0 (jaringan/endpoint mati, atau query tak ketemu).", "Periksa <C>ASK_SEARCH_DDG_URL</C> / <C>ASK_SEARCH_BACKEND</C> + key; agent sengaja tidak mengarang sumber."],
            ["API error tanpa penjelasan", "Key salah / nama model tidak ada / payload ditolak gateway.", "Settings → Test koneksi: tiga request nyata dijalankan, status + pesan server ditampilkan."],
            ["Download model gagal 'repo privat/gated'", "Repo HuggingFace butuh persetujuan (mis. DeepSeek).", "Isi Token HuggingFace di tab Model offline, atau set ASK_HF_TOKEN."],
            ["Diagram tidak muncul", "Model tidak emit Mermaid valid.", "Ulangi dengan prompt eksplisit 'diagram alir'; mode Graph tetap merender bagian yang terbaca, dan toggle Mermaid menawarkan fallback sebaliknya."],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="privasi">14. Data &amp; privasi</H2>
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
