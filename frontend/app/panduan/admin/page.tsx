import type { Metadata } from "next";
import { C, Code, DocShell, H2, H3, Note, OL, P, Shot, Table, UL } from "@/components/docs/DocShell";

export const metadata: Metadata = {
  title: "Panduan Admin — Ask Anything",
  description:
    "Panduan pengelola Ask Anything: akun & peran, pipeline dan akses per peran, settings provider & model offline, kedua papan task, serta Mechanistic Interpreter.",
};

const TOC: Array<[string, string]> = [
  ["mulai", "1. Tanggung jawab admin"],
  ["akun", "2. Akun & peran"],
  ["pipeline", "3. Pipeline & akses per peran"],
  ["provider", "4. Settings provider & model offline"],
  ["papan", "5. Dua papan task"],
  ["kelola", "6. Mengelola papan sehari-hari"],
  ["detail", "7. Merawat detail task"],
  ["internship", "8. Menjalankan program internship"],
  ["interpreter", "9. Mechanistic Interpreter untuk audit"],
  ["tampilan", "10. Tampilan, aksen & mobile"],
  ["operasional", "11. Operasional & pemeliharaan"],
  ["troubleshoot", "12. Troubleshooting"],
  ["privasi", "13. Data & privasi"],
];

export default function PanduanAdminPage() {
  return (
    <DocShell
      active="panduan-admin"
      title="Panduan Admin"
      subtitle="Untuk pengelola platform: mengatur akun dan peran, menentukan apa yang boleh dipakai member, memilih provider LLM, serta merawat kedua papan task agar jelas dan terarah."
      toc={TOC}
    >
      <section className="space-y-4">
        <H2 id="mulai">1. Tanggung jawab admin</H2>
        <P>
          Sebagai admin Anda memegang empat kendali yang tidak dimiliki member:{" "}
          <b>siapa yang boleh masuk</b> (akun &amp; peran), <b>apa yang boleh mereka pakai</b>{" "}
          (pipeline &amp; akses per peran), <b>model apa yang menjalankan chat</b> (settings
          provider), dan <b>pekerjaan apa yang harus dikerjakan</b> (kedua papan task).
        </P>
        <Note>
          Semua pembatasan ditegakkan di server. Menyembunyikan tombol bukan strategi keamanan di
          aplikasi ini — backend membalas <C>403</C> untuk request yang tidak berhak, termasuk yang
          dikirim manual.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="akun">2. Akun &amp; peran</H2>
        <P>
          Buka <C>/admin</C> → tab <b>Users</b>. Tabelnya memuat akun, peran, jumlah task yang
          ditugaskan, sesi aktif, dan waktu login terakhir.
        </P>
        <Shot
          src="/docs-images/39-admin-users.png"
          alt="Tab Users"
          caption="Tab Users: daftar akun + peran, jumlah task yang ditugaskan, sesi aktif, waktu login terakhir, dan aksi kelola."
        />
        <UL
          items={[
            <>
              <b>+ Akun baru</b> — buat akun member/admin dengan password awal; opsi “wajib ganti
              password” memaksa pemiliknya mengganti saat pertama login.
            </>,
            <>
              <b>Reset password</b> — untuk pemilik yang lupa; semua sesi user itu diputus supaya
              password baru benar-benar berlaku. Anda tidak pernah bisa melihat password lama —
              yang tersimpan hanyalah hash.
            </>,
            <>
              <b>Nonaktifkan / Hapus</b> — nonaktif menolak login (<C>401</C>) tetapi menyimpan
              riwayat &amp; task; hapus bersifat permanen. <b>Admin terakhir</b> tidak bisa dihapus
              maupun diturunkan perannya.
            </>,
          ]}
        />
        <Shot
          src="/docs-images/40-admin-reset-password.png"
          alt="Reset password dari konsol"
          caption="Reset password inline di tab Users — cara admin menolong peserta yang lupa password."
        />
        <H3>Akun hasil seed</H3>
        <P>
          Saat pertama dijalankan backend membuat akun awal dan mencetaknya di log:{" "}
          <C>admin / admin123</C> dan <C>intern1…intern3 / intern123</C>. Bisa diubah lewat env{" "}
          <C>ASK_ADMIN_PASSWORD</C>, <C>ASK_SEED_MEMBERS</C>, <C>ASK_MEMBER_PASSWORD</C>.{" "}
          <b>Ganti password bawaan sebelum dipakai bersama.</b>
        </P>
        <Note>
          Mode <C>ASK_AUTH_MODE=open</C> (demo/test) tidak mewajibkan login: semua request dianggap
          admin anonim sehingga demo &amp; test otomatis tetap jalan. Mode default adalah{" "}
          <C>required</C> — jangan jalankan <C>open</C> di lingkungan yang bisa diakses orang lain.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="pipeline">3. Pipeline &amp; akses per peran</H2>
        <P>
          Tab <b>Pipeline</b> → <b>Akses per peran</b> adalah tempat batas member diatur: provider
          chat (<C>openai</C> = tanpa model offline), cakupan task (<C>assigned</C>/<C>all</C>),
          izin model offline, settings provider, konsol admin, upload RAG, ubah status task — plus
          mode &amp; tool per peran.
        </P>
        <P>
          Rumusnya: <b>gate global × gate peran = izin efektif</b>. Mematikan sebuah mode secara
          global mematikannya untuk semua orang, apa pun saklar perannya. Perubahan berlaku untuk
          run berikutnya <b>tanpa restart</b>.
        </P>
        <Shot
          src="/docs-images/41-admin-pipeline-roles.png"
          alt="Akses per peran"
          caption="Pipeline → Akses per peran: saklar member (kiri) terhadap gate global mode (kanan); member memakai OpenAI dengan teks/diagram/RAG."
        />
        <Table
          head={["Kalau ingin…", "Lakukan"]}
          rows={[
            [
              "Member boleh membuat gambar untuk satu task",
              <span key="a">
                Aktifkan mode <C>gambar</C> + tool <C>generate_image</C> pada baris member, lalu
                matikan lagi setelah task selesai.
              </span>,
            ],
            [
              "Member melihat seluruh papan (bukan hanya task sendiri)",
              <span key="b">
                Ubah cakupan task member dari <C>assigned</C> ke <C>all</C>.
              </span>,
            ],
            [
              "Menghentikan seluruh browsing sementara",
              <span key="c">
                Matikan tool <C>web_search</C> dan <C>fetch_url</C> pada gate global.
              </span>,
            ],
            [
              "Membekukan biaya API mendadak",
              <span key="d">
                Ganti provider ke <C>mock</C> di Settings — aplikasi tetap hidup dan demo tetap
                jalan.
              </span>,
            ],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="provider">4. Settings provider &amp; model offline</H2>
        <P>
          Tombol <C>Settings provider</C> (bawah sidebar) membuka dialog pemilihan LLM: provider{" "}
          <C>huggingface</C> (model offline dari folder <C>models/</C>, atau server
          OpenAI-compatible bila <C>hf_mode=server</C>), <C>openai</C> (API/gateway
          OpenAI-compatible), atau <C>mock</C> (demo offline deterministik). Base URL, model, dan
          temperature bisa diubah runtime tanpa restart.
        </P>
        <P>
          Tombol <C>Test koneksi</C> menjalankan request sungguhan ke endpoint lalu menampilkan
          status + pesan server apa adanya — cara tercepat mengetahui kenapa sebuah API error.
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
        <Note>
          Model offline yang gated (mis. sebagian repo DeepSeek) butuh persetujuan di HuggingFace.
          Isi Token HuggingFace di tab Model offline atau set <C>ASK_HF_TOKEN</C>.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="papan">5. Dua papan task</H2>
        <P>
          Papan task punya <b>dua trek terpisah</b> yang statistiknya tidak dicampur. Id task
          sekaligus menjadi dasar nama branch git.
        </P>
        <Table
          head={["Papan", "Contoh id", "Isi", "Siapa melihat apa"]}
          rows={[
            [
              "Platform",
              <C key="a">ASK-003</C>,
              "Rencana produk aplikasi Ask Anything itu sendiri.",
              "admin: semua task; member: hanya yang ditugaskan",
            ],
            [
              "Internship",
              <C key="i">INT-014</C>,
              "Proyek peserta: membangun chatbot AI agent production-ready dari nol.",
              "admin: seluruh 36 task per fase; member: hanya task miliknya",
            ],
          ]}
        />
        <Shot
          src="/docs-images/42-admin-board-platform.png"
          alt="Papan platform"
          caption="Papan Platform: tombol Platform | Internship memindahkan trek, kolom mengikuti status, kartu memuat id task yang dipakai sebagai nama branch."
        />
        <Shot
          src="/docs-images/43-admin-board-internship.png"
          alt="Papan internship"
          caption="Papan Internship: 36 task / 53.5 hari dengan breadcrumb fase (Fondasi → chat → agent & RAG → memori → token & feedback → rilis) di bawah judul papan."
        />
      </section>

      <section className="space-y-4">
        <H2 id="kelola">6. Mengelola papan sehari-hari</H2>
        <P>
          Header papan sengaja diringkas jadi satu baris: judul + breadcrumb fase di kiri, pemindah
          trek dan aksi di kanan. Kontrol yang jarang dipakai disembunyikan sampai diminta.
        </P>
        <UL
          items={[
            <>
              <b>Chip status</b> (Backlog / To do / In progress / Review / Done) — klik untuk
              menyaring satu kolom saja.
            </>,
            <>
              <b>Kotak cari</b> — cocokkan id, judul, atau label.
            </>,
            <>
              <b>Tombol Filter</b> — panel lipat berisi saringan fase, prioritas, assignee, dan
              label. Badge angka menunjukkan berapa filter yang sedang aktif, jadi Anda tidak
              pernah bingung kenapa papan tampak kosong.
            </>,
            <>
              <b>Papan / Daftar</b> — kanban untuk memindahkan status, tampilan daftar untuk
              meninjau banyak task sekaligus.
            </>,
            <>
              <b>+ Task</b> dan menu <b>⋯</b> — membuat task, memuat rencana (seed), dan menyinkronkan
              informasi git.
            </>,
          ]}
        />
        <Shot
          src="/docs-images/50-admin-board-filters.png"
          alt="Panel filter papan"
          caption="Panel Filter dilipat secara default; dibuka hanya saat dibutuhkan, dengan badge jumlah filter aktif pada tombolnya."
        />
        <Shot
          src="/docs-images/51-admin-board-menu.png"
          alt="Menu aksi papan"
          caption="Menu ⋯ (Aksi papan) menampung aksi jarang pakai: muat rencana, sinkronkan git, dan pemeliharaan papan."
        />
      </section>

      <section className="space-y-4">
        <H2 id="detail">7. Merawat detail task</H2>
        <P>
          Panel detail bertab supaya isi yang padat tetap terbaca. Tugas Anda sebagai admin adalah
          memastikan <b>ketiga tab pertama benar-benar terisi</b> sebelum task diberikan ke
          peserta — task tanpa workflow dan wireframe akan dikerjakan sambil menebak.
        </P>
        <Table
          head={["Tab", "Isi", "Kriteria “sudah cukup”"]}
          rows={[
            [
              "Ringkasan",
              "Deskripsi, kriteria penerimaan, dependensi, estimasi, label, perintah branch.",
              "Checklist bisa dinilai objektif oleh reviewer — bukan “selesai dengan rapi”.",
            ],
            [
              "Workflow",
              "Langkah bernomor: aktor (Intern / Pembimbing / Reviewer), aksi, hasil.",
              "Peserta tahu langkah pertama tanpa bertanya.",
            ],
            [
              "Wireframe",
              "Sketsa ASCII layar, dokumen, atau struktur berkas keluaran.",
              "Bentuk hasil tidak ambigu sebelum kode ditulis.",
            ],
            ["Aktivitas", "Komentar & jejak status/commit.", "Keputusan penting tercatat, bukan hanya di chat."],
          ]}
        />
        <Shot
          src="/docs-images/47-task-ringkasan.png"
          alt="Tab Ringkasan detail task admin"
          caption="Tab Ringkasan: deskripsi, kriteria penerimaan, dan metadata yang bisa diedit admin (prioritas, fase, estimasi, assignee)."
        />
        <Shot
          src="/docs-images/47-task-workflow.png"
          alt="Tab Workflow detail task admin"
          caption="Tab Workflow pada INT-001: empat langkah dengan aktor Intern/Pembimbing dan hasil yang diharapkan. Badge pada tab = jumlah langkah."
        />
        <Shot
          src="/docs-images/47-task-wireframe.png"
          alt="Tab Wireframe detail task admin"
          caption="Tab Wireframe: blok ASCII yang menggambarkan dokumen keluaran beserta daftar berkas yang harus ada."
        />
      </section>

      <section className="space-y-4">
        <H2 id="internship">8. Menjalankan program internship</H2>
        <P>
          Rencana internship membangun <b>chatbot AI agent yang production-ready end-to-end</b> di{" "}
          <C>projects/ai-agent</C>: 36 task dalam 6 fase, total estimasi 53.5 hari.
        </P>
        <Table
          head={["Fase", "Task", "Fokus"]}
          rows={[
            ["i0 Fondasi & Kontrak", "INT-001…007", "Spesifikasi produk, ADR tech stack, kontrak API & skema DB, kerangka backend/frontend, CI."],
            ["i1 Chat Inti & Streaming", "INT-008…012", "Endpoint chat, streaming token, persistensi percakapan, UI chat."],
            ["i2 Agent, Tool & Pengetahuan", "INT-013…019", "Loop agent, tool registry, RAG (ingest → chunk → embed → retrieve), sitasi."],
            ["i3 Memori & Konteks", "INT-020…023", "Memori jangka pendek/panjang, ringkasan percakapan, jendela konteks."],
            ["i4 Token, Kuota & Feedback", "INT-024…028", "Hitung token, limit per user, dashboard biaya, feedback 👍/👎 dan pemanfaatannya."],
            ["i5 Hardening & Rilis", "INT-029…036", "Evaluasi, keamanan, observability, load test, dokumentasi, demo, rilis."],
          ]}
        />
        <Shot
          src="/docs-images/44-admin-internship.png"
          alt="Papan proyek internship (admin)"
          caption="Halaman /internship versi admin: progres keseluruhan, pembagian kerja per peserta, filter fase, daftar task, dan kartu Materi & slide."
        />
        <H3>Ritme yang disarankan</H3>
        <OL
          items={[
            <>
              <b>Sebelum sprint</b> — pastikan task fase berikutnya punya workflow + wireframe,
              lalu tugaskan assignee.
            </>,
            <>
              <b>Harian</b> — periksa kolom <i>Review</i> lebih dulu; task yang menumpuk di sana
              memblokir dependensinya.
            </>,
            <>
              <b>Saat review</b> — nilai dengan checklist kriteria penerimaan, bukan kesan umum.
              Kembalikan ke <i>In progress</i> dengan komentar spesifik bila belum lolos.
            </>,
            <>
              <b>Akhir fase</b> — pakai halaman <C>/internship</C> untuk melihat apakah beban antar
              peserta timpang, lalu seimbangkan penugasan fase berikutnya.
            </>,
          ]}
        />
        <Note>
          Kartu <b>Materi &amp; slide</b> membaca dokumen langsung dari backend (folder{" "}
          <C>docs/internship/</C>). Menambahkan berkas markdown baru di sana membuatnya muncul
          otomatis di <C>/internship</C> tanpa perubahan kode.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="interpreter">9. Mechanistic Interpreter untuk audit</H2>
        <P>
          Bagi admin, Interpreter bukan sekadar alat belajar — ia adalah jejak audit. Setiap run
          tersimpan lengkap dan bisa direplay dari riwayat.
        </P>
        <Table
          head={["Pertanyaan", "Tab yang menjawab"]}
          rows={[
            ["Kenapa jawaban ini lambat?", "Log (durasi per langkah) dan Metrik (latensi total)."],
            ["Apakah agent benar-benar memanggil tool itu?", "Tools — argumen dan payload hasil mentah."],
            ["Apakah klaimnya punya sumber?", "Sumber — status cited / appended / no-evidence."],
            ["Berapa token yang terpakai?", "Metrik — usage prompt/completion per run."],
            ["Apa persisnya yang dikirim ke provider?", "LLM — messages dan schema tools apa adanya."],
          ]}
        />
        <Shot
          src="/docs-images/23-interpreter-sources.png"
          alt="Tab Sumber"
          caption="Tab Sumber: registri sitasi bernomor + status verifikasi. Bila browser belum menghasilkan apa pun, tab ini mengatakannya — bukan menampilkan tabel kosong."
        />
        <Shot
          src="/docs-images/05-interpreter-timeline-expanded.png"
          alt="Satu baris log dibentangkan"
          caption="Satu baris dibuka: payload JSON mentah event itu, apa adanya."
        />
      </section>

      <section className="space-y-4">
        <H2 id="tampilan">10. Tampilan, aksen &amp; mobile</H2>
        <P>
          Navbar bisa di-collapse (<C>Ctrl/Cmd+B</C>) dan ruang yang dilepaskan langsung dipakai
          kolom chat serta kanvas diagram. Empat aksen warna tersedia di composer, dan seluruh
          layar tetap terpakai pada lebar ponsel.
        </P>
        <div className="grid gap-3 lg:grid-cols-2">
          <Shot
            src="/docs-images/28-wide-room-plus-interpreter.png"
            alt="Ruang chat lebar berdampingan dengan Interpreter"
            caption="Chat dan Interpreter berdampingan — layout paling berguna saat mengaudit run."
          />
          <Shot
            src="/docs-images/19-sidebar-collapsed.png"
            alt="Navbar collapsed"
            caption="Navbar collapsed: riwayat menjadi rail titik yang tetap bisa dipilih dengan keyboard."
          />
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
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
        </div>
      </section>

      <section className="space-y-4">
        <H2 id="operasional">11. Operasional &amp; pemeliharaan</H2>
        <H3>Variabel lingkungan yang sering dipakai</H3>
        <Table
          head={["Env", "Gunanya"]}
          rows={[
            [<C key="a">ASK_AUTH_MODE</C>, <span key="a2"><C>required</C> (default) atau <C>open</C> untuk demo/test.</span>],
            [<C key="b">ASK_DB_PATH</C>, "Lokasi database SQLite (default data/ask_anything.db)."],
            [<C key="c">ASK_ADMIN_PASSWORD</C>, "Password admin awal saat seeding."],
            [<C key="d">ASK_SEED_MEMBERS</C>, "Daftar akun member yang dibuat otomatis."],
            [<C key="e">ASK_HF_TOKEN</C>, "Token HuggingFace untuk repo model yang gated."],
            [<C key="f">ASK_SEARCH_DDG_URL</C>, "Endpoint gateway pencarian (bisa diarahkan ke gateway internal)."],
          ]}
        />
        <H3>Memperbarui screenshot dokumentasi</H3>
        <P>
          Seluruh gambar di panduan ini adalah screenshot aplikasi yang benar-benar berjalan,
          diambil otomatis. Jalankan ulang setiap kali UI berubah supaya dokumen tidak kedaluwarsa
          diam-diam:
        </P>
        <Code>{`# sekali saja: siapkan Chromium + font
bash scripts/setup_chromium.sh
source ~/.tooling/chrome/env.sh

# ambil ulang screenshot (urut: main → roles → pages)
python scripts/capture_screenshots.py main
python scripts/capture_screenshots.py roles
python scripts/capture_screenshots.py pages`}</Code>
      </section>

      <section className="space-y-4">
        <H2 id="troubleshoot">12. Troubleshooting</H2>
        <Table
          head={["Gejala", "Penyebab umum", "Solusi"]}
          rows={[
            [
              "Banner kuning 'Belum ada model offline yang dimuat'",
              "Provider huggingface mode lokal belum punya model.",
              "Settings → Model offline → cari → Download → Pakai & muat.",
            ],
            [
              "Indikator sidebar merah 'LLM server offline'",
              "Base URL provider tidak reachable.",
              "Periksa Settings provider → base URL, atau jalankan Test koneksi.",
            ],
            [
              "API error tanpa penjelasan",
              "Key salah / nama model tidak ada / payload ditolak gateway.",
              "Settings → Test koneksi: request nyata dijalankan, status + pesan server ditampilkan.",
            ],
            [
              "Download model gagal 'repo privat/gated'",
              "Repo HuggingFace butuh persetujuan.",
              "Isi Token HuggingFace di tab Model offline, atau set ASK_HF_TOKEN.",
            ],
            [
              "Tool web_search berstatus error",
              "Tidak ada akses internet dari backend.",
              "Normal di lingkungan offline; konfigurasi Serper/Tavily bila punya key.",
            ],
            [
              "Papan task member kosong",
              "Belum ada task yang ditugaskan.",
              "Tetapkan Assignee di detail task, atau muat rencana lewat menu ⋯.",
            ],
            [
              "Member melaporkan 403 pada fitur yang ia butuhkan",
              "Policy peran membatasi fitur itu.",
              "Pipeline → Akses per peran; buka izinnya bila tugas memang memerlukannya.",
            ],
            [
              "/admin menolak akses",
              "Akun bukan role admin.",
              "Naikkan peran di tab Users (admin terakhir tidak bisa diturunkan).",
            ],
            [
              "Chip token di tab LLM kosong",
              "Provider tidak mengirim logprobs.",
              "Pakai provider yang mendukung logprobs, atau mode mock.",
            ],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="privasi">13. Data &amp; privasi</H2>
        <UL
          items={[
            <>
              Semua percakapan &amp; trace tersimpan lokal di SQLite (<C>data/ask_anything.db</C>,
              bisa diubah via <C>ASK_DB_PATH</C>).
            </>,
            <>Tidak ada telemetri dari aplikasi; permintaan LLM hanya menuju provider yang Anda pilih.</>,
            <>
              Hapus riwayat: <C>DELETE /api/conversations/&#123;id&#125;</C> atau hapus file DB saat
              aplikasi mati.
            </>,
            <>
              Password disimpan sebagai hash PBKDF2 (tidak pernah dikembalikan API); sesi berupa
              cookie HttpOnly <C>ask_session</C>. Ganti/reset password memutus sesi lain, akun
              nonaktif ditolak login.
            </>,
            <>
              Percakapan hanya bisa dibuka pemiliknya — termasuk oleh admin. Kalau Anda butuh
              meninjau isi percakapan peserta, mintalah mereka membagikannya, jangan mengakses DB
              diam-diam.
            </>,
            <>
              Bila provider aktif adalah layanan cloud, isi percakapan dikirim ke sana.
              Komunikasikan ini ke pengguna — chip provider di header adalah indikator yang
              terlihat semua orang.
            </>,
          ]}
        />
      </section>
    </DocShell>
  );
}
