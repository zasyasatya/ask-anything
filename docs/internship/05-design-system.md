# Design System: Internal AI Assistant & RAG Agent (beUI Native)

* **Kode Dokumen**: `DS-001`
* **Versi**: `1.1.0`
* **Status**: `Approved / Definitive Source of Truth`
* **Pustaka Utama**: **beUI (`https://beui.dev`)**
* **Registri Komponen**: `@beui` via shadcn registry (`https://mcp.beui.dev/mcp`)
* **Pustaka Ikon**: **`lucide-react`** *(Standar resmi komponen beUI)*
* **Pustaka Motion**: **`motion` (`motion/react`)**
* **Tema Default**: **Light Mode** *(Sesuai keputusan manajemen)*

---

## 1. Filosofi & Prinsip Desain beUI

1. **beUI sebagai Sumber Kebenaran Tunggal (Single Source of Truth)**:
   Seluruh antarmuka agen, alur obrolan, status penalaran, dan tampilan alat mengacu langsung pada arsitektur komponen beUI. Tidak diperkenankan membuat komponen kustom liar jika fungsionalitas sudah disediakan oleh registri `@beui`.
2. **Keterbukaan & Transparansi Penalaran (Agentic Transparency)**:
   Proses internal agen (pembacaan brief, pencarian web, pemanggilan tool database/RAG, pelacakan eksekusi) divisualisasikan secara elegan melalui komponen pengungkapan (*disclosure*) terstruktur yang dapat diciutkan.
3. **Fisika Gerak Terukur (Physics-based Motion)**:
   Transisi dan animasi antarmuka menggunakan token fisika pegas (*spring physics*) dan kurva perlambatan tajam (`EASE_OUT`) resmi beUI, bukan animasi linier kaku.
4. **Monokromatik Bersih (No AI Slop)**:
   Menghindari gradasi warna mencolok atau efek dekoratif tanpa fungsi. Palet menggunakan kontras netral terukur berbasis HSL CSS variables.
5. **Kebijakan Bebas Emotikon (Zero-Emoji Policy)**:
   Dilarang keras menggunakan emotikon gambar/emoji pada antarmuka pengguna maupun copywriting sistem. Seluruh representasi visual memanfaatkan ikon garis presisi dari **`lucide-react`**.

---

## 2. Design Tokens

### A. Palet Warna (Color Palette Tokens)

Tema menggunakan pemetaan CSS Variables yang terikat pada elemen `:root` (Light Mode sebagai default) dan `.dark` (Dark Mode).

| Token | Light Mode (`:root` - Default) | Dark Mode (`.dark`) | Peran / Penggunaan |
| :--- | :--- | :--- | :--- |
| `--background` | `oklch(99% 0 0)` | `#151515` | Latar belakang kanvas aplikasi |
| `--foreground` | `oklch(15% 0 0)` | `oklch(96% 0 0)` | Warna teks primer |
| `--card` | `oklch(97% 0 0)` | `#1c1c1c` | Kontainer kartu, sidebar, dan panel obrolan |
| `--card-foreground` | `oklch(15% 0 0)` | `oklch(96% 0 0)` | Teks dalam kartu dan gelembung asisten |
| `--popover` | `oklch(97% 0 0)` | `#1c1c1c` | Latar belakang popover, menu konteks, dan dropdown |
| `--popover-foreground` | `oklch(15% 0 0)` | `oklch(96% 0 0)` | Teks dalam popover dan menu dropdown |
| `--primary` | `#0285f7` | `#0285f7` | Warna aksen primer, tombol aksi utama, bubble pengguna |
| `--primary-foreground` | `#ffffff` | `#ffffff` | Teks kontras pada aksi utama |
| `--secondary` | `oklch(97% 0 0)` | `#1c1c1c` | Tombol sekunder, hover item sidebar |
| `--secondary-foreground` | `oklch(15% 0 0)` | `oklch(96% 0 0)` | Teks pada elemen sekunder |
| `--muted` | `oklch(97% 0 0)` | `#1c1c1c` | Background tag kode, chip sitasi, avatar container |
| `--muted-foreground` | `oklch(50% 0 0)` | `oklch(62% 0 0)` | Subtitle, placeholder, timestamp, status |
| `--accent` | `oklch(72% 0.18 195)` | `oklch(80% 0.18 195)` | Sorotan interaktif dan seleksi aktif |
| `--accent-foreground` | `oklch(15% 0 0)` | `#151515` | Teks di atas elemen beraksen |
| `--destructive` | `oklch(62% 0.22 25)` | `oklch(62% 0.22 25)` | Status error, aksi penolakan tool approval |
| `--destructive-foreground` | `#ffffff` | `#ffffff` | Teks kontras pada status error |
| `--border` | `oklch(15% 0 0 / 0.06)` | `rgb(255 255 255 / 0.05)` | Garis tepi komponen & pembatas kartu |
| `--input` | `oklch(15% 0 0 / 0.06)` | `rgb(255 255 255 / 0.05)` | Garis batas input form dan textarea |
| `--ring` | `oklch(15% 0 0 / 0.12)` | `rgb(255 255 255 / 0.1)` | Ring fokus aksesibilitas navigasi keyboard |
| `--radius` | `0.5rem` | `0.5rem` | Radius lengkung standar sudut kartu (`var(--radius)`) |

