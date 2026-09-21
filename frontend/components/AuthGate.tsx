"use client";
/* Penjaga halaman: pastikan user sudah login sebelum UI dirender.
 *
 *  * `ASK_AUTH_MODE=open` (demo/test) → backend membalas user anonim admin,
 *    halaman langsung jalan tanpa login,
 *  * `required` (default) → tanpa sesi, browser diarahkan ke `/login?next=…`
 *    sehingga setelah masuk user kembali ke halaman yang dituju.
 */
import { useRouter, usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Spinner } from "./LoadingScreen";
import { useAuth } from "@/lib/auth";

export default function AuthGate({
  children,
  requireAdmin = false,
}: {
  children: ReactNode;
  /** Halaman yang hanya untuk role admin (mis. /admin). */
  requireAdmin?: boolean;
}) {
  const { user, capabilities, anonymous, loading, error, refresh } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading || user || anonymous) return;
    const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
    router.replace(`/login${next}`);
  }, [loading, user, anonymous, router, pathname]);

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f7f8] text-sm text-zinc-500">
        <span className="flex items-center gap-2">
          <Spinner size={14} className="text-zinc-400" />
          Memeriksa sesi login…
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f7f8] px-6">
        <div className="max-w-md rounded-xl border border-rose-200 bg-white p-5 text-sm">
          <p className="font-medium text-rose-700">Backend tidak bisa dihubungi</p>
          <p className="mt-1 text-zinc-600">{error}</p>
          <button
            onClick={() => refresh()}
            className="mt-3 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white"
          >
            Coba lagi
          </button>
        </div>
      </div>
    );
  }

  if (requireAdmin && !(capabilities?.is_admin ?? anonymous)) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f7f8] px-6">
        <div className="max-w-md rounded-xl border border-amber-200 bg-white p-5 text-sm">
          <p className="font-medium text-amber-700">Halaman ini khusus admin</p>
          <p className="mt-1 text-zinc-600">
            Akun Anda berperan <b>{capabilities?.role || "member"}</b>. Konsol admin
            mengatur pipeline, memori, model offline, dan akun pengguna —
            minta admin bila perlu perubahan.
          </p>
          <div className="mt-3 flex gap-2">
            <a
              href="/"
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white"
            >
              ← Kembali ke playground
            </a>
            <a
              href="/internship"
              className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700"
            >
              Papan internship
            </a>
          </div>
        </div>
      </div>
    );
  }

  if (!user && !anonymous) {
    // Redirect sedang berjalan (satu render); jangan tampilkan UI aplikasi.
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f7f8] text-sm text-zinc-400">
        Mengalihkan ke halaman login…
      </div>
    );
  }

  return <>{children}</>;
}
