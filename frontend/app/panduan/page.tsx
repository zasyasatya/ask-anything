import type { Metadata } from "next";
import Link from "next/link";
import { C, DocShell, H2, Note, P, Shot, Table, UL } from "@/components/docs/DocShell";

export const metadata: Metadata = {
  title: "Panduan Pengguna — Ask Anything",
  description:
    "Titik masuk panduan Ask Anything: pilih panduan sesuai peran Anda — Member (peserta internship) atau Admin (pengelola platform).",
};

const TOC: Array<[string, string]> = [
  ["mulai", "Mulai dalam 1 menit"],
  ["peran", "Dua peran: member & admin"],
  ["pilih", "Pilih panduan Anda"],
  ["bersama", "Yang sama untuk semua peran"],
  ["troubleshoot", "Troubleshooting umum"],
  ["privasi", "Data & privasi"],
];

function RoleCard({
  href,
  badge,
  title,
  blurb,
  points,
  cta,
}: {
  href: string;
  badge: string;
  title: string;
  blurb: string;
  points: string[];
  cta: string;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-2xl border border-zinc-200 bg-white p-5 transition hover:border-accent-ring hover:shadow-card"
    >
      <span className="w-fit rounded-md bg-zinc-900 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
        {badge}
      </span>
      <h3 className="mt-2.5 text-[17px] font-semibold text-zinc-900">{title}</h3>
      <p className="mt-1 text-[13.5px] leading-6 text-zinc-500">{blurb}</p>
      <ul className="mt-3 flex-1 space-y-1.5 text-[13px] leading-6 text-zinc-600">
        {points.map((p) => (
          <li key={p} className="flex gap-2">
            <span aria-hidden className="text-accent">
              ›
            </span>
            <span>{p}</span>
          </li>
        ))}
      </ul>
      <span className="mt-4 text-[13.5px] font-medium text-accent group-hover:underline">
        {cta} →
      </span>
    </Link>
  );
}