### B. Tipografi (Typography)

* **Font Utama (Body & UI)**: Inter / UI Sans-serif (`var(--font-sans)`).
* **Font Monospace (Kode, Metadata, & Token)**: UI Monospace, SFMono-Regular, Menlo, Monaco, Consolas.

| Ukuran Token | Nilai CSS | Line Height | Penggunaan |
| :--- | :--- | :--- | :--- |
| `text-[10px]` | 10px (0.625rem) | 14px | Nomor sitasi inline, counter progress, tag status micro |
| `text-[11px]` | 11px (0.6875rem) | 16px | Keterangan sidebar, label monospace, badge outline |
| `text-xs` | 12px (0.75rem) | 18px | Isi gelembung pesan, item aktivitas agen, placeholder |
| `text-sm` | 14px (0.875rem) | 20px | Header bar, subjudul hero, label textarea |
| `text-base` | 16px (1.0rem) | 24px | Paragraf dokumen, uraian markdown panjang |
| `text-lg` | 18px (1.125rem) | 28px | Judul kartu atau modal |
| `text-3xl` s.d. `text-4xl` | 30px - 36px | 38px - 44px | Judul utama Hero Empty State (*Ask Anything*) |

### C. Jarak (Spacing Scale)

* Menggunakan skala grid kelipatan **4px**:
  * `0.5` (2px), `1` (4px), `1.5` (6px), `2` (8px), `3` (12px), `4` (16px), `6` (24px), `8` (32px), `12` (48px).
* **Sidebar**: Lebar standar `w-64` (256px).
* **Content Width**: Maksimal `max-w-3xl` (768px) untuk keterbacaan optimal alur pesan.

### D. Sudut Lengkung (Border Radius)

* `rounded-sm`: 2px (Favicon container, checkbox).
* `rounded`: 4px (Tombol aksi kecil, badge inline).
* `rounded-md`: 6px (`calc(var(--radius) - 2px)` - Menu session button, input).
* `rounded-lg`: 8px (`var(--radius)` - Kartu modul, kontainer dialog, avatar square).
* `rounded-xl`: 12px (Hero card prompt composer, pesan bubble, New chat button).
* `rounded-2xl`: 16px (ChatApp shell container, approval card container).
* `rounded-full`: 9999px (Pill quick prompts, live status indicator, connection badge).

### E. Token Gerak & Fisika beUI (`lib/ease.ts`)

beUI menggunakan konstanta fisika motion resmi untuk memastikan interaksi terasa hidup dan alami:

```typescript
// Kurva perlambatan (Easing)
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const EASE_IN_OUT = [0.77, 0, 0.175, 1] as const;
export const EASE_DRAWER = [0.32, 0.72, 0, 1] as const;
export const EASE_OUT_CSS = "cubic-bezier(0.16, 1, 0.3, 1)";

// Fisika Pegas (Springs)
export const SPRING_PRESS = { type: "spring", stiffness: 500, damping: 30, mass: 0.6 };
export const SPRING_SWAP = { type: "spring", stiffness: 460, damping: 30, mass: 0.55 };
export const SPRING_PANEL = { type: "spring", stiffness: 420, damping: 40, mass: 0.5 };
export const SPRING_LAYOUT = { type: "spring", stiffness: 360, damping: 32, mass: 0.6 };
export const SPRING_MOUSE = { stiffness: 200, damping: 15, mass: 0.3 };
export const SPRING_GLIDE = { stiffness: 700, damping: 50, mass: 0.5 };
```

---

## 3. Katalog 17 Komponen AI Agents beUI

Berdasarkan registri resmi beUI (`mcp.beui.dev`), berikut adalah 17 modul komponen spesifik agen beserta deskripsi resmi, dependensi, dan perintah instalasi shadcn CLI:

### 1. Prompt Input
* **Slug**: `prompt-input`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/prompt-input
  ```
* **Deskripsi**: Area komposer agen yang membesar otomatis (*auto-growing*) dilengkapi menu aksi prompt, pemilihan model LLM, penanganan submit keyboard (Enter / Shift+Enter), serta animasi status kirim dan stop.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 2. Citations
* **Slug**: `citations`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/citations
  ```
* **Deskripsi**: Penanda sitasi inline `[1]`, `[2]` yang dipadukan dengan koleksi referensi dokumen sumber yang dapat diciutkan (*collapsible reference disclosure*) untuk grounding jawaban agen.
* **Komponen yang Diekspor**: `<Citation />`, `<Citations />`, `<CitationList />`, `<CitationStack />`, `<CitationFavicon />`.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 3. Agent Activity
* **Slug**: `agent-activity`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/agent-activity
  ```
* **Deskripsi**: Satu aliran aktivitas adaptif untuk menampilkan proses penalaran (*reasoning*), pencarian dokumen (*searches*), pemanggilan tool, jejak eksekusi terstruktur, atau campuran kronologis.
* **Komponen yang Diekspor**: `<AgentActivity />`, `<ActivityRow />`.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 4. Agent Loading States
* **Slug**: `loading-states`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/loading-states
  ```
* **Deskripsi**: Tiga status loading terencana untuk antarmuka AI: teks status berbayang (`ThinkingShimmer`), indikator progres agen langsung (`AgentProgress`), dan frasa penalaran siklik (`ReasoningText`).
* **Dependensi**: `clsx`, `motion`, `tailwind-merge`.

### 5. Tool Result
* **Slug**: `tool-result`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/tool-result
  ```
* **Deskripsi**: Penampil eksekusi ringan untuk keluaran terminal dengan syntax-highlighting dan respons request yang menciut otomatis ke status ringkas setelah selesai.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 6. Tool Approval
* **Slug**: `tool-approval`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/tool-approval
  ```
* **Deskripsi**: Kartu izin *human-in-the-loop* untuk meninjau rincian tool, mengizinkan eksekusi sekali, mengingat izin akses, atau menolak eksekusi.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 7. Approval Card
* **Slug**: `approval-card`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/approval-card
  ```
* **Deskripsi**: Permukaan keputusan interaktif untuk persetujuan bertahap, pertanyaan pilihan tunggal/ganda, respons kustom, dan alur peninjauan multi-langkah.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 8. Streaming Response
* **Slug**: `streaming-response`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/streaming-response
  ```
* **Deskripsi**: Permukaan respons stabil dengan tombol aksi saat selesai (salin, regenerasi), konten terformat, dan ringkasan sumber yang dapat diperluas.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 9. Todo List
* **Slug**: `todo-list`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/todo-list
  ```
* **Deskripsi**: Rencana tugas agen yang dapat diciutkan dengan penanda status bertransformasi (*morphing status marks*), penghitung tugas selesai, metadata ringkas, dan pembaruan daftar yang halus.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 10. Message Bubble
* **Slug**: `message-bubble`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/message-bubble
  ```
* **Deskripsi**: Permukaan obrolan terfokus dengan penyesuaian nada visual, perataan independen (user vs assistant), pengelompokan pesan, dan dukungan tombol interaktif.
* **Dependensi**: `clsx`, `tailwind-merge`.

### 11. Message
* **Slug**: `message`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/message
  ```
* **Deskripsi**: Primitif percakapan modular untuk baris pesan, avatar, metadata pengirim, penanda live, dan animasi pop-up pada baris yang baru terkirim.
* **Dependensi**: `clsx`, `motion`, `tailwind-merge`.

### 12. Message Scroller
* **Slug**: `message-scroller`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/message-scroller
  ```
* **Deskripsi**: Viewport percakapan cerdas yang otomatis mengikuti keluaran streaming pada tepi bawah dan melepas kendali gulir saat pengguna menggulir ke atas untuk membaca.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 13. Code Block
* **Slug**: `code-block`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/code-block
  ```
* **Deskripsi**: Permukaan kode dengan syntax highlighting, nomor baris, penyorotan baris terfokus, penyalinan dengan umpan balik visual, dan pembaruan streaming yang stabil.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 14. File Diff
* **Slug**: `file-diff`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/file-diff
  ```
* **Deskripsi**: Penampil perubahan berkas dengan syntax highlighting, nomor baris, penghitung perubahan langsung (+/-), dan penciutan otomatis saat selesai.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 15. Image Generation
* **Slug**: `image-generation`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/image-generation
  ```
* **Deskripsi**: Permukaan generasi gambar stabil yang bertransisi dari antrean tugas, proses pemurnian bertahap, hingga hasil jadi tanpa pergeseran tata letak (*layout shift*).
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 16. AI Sidebar
* **Slug**: `ai-sidebar`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/ai-sidebar
  ```
