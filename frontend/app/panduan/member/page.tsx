import type { Metadata } from "next";
import { C, Code, DocShell, H2, H3, Note, OL, P, Shot, Table, UL } from "@/components/docs/DocShell";

export const metadata: Metadata = {
  title: "Panduan Member — Ask Anything",
  description:
    "Panduan lengkap untuk peserta internship: masuk, memakai playground chat, membaca task (deskripsi, workflow, wireframe), dan alur kerja harian dengan git.",
};

const TOC: Array<[string, string]> = [
  ["mulai", "1. Untuk siapa halaman ini"],
  ["masuk", "2. Masuk & akun Anda"],
  ["layar", "3. Mengenal layar playground"],
  ["chat", "4. Chat pertama Anda"],
  ["jawaban", "5. Membaca jawaban agent"],
  ["interpreter", "6. Menelusuri proses dengan Interpreter"],
  ["riwayat", "7. Riwayat percakapan"],
  ["papan", "8. Papan task Anda"],
  ["detail", "9. Membaca detail task"],
  ["harian", "10. Alur kerja harian"],
  ["internship", "11. Halaman /internship & materi"],
  ["tips", "12. Tips prompt yang efektif"],
  ["batas", "13. Batas akses member"],
  ["troubleshoot", "14. Troubleshooting"],
];