export default function PanduanPage() {
  return (
    <DocShell
      active="panduan"
      title="Panduan Pengguna"
      subtitle="Ask Anything dipakai oleh dua peran dengan kebutuhan yang sangat berbeda. Mulailah dari panduan peran Anda — keduanya berdiri sendiri dan berisi screenshot aplikasi sungguhan."
      toc={TOC}
    >
      <section className="space-y-4">
        <H2 id="mulai">1. Mulai dalam 1 menit</H2>
        <P>
          Ask Anything adalah chatbot AI <b>agentic</b>: ia bisa mencari di web, membaca isi
          halaman, menghitung, dan menggambar diagram — sambil memperlihatkan seluruh proses
          berpikirnya di panel Mechanistic Interpreter. Di atas itu ada <b>papan task</b> untuk
          mengelola pekerjaan platform (<C>ASK-NNN</C>) dan proyek internship (<C>INT-NNN</C>).
        </P>
        <Shot
          src="/docs-images/30-login.png"
          alt="Halaman login Ask Anything"
          caption="Halaman /login. Semua orang masuk lewat pintu yang sama; peran akun Anda yang menentukan apa yang terlihat setelahnya."
        />
      </section>

      <section className="space-y-4">
        <H2 id="peran">2. Dua peran: member &amp; admin</H2>
        <P>
          Pembatasan peran ditegakkan <b>di server</b>, bukan sekadar disembunyikan di UI. Menebak
          URL halaman admin tidak akan berhasil — backend membalas <C>403</C>.
        </P>
        <Table
          head={["", "Member (peserta internship)", "Admin (pengelola)"]}
          rows={[
            [
              "Chat",
              "Mode teks, diagram, RAG — provider OpenAI",
              "Semua mode: teks, gambar, diagram, PPT, RAG, deep research",
            ],
            [
              "Papan task",
              "Hanya task yang ditugaskan kepadanya; boleh ubah status, checklist, komentar",
              "Semua task di kedua papan; buat, hapus, tugaskan, seed, sync git",
            ],
            ["Pengaturan provider", "Tidak (403)", "Ya, termasuk model offline"],
            ["Konsol /admin", "Tidak (403)", "Ya: akun, peran, pipeline, analitik"],
            ["Akun", "Ganti nama & password sendiri", "Buat akun, atur peran, reset password"],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="pilih">3. Pilih panduan Anda</H2>
        <div className="grid gap-4 md:grid-cols-2">
          <RoleCard
            href="/panduan/member"
            badge="member"
            title="Panduan Member"
            blurb="Untuk peserta internship yang mengerjakan task dan memakai playground."
            points={[
              "Masuk & mengenal playground",
              "Chat: mode teks, diagram, dan RAG",
              "Membaca task: deskripsi, workflow, wireframe",
              "Memindahkan status & melapor lewat komentar",
              "Alur kerja harian dengan branch git",
            ]}
            cta="Buka panduan member"
          />
          <RoleCard
            href="/panduan/admin"
            badge="admin"
            title="Panduan Admin"
            blurb="Untuk pengelola platform: akun, peran, pipeline, dan kedua papan task."
            points={[
              "Mengelola akun & peran (konsol /admin)",
              "Pipeline: mode, tool, dan akses per peran",
              "Settings provider & model offline",
              "Papan platform + internship, seed & sync git",
              "Mechanistic Interpreter untuk menelusuri jawaban",
            ]}
            cta="Buka panduan admin"
          />
        </div>
        <Note>
          Belum tahu peran Anda? Lihat pojok kiri bawah sidebar setelah login — nama akun beserta
          labelnya (<b>Admin</b> atau <b>Member</b>) tertulis di sana.
        </Note>
      </section>

      <section className="space-y-4">
        <H2 id="bersama">4. Yang sama untuk semua peran</H2>
        <UL
          items={[
            <>
              <b>Login & sesi</b> — cookie <C>HttpOnly</C> (<C>ask_session</C>), bukan localStorage.
              Tombol <b>Keluar</b> di sidebar benar-benar mencabut sesi.
            </>,
            <>
              <b>Ganti password sendiri</b> — ikon ⚙ di sidebar → Profil. Admin tidak bisa melihat
              password Anda; ia hanya bisa me-reset-nya.
            </>,
            <>
              <b>Papan task</b> — kartu, kolom, dan panel detail bertab (Ringkasan, Workflow,
              Wireframe, Aktivitas) sama untuk kedua peran; yang berbeda adalah cakupan task dan
              field mana yang boleh diubah.
            </>,
            <>
              <b>Aksen warna & mobile</b> — pemilih warna ada di composer, dan seluruh layar tetap
              bisa dipakai pada lebar 390 px.
            </>,
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="troubleshoot">5. Troubleshooting umum</H2>
        <Table
          head={["Gejala", "Penyebab biasanya", "Tindakan"]}
          rows={[
            [
              "Diarahkan kembali ke /login terus",
              "Sesi kedaluwarsa atau cookie diblokir",
              "Masuk ulang; pastikan cookie pihak pertama tidak diblokir browser",
            ],
            [
              <>
                Tombol/halaman membalas <C>403</C>
              </>,
              "Fitur itu memang khusus admin",
              "Minta admin mengubah izin di Admin → Pipeline → Akses per peran",
            ],
            [
              "Banner “Belum ada model offline yang dimuat”",
              "Provider huggingface aktif tetapi model belum diunduh",
              <>
                Klik <b>Pakai mode mock</b>, atau minta admin memuat model
              </>,
            ],
            [
              "Papan task kosong",
              "Belum ada task yang ditugaskan kepada Anda",
              "Minta admin menugaskan task di papan yang sesuai",
            ],
            [
              "Jawaban menyebut browsing tidak menghasilkan apa pun",
              "Tidak ada akses internet dari server",
              "Itu perilaku jujur — agent menolak mengarang sitasi",
            ],
          ]}
        />
      </section>

      <section className="space-y-4">
        <H2 id="privasi">6. Data &amp; privasi</H2>
        <UL
          items={[
            "Percakapan, task, dan komentar disimpan di database lokal aplikasi (SQLite) — tidak dikirim ke pihak ketiga selain provider LLM yang dikonfigurasi admin.",
            "Password disimpan sebagai hash, tidak pernah dalam bentuk asli.",
            "Sesi memakai cookie HttpOnly sehingga tidak bisa dibaca JavaScript halaman.",
            "Bila provider yang aktif adalah layanan cloud (mis. OpenAI), isi percakapan dikirim ke sana — tanyakan ke admin provider mana yang sedang dipakai; indikatornya terlihat di header chat.",
          ]}
        />
      </section>
    </DocShell>
  );
}
