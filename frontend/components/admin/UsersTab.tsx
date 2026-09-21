"use client";
/* Tab Users — kelola akun & peran (admin | member).
 *
 *   * admin melihat daftar akun + jumlah task yang ditugaskan + sesi aktif,
 *   * buat akun baru (member/admin) dengan password awal,
 *   * ubah nama/peran/status aktif, dan
 *   * **reset password** — password pemilik yang lupa diganti dari sini; semua
 *     sesi user itu diputus supaya password baru benar-benar berlaku.
 */
import { useCallback, useEffect, useState } from "react";
import {
  adminCreateUser,
  adminDeleteUser,
  adminResetUserPassword,
  adminUpdateUser,
  adminUsers,
} from "@/lib/api";
import type { AdminUser, Role } from "@/lib/types";
import { Card, fmtTime } from "./ui";

const ROLE_STYLE: Record<string, string> = {
  admin: "border-indigo-200 bg-indigo-50 text-indigo-700",
  member: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

interface Draft {
  username: string;
  name: string;
  password: string;
  role: Role;
  must_change_password: boolean;
}

const EMPTY_DRAFT: Draft = {
  username: "",
  name: "",
  password: "",
  role: "member",
  must_change_password: true,
};

export default function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>(["admin", "member"]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await adminUsers("");
      setUsers(data.users);
      if (data.roles?.length) setRoles(data.roles);
      setLabels(data.role_labels || {});
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      await load();
      setNotice(ok);
    } catch (e) {
      const text = String(e);
      setError(
        text.includes("400")
          ? `Ditolak server: kemungkinan username sudah dipakai / password terlalu pendek / admin terakhir tidak boleh dihapus. (${text})`
          : text
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
      <Card
        title="Akun & peran"
        subtitle="Role member = playground (teks/diagram/RAG, model OpenAI) + task yang ditugaskan. Role admin = seluruh pipeline, model offline, dan konsol ini."
        right={
          <button
            onClick={() => setCreating((v) => !v)}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:brightness-95"
          >
            {creating ? "Tutup form" : "+ Akun baru"}
          </button>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-zinc-200 text-[11px] uppercase tracking-wide text-zinc-400">
                <th className="py-2 pr-2 font-medium">Akun</th>
                <th className="py-2 pr-2 font-medium">Peran</th>
                <th className="py-2 pr-2 font-medium">Task</th>
                <th className="py-2 pr-2 font-medium">Sesi</th>
                <th className="py-2 pr-2 font-medium">Terakhir masuk</th>
                <th className="py-2 font-medium">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-zinc-100 last:border-0">
                  <td className="py-2 pr-2">
                    <span className="block font-medium text-zinc-800">
                      {u.name || u.username}
                    </span>
                    <span className="font-mono text-[11px] text-zinc-400">
                      {u.username}
                    </span>
                    {!u.active && (
                      <span className="ml-1 rounded bg-rose-50 px-1 text-[10.5px] text-rose-600">
                        nonaktif
                      </span>
                    )}
                    {u.must_change_password && (
                      <span className="ml-1 rounded bg-amber-50 px-1 text-[10.5px] text-amber-700">
                        wajib ganti password
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-2">
                    <select
                      aria-label={`Peran ${u.username}`}
                      value={u.role}
                      disabled={busy}
                      onChange={(e) =>
                        run(
                          () =>
                            adminUpdateUser("", u.id, {
                              role: e.target.value as Role,
                            }),
                          `Peran ${u.username} → ${labels[e.target.value] || e.target.value}.`
                        )
                      }
                      className={`rounded-lg border px-2 py-1 text-[11.5px] font-medium ${
                        ROLE_STYLE[u.role] || ROLE_STYLE.member
                      }`}
                    >
                      {roles.map((r) => (
                        <option key={r} value={r}>
                          {labels[r] || r}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 pr-2 text-zinc-500">
                    {u.tasks_done ?? 0}/{u.tasks_total ?? 0}
                  </td>
                  <td className="py-2 pr-2 text-zinc-500">{u.sessions ?? 0}</td>
                  <td className="py-2 pr-2 text-[11.5px] text-zinc-400">
                    {u.last_login ? fmtTime(u.last_login) : "belum pernah"}
                  </td>
                  <td className="py-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <button
                        onClick={() => {
                          setResetFor(resetFor === u.id ? null : u.id);
                          setResetPw("");
                        }}
                        className="rounded-lg border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-600 hover:bg-zinc-50"
                      >
                        Reset password
                      </button>
                      <button
                        onClick={() =>
                          run(
                            () =>
                              adminUpdateUser("", u.id, { active: !u.active }),
                            `${u.username} ${u.active ? "dinonaktifkan" : "diaktifkan"}.`
                          )
                        }
                        className="rounded-lg border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-600 hover:bg-zinc-50"
                      >
                        {u.active ? "Nonaktifkan" : "Aktifkan"}
                      </button>
                      <button
                        onClick={() => {
                          if (
                            typeof window !== "undefined" &&
                            !window.confirm(
                              `Hapus akun ${u.username}? Task yang pernah ditugaskan tetap ada di papan.`
                            )
                          )
                            return;
                          run(
                            () => adminDeleteUser("", u.id),
                            `Akun ${u.username} dihapus.`
                          );
                        }}
                        className="rounded-lg border border-rose-200 px-2 py-1 text-[11px] font-medium text-rose-600 hover:bg-rose-50"
                      >
                        Hapus
                      </button>
                    </div>

                    {resetFor === u.id && (
                      <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50/70 p-2">
                        <p className="text-[11px] text-amber-800">
                          Password baru untuk <b>{u.username}</b> — semua sesinya
                          diputus. Sampaikan lewat jalur aman, lalu minta ia
                          menggantinya di Profil.
                        </p>
                        <div className="mt-1.5 flex items-center gap-2">
                          <input
                            value={resetPw}
                            onChange={(e) => setResetPw(e.target.value)}
                            placeholder="password baru (min. 6 karakter)"
                            className="w-44 rounded-lg border border-amber-200 px-2 py-1 text-[12px]"
                          />
                          <button
                            disabled={busy || resetPw.length < 6}
                            onClick={() =>
                              run(
                                () =>
                                  adminResetUserPassword("", u.id, resetPw, true),
                                `Password ${u.username} direset — sesi lain diputus.`
                              )
                            }
                            className="rounded-lg bg-amber-600 px-2.5 py-1 text-[11px] font-medium text-white disabled:opacity-40"
                          >
                            Simpan password
                          </button>
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {notice && (
          <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
            {notice}
          </p>
        )}
        {error && (
          <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
            {error}
          </p>
        )}
      </Card>

      <div className="space-y-4">
        {creating && (
          <Card title="Akun baru" subtitle="Password awal wajib diganti oleh pemiliknya saat login pertama (opsional).">
            <div className="grid gap-2">
              <input
                value={draft.username}
                onChange={(e) =>
                  setDraft({ ...draft, username: e.target.value.trim() })
                }
                placeholder="username (mis. intern4)"
                className="rounded-lg border border-zinc-200 px-3 py-2 text-[13px]"
              />
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="nama tampilan (mis. Intern Empat)"
                className="rounded-lg border border-zinc-200 px-3 py-2 text-[13px]"
              />
              <input
                type="password"
                value={draft.password}
                onChange={(e) => setDraft({ ...draft, password: e.target.value })}
                placeholder="password awal (min. 6 karakter)"
                className="rounded-lg border border-zinc-200 px-3 py-2 text-[13px]"
              />
              <div className="flex items-center gap-2">
                <select
                  value={draft.role}
                  onChange={(e) =>
                    setDraft({ ...draft, role: e.target.value as Role })
                  }
                  className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-[13px]"
                >
                  {roles.map((r) => (
                    <option key={r} value={r}>
                      {labels[r] || r}
                    </option>
                  ))}
                </select>
                <label className="flex items-center gap-1.5 text-[11.5px] text-zinc-600">
                  <input
                    type="checkbox"
                    checked={draft.must_change_password}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        must_change_password: e.target.checked,
                      })
                    }
                  />
                  wajib ganti password
                </label>
              </div>
              <button
                disabled={
                  busy ||
                  draft.username.length < 3 ||
                  draft.password.length < 6
                }
                onClick={async () => {
                  await run(
                    () => adminCreateUser("", { ...draft }),
                    `Akun ${draft.username} dibuat.`
                  );
                  setDraft(EMPTY_DRAFT);
                  setCreating(false);
                }}
                className="rounded-lg bg-zinc-900 px-3 py-2 text-[13px] font-medium text-white disabled:opacity-40"
              >
                Buat akun
              </button>
            </div>
          </Card>
        )}

        <Card title="Aturan yang ditegakkan server" subtitle="UI hanya menyembunyikan; keputusan akhir tetap di backend.">
          <ul className="space-y-1.5 text-[12.5px] leading-6 text-zinc-600">
            <li>• Member: playground teks/diagram/RAG dengan provider <b>OpenAI</b> — mode gambar/PPT/deep research, setelan provider, dan model offline ditolak (403).</li>
            <li>• Member hanya melihat task yang ditugaskan kepadanya, dan boleh memindahkan status/menulis komentar.</li>
            <li>• Password bisa diganti sendiri di Profil (butuh password lama) atau direset admin di tabel ini.</li>
            <li>• Menonaktifkan akun = login langsung ditolak (401) tanpa membocorkan alasan ke luar.</li>
            <li>• Admin terakhir tidak bisa dihapus/diturunkan agar konsol tidak terkunci.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