export default function PanduanMemberPage() {
  return (
    <DocShell
      active="panduan-member"
      title="Panduan Member"
      subtitle="Untuk peserta internship. Berisi semua yang Anda butuhkan: masuk, memakai playground, membaca task sampai ke workflow & wireframe, dan menyelesaikannya lewat branch git."
      toc={TOC}
    >
      <section className="space-y-4">
        <H2 id="mulai">1. Untuk siapa halaman ini</H2>
        <P>
          Halaman ini ditulis untuk akun berperan <b>member</b> — peserta internship yang
          memakai Ask Anything sebagai dua hal sekaligus: <b>playground</b> untuk memahami cara
          kerja chatbot agentik, dan <b>papan task</b> tempat pekerjaan Anda dikelola. Anda tidak
          perlu membuka Panduan Admin; semua yang relevan ada di sini.
        </P>
        <Note>
          Kalau sebuah tombol membalas <C>403</C>, itu bukan bug — fitur tersebut memang khusus
          admin. Daftar lengkapnya ada di bab <a className="underline" href="#batas">13</a>.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="masuk">2. Masuk &amp; akun Anda</H2>
        <P>
          Buka aplikasi tanpa sesi → Anda diarahkan ke <C>/login</C>, lalu dikembalikan ke halaman
          yang dituju (<C>?next=…</C>). Sesi disimpan sebagai cookie <b>HttpOnly</b>{" "}
          <C>ask_session</C> — tidak ada token di localStorage.
        </P>
        <Shot
          src="/docs-images/30-login.png"
          alt="Halaman login"
          caption="Halaman login: satu pintu masuk untuk admin maupun member. Salah password → pesan jelas, percobaan beruntun dibatasi (429)."
        />
        <Shot
          src="/docs-images/31-login-error.png"
          alt="Pesan error login"
          caption="Login gagal menampilkan sebabnya (password salah / akun nonaktif) tanpa membocorkan informasi akun lain."
        />
        <H3>Akun awal</H3>
        <P>
          Akun peserta hasil seed berbentuk <C>intern1…intern3</C> dengan password{" "}
          <C>intern123</C>. <b>Ganti password bawaan pada hari pertama.</b> Bila admin membuat
          akun untuk Anda dengan opsi “wajib ganti password”, aplikasi akan memaksa penggantian
          saat login pertama.
        </P>
        <H3>Ganti nama &amp; password sendiri</H3>
        <P>
          Klik <b>Profil &amp; password</b> di bawah sidebar. Nama tampilan bebas; ganti password
          wajib mengisi password lama dan minimal 6 karakter. Setelah sukses,{" "}
          <b>semua sesi lain milik akun Anda diputus</b>. Lupa password? Minta admin meresetnya —
          tidak ada reset lewat email.
        </P>
        <Shot
          src="/docs-images/34-member-profile.png"
          alt="Modal profil"
          caption="Modal Profil: ubah nama tampilan dan ganti password (butuh password lama)."
        />
        <Shot
          src="/docs-images/35-member-password-changed.png"
          alt="Password diganti"
          caption="Bukti sukses ganti password — sesi lain diputus supaya password baru benar-benar berlaku."
        />
      </section>

      <section className="space-y-4">
        <H2 id="layar">3. Mengenal layar playground</H2>
        <P>
          UI otomatis menyesuaikan peran Anda: badge <C>openai · akses member</C> di header
          (provider dikunci policy), mode gambar/PPT/deep research tidak aktif, dan tombol bawah
          sidebar menjadi <b>Profil &amp; password</b> — bukan <i>Settings provider</i>.
        </P>
        <Shot
          src="/docs-images/32-member-chat.png"
          alt="Playground member"
          caption="Playground member: mode teks, diagram, dan RAG — label openai menandakan hanya provider OpenAI yang dipakai."
        />
        <UL
          items={[
            <>
              <b>Navbar kiri</b> — bisa di-collapse jadi rail ikon (64px) atau di-expand (268px)
              lewat tombol <C>‹</C> atau <C>Ctrl/Cmd+B</C>. Berisi <C>New chat</C>, riwayat per
              tanggal, pintasan <b>Tasks</b> &amp; <b>Internship</b>, dan indikator status LLM.
              Pilihan Anda tersimpan setelah refresh.
            </>,
            <>
              <b>Header</b> — judul percakapan aktif, chip provider+model, tautan{" "}
              <C>Docs &amp; Slides</C>, dan tombol <C>Mechanistic Interpreter →</C>.
            </>,
            <>
              <b>Composer</b> — tempat menulis pertanyaan; kirim dengan <C>Enter</C> (
              <C>Shift+Enter</C> untuk baris baru). Baris bawahnya memuat pemilih mode, badge
              jumlah tool aktif, dan empat titik aksen warna.
            </>,
            <>
              <b>Chip contoh &amp; galeri Explore</b> — klik untuk mengisi composer dengan prompt
              siap pakai per kategori.
            </>,
          ]}
        />
        <Shot
          src="/docs-images/33-member-sidebar.png"
          alt="Sidebar member"
          caption="Sidebar member: identitas (intern1 · Member · task saya), status LLM, Profil & password, dan Keluar."
        />
      </section>

      <section className="space-y-4">
        <H2 id="chat">4. Chat pertama Anda</H2>
        <OL
          items={[
            <>
              Klik chip contoh (mis. <C>Diagram alir →</C>) atau ketik pertanyaan sendiri.
            </>,
            <>
              Periksa baris bawah composer: badge <C>tools</C> menunjukkan tool yang aktif untuk
              agent.
            </>,
            <>
              Tekan <C>Enter</C>. Tombol berubah menjadi <C>Thinking…</C> selama agent bekerja.
            </>,
            <>
              Jawaban muncul bertahap (streaming), dan panel Mechanistic Interpreter merekam
              prosesnya.
            </>,
          ]}
        />
        <Shot
          src="/docs-images/03-composer-filled.png"
          alt="Composer terisi prompt contoh"
          caption="Composer terisi prompt contoh setelah klik chip. Badge tools = web_search, fetch_url, create_diagram, calculator."
        />
        <Shot
          src="/docs-images/04-chat-diagram-interpreter.png"
          alt="Chat dengan diagram dan interpreter"
          caption="Hasil permintaan diagram: chip tool create_diagram ✓, jawaban teks, diagram yang dirender live sebagai graph interaktif, dan panel Interpreter yang merekam seluruh event."
        />
      </section>

      <section className="space-y-4">
        <H2 id="jawaban">5. Membaca jawaban agent</H2>
        <P>Satu balasan agent bisa memuat beberapa lapisan informasi:</P>
        <Table
          head={["Elemen UI", "Artinya"]}
          rows={[
            [
              <C key="t">💭 kotak thinking</C>,
              "Reasoning mentah model sebelum memutuskan langkah (muncul saat streaming).",
            ],
            [
              <span key="c">
                Chip tool + lencana asal, mis. <C>🔀 create_diagram · Tool diagram</C>
              </span>,
              "Agent memanggil tool itu. Lencana menyatakan asalnya: 🌐 Browser (bukti web, wajib disitasi), 🔀 Tool diagram (konten dibuat alat, bukan sumber), 🧮 Kalkulator.",
            ],
            [
              <span key="s">
                Marker sitasi <C>[1]</C> + bar <C>Sitasi</C>
              </span>,
              "Setiap klaim dari browser menaut ke sumber bernomor; bar di bawah jawaban mendaftar URL, tool asal, dan status dikutip.",
            ],
            [
              <span key="g">
                Kartu <C>graph interaktif</C>
              </span>,
              "Diagram dirender sebagai graph HTML: zoom, pan, drag node; toggle ke mode Mermaid tersedia.",
            ],
          ]}
        />
        <Shot
          src="/docs-images/24-chat-browsing-cited.png"
          alt="Jawaban browsing dengan sitasi"
          caption="Satu run browsing: chip web_search · Browser, marker [1] yang bisa diklik, daftar Sumber, dan bar Sitasi."
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
            caption="Tool calculator: ekspresi dikirim ke tool, hasilnya dikutip agent di jawaban final (lencana 🧮, bukan bukti web)."
          />
        </div>
        <P>
          Bila jaringan gagal, error <b>tidak</b> mematikan percakapan: status error diberikan ke
          model sebagai data, dan model menjawab jujur menyebutkan kegagalannya — bukan mengarang
          sumber.
        </P>
        <Shot
          src="/docs-images/09-chat-browsing-error.png"
          alt="Tool web_search gagal ditangani graceful"
          caption="Graceful degradation: web_search gagal (lingkungan offline), error tampil sebagai tool_result, agent tetap merangkum dengan menyebut keterbatasannya."
        />
      </section>

      <section className="space-y-4">
        <H2 id="interpreter">6. Menelusuri proses dengan Interpreter</H2>
        <P>
          Panel kanan (tombol <C>Mechanistic Interpreter →</C>) adalah alat belajar paling berguna
          bagi peserta: semua yang dilakukan LLM &amp; agent terekam per-event dan bisa direplay
          dari riwayat.
        </P>
        <Table
          head={["Tab", "Isi", "Kapan dipakai"]}
          rows={[
            [
              "Log",
              "Satu baris per langkah: t+ relatif, actor, aksi, status, lencana provenance, durasi. Tiap baris bisa dibuka jadi JSON mentah.",
              "Melihat urutan eksekusi & mencari langkah yang lambat atau gagal.",
            ],
            [
              "LLM",
              "Blackbox per langkah: messages persis yang dikirim, schema tools, raw completion, tool_calls, finish_reason.",
              "Memahami apa yang sebenarnya diterima dan dikeluarkan model.",
            ],
            [
              "Tools",
              "Tiap pemanggilan: argumen JSON dari model, payload hasil mentah, ok/error, durasi.",
              "Mengecek tool benar-benar dijalankan, bukan sekadar disebut.",
            ],
            [
              "Sumber",
              "Tabel sitasi bernomor: asal, judul/URL, status dikutip, hasil verifikasi.",
              "Memastikan klaim punya dasar yang bisa diklik.",
            ],
            [
              "Metrik",
              "Provider/model, temperature, steps, latensi, token usage, jumlah tool/error.",
              "Mengukur biaya & performa — relevan untuk task kuota token.",
            ],
          ]}
        />
        <Shot
          src="/docs-images/22-interpreter-log.png"
          alt="Tab Log"
          caption="Tab Log: setiap langkah satu baris — timestamp relatif, actor, aksi, status, provenance, durasi."
        />
        <Shot
          src="/docs-images/06-interpreter-prompt.png"
          alt="Tab LLM"
          caption="Tab LLM: system prompt, messages persis yang diterima model, raw completion, dan tool_calls yang diminta."
        />
        <Shot
          src="/docs-images/08-interpreter-metrics.png"
          alt="Tab Metrik"
          caption="Tab Metrik: angka mentah run — provider, model, temperature, steps, latensi, usage."
        />
      </section>

      <section className="space-y-4">
        <H2 id="riwayat">7. Riwayat percakapan</H2>
        <P>
          Setiap percakapan tersimpan otomatis beserta seluruh trace event-nya. Klik judul di
          sidebar untuk membuka kembali pesan <b>dan</b> replay Interpreter-nya. Percakapan hanya
          bisa dibuka pemiliknya — pembatasan ditegakkan server.
        </P>
        <Shot
          src="/docs-images/13-sidebar-history.png"
          alt="Sidebar riwayat percakapan"
          caption="Sidebar: riwayat dikelompokkan per tanggal (Today / Yesterday / …) dan indikator status LLM."
        />
      </section>

      <section className="space-y-4">
        <H2 id="papan">8. Papan task Anda</H2>
        <P>
          Papan dibuka di trek <b>Internship</b> (id <C>INT-NNN</C>) dan hanya memuat task yang
          ditugaskan kepada Anda — badan papan menampilkan penanda{" "}
          <b>“menampilkan task untuk Anda”</b>. Filter yang sama berlaku di API (
          <C>tasks_scope=assigned</C>), jadi task orang lain tidak bisa ditarik lewat request
          manual.
        </P>
        <Shot
          src="/docs-images/36-member-tasks.png"
          alt="Papan member"
          caption="Papan versi member: hanya task yang ditugaskan ke akun tersebut, lengkap dengan badge cakupan."
        />
        <H3>Cara membaca kartu</H3>
        <UL
          items={[
            <>
              <b>Id task</b> (mis. <C>INT-014</C>) — sekaligus dasar nama branch git.
            </>,
            <>
              <b>Chip prioritas</b> dan, bila ada, lencana <b>⛔ n</b> = jumlah task yang harus
              selesai lebih dulu. Kartu terkunci sampai dependensinya <i>Done</i>.
            </>,
            <>
              <b>checklist 0/4</b> + bar progres — kriteria penerimaan yang harus dicentang.
            </>,
            <>
              <b>Label</b> (<C>#internship</C>, <C>#backend</C>, …) untuk menyaring cepat.
            </>,
            <>
              <b>Estimasi</b> dalam hari, dan inisial assignee di pojok.
            </>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="detail">9. Membaca detail task</H2>
        <P>
          Klik kartu mana pun untuk membuka panel detail. Panel ini <b>bertab</b> supaya isinya
          yang padat tidak menumpuk jadi satu dinding teks:
        </P>
        <Table
          head={["Tab", "Isi", "Gunanya"]}
          rows={[
            [
              "Ringkasan",
              "Deskripsi, kriteria penerimaan (checklist), dependensi, estimasi, label, dan perintah branch siap salin.",
              "Menjawab “apa yang harus jadi” — checklist inilah kontrak task.",
            ],
            [
              "Workflow",
              "Langkah-langkah bernomor: siapa aktornya (Intern / Pembimbing / Reviewer), apa aksinya, dan hasil yang diharapkan.",
              "Menjawab “bagaimana urutan mengerjakannya”.",
            ],
            [
              "Wireframe",
              "Sketsa ASCII layar/berkas yang harus dihasilkan.",
              "Menjawab “seperti apa bentuk hasilnya” sebelum Anda menulis kode.",
            ],
            ["Aktivitas", "Komentar & jejak perubahan status.", "Melapor progres dan mencatat keputusan."],
          ]}
        />
        <Shot
          src="/docs-images/46-member-task-ringkasan.png"
          alt="Tab Ringkasan pada detail task member"
          caption="Tab Ringkasan: deskripsi, checklist kriteria penerimaan, dan metadata task."
        />
        <Shot
          src="/docs-images/46-member-task-workflow.png"
          alt="Tab Workflow pada detail task member"
          caption="Tab Workflow: langkah bernomor dengan aktor dan hasil yang diharapkan. Badge di tab menunjukkan jumlah langkah."
        />
        <Shot
          src="/docs-images/46-member-task-wireframe.png"
          alt="Tab Wireframe pada detail task member"
          caption="Tab Wireframe: sketsa ASCII bentuk keluaran task — layar, dokumen, atau struktur berkas."
        />
        <H3>Apa yang boleh Anda ubah</H3>
        <Table
          head={["Bagian task", "Member", "Admin"]}
          rows={[
            ["Status (Backlog → To do → In progress → Review → Done)", "boleh", "boleh"],
            ["Checklist kriteria penerimaan", "boleh centang", "boleh"],
            ["Komentar (catatan progres, link bukti)", "boleh", "boleh"],
            ["Prioritas, fase, estimasi, assignee, deskripsi", "terkunci", "boleh"],
            ["Hapus task", "tidak", "boleh"],
          ]}
        />
        <Shot
          src="/docs-images/37-member-task-detail.png"
          alt="Detail task untuk member"
          caption="Detail task bagi member: status, checklist, dan komentar terbuka; penugasan/prioritas/fase/hapus terkunci."
        />
      </section>

      <section className="space-y-4">
        <H2 id="harian">10. Alur kerja harian</H2>
        <OL
          items={[
            <>
              Ambil task <i>To do</i> milik Anda yang <b>tidak terkunci dependensi</b>.
            </>,
            <>
              Baca ketiga tab sampai jelas: Ringkasan (kontrak) → Workflow (urutan) → Wireframe
              (bentuk hasil). Bila masih ambigu, tanyakan di komentar <i>sebelum</i> menulis kode.
            </>,
            <>Salin perintah branch dari panel detail dan buat branch-nya.</>,
            <>
              Pindahkan status ke <i>In progress</i> dan tulis komentar untuk setiap keputusan
              penting.
            </>,
            <>
              Centang kriteria penerimaan satu per satu sambil mengerjakan — bukan sekaligus di
              akhir.
            </>,
            <>
              Buka PR/MR, tempel tautannya di komentar, pindahkan ke <i>Review</i>.
            </>,
            <>
              Setelah lolos review dan seluruh checklist tercentang → <i>Done</i>.
            </>,
          ]}
        />
        <Code>{`# contoh: task INT-014
git checkout main && git pull
git checkout -b int-014-tool-registry
# ... kerjakan sesuai tab Workflow ...
git add -A && git commit -m "INT-014: tool registry + skema argumen"
git push -u origin int-014-tool-registry`}</Code>
        <Note>
          Tulis pesan commit berawalan id task (<C>INT-014: …</C>). Papan mencocokkan commit ke
          task lewat awalan itu, sehingga jejak kerja Anda muncul otomatis di tab Aktivitas.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="internship">11. Halaman /internship &amp; materi</H2>
        <P>
          Halaman{" "}
          <a className="underline" href="/internship">
            /internship
          </a>{" "}
          adalah rumah proyek Anda: progres per fase, task milik Anda, dan kartu{" "}
          <b>Materi &amp; slide</b>. Kartu materi membaca dokumen langsung dari repo (folder{" "}
          <C>docs/internship/</C>), jadi yang tampil selalu versi terbaru.
        </P>
        <Shot
          src="/docs-images/38-member-internship.png"
          alt="Papan internship versi member"
          caption="Versi member: hanya task INT-NNN miliknya, dengan aksi cepat memindahkan status dan membaca materi."
        />
        <P>
          Sebelum menulis kode, baca slide{" "}
          <a className="underline" href="/slides/slides-rag-agent.html">
            slides-rag-agent
          </a>{" "}
          dan{" "}
          <a className="underline" href="/slides/slides-cara-kerja.html">
            slides-cara-kerja
          </a>
          . Keduanya menjelaskan konsep yang dipakai task fase awal.
        </P>
        <Shot
          src="/docs-images/14-slides-cara-kerja.png"
          alt="Slide cara kerja agent"
          caption="Slide interaktif 'cara kerja agent' — navigasi dengan ← / →."
        />
      </section>

      <section className="space-y-4">
        <H2 id="tips">12. Tips prompt yang efektif</H2>
        <UL
          items={[
            <>
              Sebutkan kata kunci kemampuan: <C>cari/berita</C> memicu browsing,{" "}
              <C>diagram/alur/graph/mindmap</C> memicu pembuatan diagram, <C>hitung</C> memicu
              calculator.
            </>,
            <>Minta sumber: “lengkap dengan link sumber” membuat agent menyertakan URL hasil search.</>,
            <>
              Untuk diagram relasi, sebutkan node-nya: “graph relasi antar microservice: gateway,
              auth, billing…”.
            </>,
            <>
              Gabungkan: “Jelaskan cara kerja DNS lalu buat diagram alurnya” — penjelasan + visual
              dalam satu run.
            </>,
            <>
              Lanjutkan percakapan untuk memperbaiki diagram: riwayat dikirim sebagai konteks
              langkah berikutnya.
            </>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="batas">13. Batas akses member</H2>
        <P>
          Hal-hal berikut sengaja ditolak server dengan <C>403</C>. Bila sebuah task memang
          membutuhkannya, minta admin membuka izinnya di Pipeline → Akses per peran.
        </P>
        <UL
          items={[
            "Mode gambar, PPT, dan deep research pada composer.",
            <>
              Tool <C>generate_image</C> dan <C>generate_ppt</C>.
            </>,
            "Upload dokumen ke indeks RAG (memakai indeks yang ada tetap boleh).",
            "Settings provider, serta mengunduh/memuat model offline.",
            <>
              Konsol <C>/admin</C> dan papan task penuh (kedua trek, semua assignee).
            </>,
            "Membuat, menghapus, atau menugaskan task.",
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="troubleshoot">14. Troubleshooting</H2>
        <Table
          head={["Gejala", "Penyebab umum", "Solusi"]}
          rows={[
            [
              "Papan task saya kosong",
              "Belum ada task yang ditugaskan ke akun Anda.",
              "Minta admin menetapkan Assignee pada task yang relevan.",
            ],
            [
              "Kartu task tidak bisa dipindahkan",
              "Dependensinya belum Done (lencana ⛔ pada kartu).",
              "Selesaikan task prasyarat lebih dulu, atau diskusikan urutannya dengan pembimbing.",
            ],
            [
              "Tab Workflow / Wireframe kosong",
              "Task itu memang belum punya rincian tersebut.",
              "Minta pembimbing melengkapinya sebelum Anda mulai — jangan menebak.",
            ],
            [
              "403 saat mengubah provider atau mode gambar",
              "Role member dibatasi policy (bukan bug).",
              "Lihat bab 13; minta admin bila tugas memang membutuhkannya.",
            ],
            [
              "Selalu diarahkan ke /login",
              "Sesi kedaluwarsa atau cookie diblokir.",
              "Masuk ulang; pastikan cookie pihak pertama tidak diblokir browser.",
            ],
            [
              "Indikator sidebar merah 'LLM server offline'",
              "Endpoint provider tidak terjangkau.",
              "Laporkan ke admin — member tidak bisa mengubah settings provider.",
            ],
            [
              "Tool web_search berstatus error",
              "Tidak ada akses internet dari server.",
              "Normal di lingkungan offline; agent tetap menjawab dengan menyebut error.",
            ],
            [
              "Diagram tidak muncul",
              "Model tidak menghasilkan Mermaid yang valid.",
              "Ulangi dengan prompt eksplisit 'diagram alir'; mode Graph tetap merender bagian yang terbaca.",
            ],
          ]}
        />
      </section>
    </DocShell>
  );
}
