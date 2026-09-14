/* Fullscreen untuk kanvas visualisasi — dengan fallback yang jujur.
   `requestFullscreen()` bisa ditolak (iframe tanpa `allow="fullscreen"`,
   browser tanpa dukungan, atau gesture bukan-user). Dalam semua kasus itu UI
   pindah ke "focus mode": kartu di-position fixed inset-0 sehingga kanvas
   tetap penuh layar, dan status dilaporkan apa adanya (`mode`). */
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";

export type FullscreenMode = "native" | "fallback" | null;

export function fullscreenSupported(el?: Element | null): boolean {
  if (typeof document === "undefined") return false;
  const target = el ?? document.documentElement;
  return typeof (target as HTMLElement).requestFullscreen === "function";
}

export interface FullscreenState {
  ref: RefObject<HTMLDivElement | null>;
  /** true = tampil immersive (native ATAU fallback focus mode). */
  active: boolean;
  mode: FullscreenMode;
  /** Pesan teknis kenapa fallback dipakai (ditampilkan sebagai tooltip). */
  notice: string | null;
  toggle: () => void;
  exit: () => void;
}

export function useFullscreen(): FullscreenState {
  const ref = useRef<HTMLDivElement | null>(null);
  const [active, setActive] = useState(false);
  const [mode, setMode] = useState<FullscreenMode>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Sinkron dengan perubahan native (mis. user menekan Esc).
  useEffect(() => {
    const onChange = () => {
      const isFs = document.fullscreenElement === ref.current;
      if (isFs) {
        setActive(true);
        setMode("native");
      } else if (mode === "native") {
        setActive(false);
        setMode(null);
      }
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, [mode]);

  const exit = useCallback(() => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => undefined);
    }
    setActive(false);
    setMode(null);
    setNotice(null);
  }, []);

  const toggle = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    if (active) {
      exit();
      return;
    }
    if (!fullscreenSupported(el)) {
      setNotice("Fullscreen API tidak tersedia di browser ini — memakai focus mode.");
      setActive(true);
      setMode("fallback");
      return;
    }
    el.requestFullscreen()
      .then(() => {
        setNotice(null);
        setActive(true);
        setMode("native");
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setNotice(`Fullscreen ditolak (${msg.slice(0, 60)}) — memakai focus mode.`);
        setActive(true);
        setMode("fallback");
      });
  }, [active, exit]);

  // Esc selalu keluar, juga dari focus mode (native fullscreen sudah keluar
  // sendiri lewat browser, tapi state React harus ikut).
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") exit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, exit]);

  return { ref, active, mode, notice, toggle, exit };
}
