"use client";
/* Halaman /login — masuk dengan akun admin atau member.
 *
 *  * mode `open` (demo/test): backend tidak mewajibkan login, jadi kredensial
 *    awal ditampilkan sebagai petunjuk dan form tetap bisa dipakai,
 *  * mode `required` (default): tanpa akun yang sah tidak ada halaman aplikasi
 *    yang bisa dibuka — ini pintu masuknya.
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import Logo from "./Logo";
import { authBootstrap, authLogin } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuthBootstrap } from "@/lib/types";

export default function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<AuthBootstrap | null>(null);

  const next = params.get("next") || "/";

  useEffect(() => {
    authBootstrap()
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await authLogin(username.trim(), password);
      await refresh();
      router.replace(next.startsWith("/") ? next : "/");
    } catch (err) {
      const text = String(err);
      setError(
        text.includes("401")
          ? "Username atau password salah."
          : text.includes("429")
            ? "Terlalu banyak percobaan login. Tunggu sebentar lalu coba lagi."
            : `Tidak bisa masuk: ${text}`
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-[#f7f7f8] px-5 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <Logo />
          <span className="text-[15px] font-semibold tracking-tight text-zinc-900">
            ask-anything
          </span>
        </div>

        <form
          onSubmit={submit}
          className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
        >
          <h1 className="text-lg font-semibold text-zinc-900">Masuk</h1>
          <p className="mt-1 text-[12.5px] leading-5 text-zinc-500">
            Member memakai <b>playground</b> (mode teks, diagram, RAG) dengan model
            OpenAI; pengaturan provider &amp; model offline hanya untuk admin.
          </p>

          <label className="mt-4 block text-[12px] font-medium text-zinc-600">
            Username
            <input
              data-testid="login-username"
              value={username}
              autoComplete="username"
              autoFocus
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-accent-ring focus:ring-2 focus:ring-accent-soft"
              placeholder="mis. intern1"
            />
          </label>

          <label className="mt-3 block text-[12px] font-medium text-zinc-600">
            Password
            <input
              data-testid="login-password"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-accent-ring focus:ring-2 focus:ring-accent-soft"
              placeholder="••••••••"
            />
          </label>

          {error && (
            <p
              data-testid="login-error"
              className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            data-testid="login-submit"
            disabled={busy || !username || !password}
            className="mt-4 w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition hover:brightness-95 disabled:opacity-50"
          >
            {busy ? "Masuk…" : "Masuk"}
          </button>

          {info?.demo && info.credentials?.length ? (
            <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-3 text-[11.5px] leading-5 text-sky-800">
              <p className="font-medium">Mode demo (ASK_AUTH_MODE=open)</p>
              <p>Akun contoh — ganti password setelah masuk:</p>
              <ul className="mt-1 font-mono">
                {info.credentials.map((c) => (
                  <li key={c.username}>
                    {c.username} / {c.password}{" "}
                    <span className="text-sky-600">({c.role})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 text-[11.5px] leading-5 text-zinc-400">
              {info?.seeded
                ? "Belum ada akun di server ini — admin pertama dibuat otomatis dari ASK_ADMIN_PASSWORD."
                : "Lupa password? Minta admin mereset lewat konsol Admin → Users."}
            </p>
          )}
        </form>

        <p className="mt-4 text-center text-[11px] text-zinc-400">
          Sesi disimpan di cookie HttpOnly (`ask_session`) — bukan localStorage.
        </p>
      </div>
    </div>
  );
}
