"use client";
import Logo from "./Logo";

/**
 * Loading screen terpusat — dipakai di SETIAP proses ber-tunda agar user
 * tidak pernah menatap layar mati:
 *  - `AppSplash`     : startup aplikasi (backend belum siap / data pertama).
 *  - `Spinner`       : indikator kecil reusable (tombol, baris, overlay).
 *  - `ThinkingDots`  : "Model sedang berpikir…" sebelum token pertama.
 *  - `BusyOverlay`   : overlay semi-transparan untuk area yang sedang dimuat.
 */

export function Spinner({ size = 16, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={`animate-spin ${className}`}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/** Tiga titik berdenyut — status "proses berlangsung". */
export function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block h-1 w-1 animate-bounce rounded-full bg-current"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: "0.9s" }}
        />
      ))}
    </span>
  );
}

/** Label "Model sedang berpikir…" — tampil sebelum token pertama tiba. */
export function ThinkingIndicator({ label = "Model sedang berpikir" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] text-zinc-500">
      <Spinner size={12} className="text-accent" />
      {label}
      <ThinkingDots />
    </span>
  );
}

/**
 * Layar penuh saat aplikasi memulai: sampai backend menjawab + percakapan,
 * settings, dan health selesai dimuat — atau layar error bila backend mati.
 */
export function AppSplash({
  error = null,
  onRetry,
}: {
  error?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div
      data-testid="app-splash"
      className="flex h-screen w-full flex-col items-center justify-center gap-4 bg-[#f7f7f8] text-zinc-900"
    >
      <div className="flex items-center gap-2.5">
        <Logo size={30} />
        <span className="text-lg font-semibold tracking-tight">Ask Anything</span>
      </div>
      {error ? (
        <div className="flex max-w-md flex-col items-center gap-3 px-6 text-center">
          <p className="text-sm font-medium text-rose-600">
            Backend tidak bisa dihubungi
          </p>
          <p className="whitespace-pre-line text-xs leading-5 text-zinc-500">
            {error}
            {"\n"}Pastikan server backend berjalan (python run.py atau
            uvicorn di port 8000), lalu coba lagi.
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-900 bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-800"
            >
              <Spinner size={13} />
              Coba lagi
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2.5">
          <Spinner size={26} className="text-accent" />
          <p className="flex items-center gap-1.5 text-sm text-zinc-500">
            Menyiapkan Ask Anything…
            <ThinkingDots />
          </p>
          <p className="text-[11px] text-zinc-400">
            memuat percakapan, settings &amp; status model
          </p>
        </div>
      )}
    </div>
  );
}

/** Overlay ringan untuk area yang sedang diproses (mis. membuka riwayat). */
export function BusyOverlay({
  label = "Memuat…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      data-testid="busy-overlay"
      className={`pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-white/60 backdrop-blur-[1px] ${className}`}
    >
      <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-2.5 shadow-card">
        <Spinner size={16} className="text-accent" />
        <span className="flex items-center gap-1.5 text-[13px] text-zinc-600">
          {label}
          <ThinkingDots />
        </span>
      </div>
    </div>
  );
}
