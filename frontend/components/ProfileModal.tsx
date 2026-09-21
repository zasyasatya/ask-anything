"use client";
/* Modal Profil — yang bisa dilakukan **semua** peran:
 *   * ganti nama tampilan,
 *   * ganti password sendiri (wajib tahu password lama; semua sesi lain diputus).
 * Setelan provider/model tetap khusus admin (komponen SettingsModal).
 */
import { useState } from "react";
import { authChangePassword, authUpdateProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ProfileModal({ onClose }: { onClose: () => void }) {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await authUpdateProfile(name.trim());
      await refresh();
      setNotice("Nama diperbarui.");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setNotice(null);
    setError(null);
    if (next !== confirm) {
      setError("Konfirmasi password tidak sama.");
      return;
    }
    setBusy(true);
    try {
      await authChangePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setNotice("Password diganti — sesi lain diputus.");
    } catch (err) {
      const text = String(err);
      setError(
        text.includes("403")
          ? "Password lama salah."
          : text.includes("400")
            ? "Password minimal 6 karakter."
            : `Gagal mengganti password: ${text}`
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-900/40 p-4 backdrop-blur-sm">
      <div
        data-testid="profile-modal"
        className="w-full max-w-md overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Profil</h2>
            <p className="text-[11.5px] text-zinc-500">
              {user?.username} ·{" "}
              <span className="font-medium">
                {user?.role_label || user?.role}
              </span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-50"
          >
            Tutup
          </button>
        </div>

        <form onSubmit={saveName} className="border-b border-zinc-100 px-5 py-4">
          <label className="block text-[12px] font-medium text-zinc-600">
            Nama tampilan
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="mt-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-40"
          >
            Simpan nama
          </button>
        </form>

        <form onSubmit={savePassword} className="px-5 py-4">
          <p className="text-[12px] font-medium text-zinc-700">Ganti password</p>
          <div className="mt-2 grid gap-2">
            <input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              placeholder="Password lama"
              autoComplete="current-password"
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm"
            />
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              placeholder="Password baru (min. 6 karakter)"
              autoComplete="new-password"
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm"
            />
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Ulangi password baru"
              autoComplete="new-password"
              className="w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm"
            />
          </div>

          {error && (
            <p className="mt-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
              {error}
            </p>
          )}
          {notice && (
            <p className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !current || next.length < 6}
            className="mt-3 w-full rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {busy ? "Menyimpan…" : "Ganti password"}
          </button>
          <p className="mt-2 text-[11px] leading-5 text-zinc-400">
            Admin bisa mereset password lewat konsol <b>Admin → Users</b> bila
            pemiliknya lupa.
          </p>
        </form>
      </div>
    </div>
  );
}