* **Deskripsi**: Sidebar ruang kerja AI yang dapat diciutkan untuk navigasi folder, proyek dokumen, riwayat sesi, dan bookmark dengan dukungan navigasi keyboard dan rename inline.
* **Dependensi**: `clsx`, `lucide-react`, `motion`, `tailwind-merge`.

### 17. Chat App
* **Slug**: `chat-app`
* **Instalasi**:
  ```bash
  npx shadcn add @beui/chat-app
  ```
* **Deskripsi**: Shell aplikasi percakapan agen lengkap yang menggabungkan navigasi, pesan, streaming, rencana todo, approvals, tool result, kode, diffs, sitasi sumber, dan prompt input.
* **Dependensi**: Seluruh komponen AI Agent di atas.

---

## 4. Perilaku Lintas Tema, Responsivitas, & Aksesibilitas

### A. Penanganan Tema (Light Theme sebagai Default)
* Sesuai keputusan manajemen perusahaan, **Light Mode adalah tema default sistem** (`defaultTheme="light"`).
* Variabel CSS diatur secara semantik sehingga pergantian ke Dark Mode tidak memerlukan perubahan nama class Tailwind (`bg-background`, `text-foreground`, `border-border` otomatis beradaptasi).
* Komponen `ThemeToggle` menggunakan beUI Motion `ThemeToggle` (`@/components/motion/theme-toggle`) dengan animasi View Transition (`variant="circle"`), ikon dinamis `ActionSwapIcon` (`Sun` dan `Moon`), dan disematkan secara terpusat di footer sidebar di samping profil pengguna tanpa duplikasi di bilah navigasi atas.

### B. Aksesibilitas Gerak (`prefers-reduced-motion`)
* Seluruh komponen beUI mengintegrasikan hook `useReducedMotion()`.
* Jika pengguna mengaktifkan preferensi *Reduced Motion* pada sistem operasi:
  * Seluruh durasi animasi spring di-bypass (`duration: 0`).
  * Elemen transisi clip-path dan transform langsung berada pada status akhir tanpa animasi gerak.

### C. Aksesibilitas Keyboard & Screen Reader
* Elemen interaktif (`button`, `input`, `textarea`, `a`) memiliki ring fokus eksplisit `focus-visible:ring-2 focus-visible:ring-ring`.
* Status aktif agen (seperti teks reasoning atau streaming) menggunakan penanda `role="status"` atau `aria-live="polite"` agar dapat dibaca oleh pembaca layar.

---

## 5. Sumber Kebenaran dalam Kode & Panduan Implementasi Personel / AI

### File Sumber Kebenaran dalam Repositori:
1. `frontend/components.json`: Konfigurasi shadcn dengan `"style": "base-mira"` dan `"iconLibrary": "lucide"`.
2. `frontend/app/globals.css`: Definisi token warna CSS (`:root` dan `.dark`).
3. `frontend/tailwind.config.js`: Pemetaan variabel CSS ke utility class Tailwind (`var(--color)`).
4. `frontend/src/lib/ease.ts`: Konstanta kurva easing dan spring physics resmi beUI.
5. `frontend/src/components/agents/`: Direktori penyimpanan komponen AI Agents resmi dari `@beui`.
6. `frontend/src/components/motion/`: Direktori komponen pondasi motion beUI (`button`, `theme-toggle`, `popover-morph`, `action-swap`, `preview-rail`, `select`, `text-shimmer`).

### Aturan Ketat Implementasi untuk Pengembang & AI Agent:
1. **GUNAKAN PERINTAH SHADCN RESMI UNTUK MENAMBAH KOMPONEN**:
   Selalu gunakan format:
   ```bash
   npx shadcn add @beui/<slug>
   ```
2. **GUNAKAN `lucide-react` UNTUK SEMUA IKON**:
   Dilarang mengimpor ikon dari pustaka lain (seperti `hugeicons-react`, `font-awesome`, dll.). beUI secara baku mengandalkan `lucide-react`.
3. **DILARANG MENGGUNAKAN EMOTIKON/EMOJI**:
   Tidak boleh ada emoji visual (seperti robot, roket, api, atau gear) di file kode, teks UI, maupun copywriting.
4. **PATUHI CLEAN ARCHITECTURE**:
   Komponen UI hanya berfungsi sebagai layer presentasi. Logika pemanggilan endpoint backend dan penanganan stream SSE tetap berada di `src/infrastructure/` dan diorkestrasi oleh `src/interface-adapters/controllers/`.
