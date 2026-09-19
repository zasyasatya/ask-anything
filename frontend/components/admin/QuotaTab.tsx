"use client";
/* Tab Kuota — monitoring & manage pipeline batas token per end user.

   Dua lapis yang ditampilkan di sini:
     1. Kebijakan global (berlaku untuk semua user) — dari policy admin.
     2. Override per user — menang atas kebijakan global; 0 = tanpa batas,
        kosong = ikut kebijakan global.

   Kolom "Ditolak" memperlihatkan siapa yang benar-benar terkena limit, bukan
   hanya angka batasnya: tanpa itu admin tidak bisa tahu apakah batasnya
   terlalu ketat. */
import { useState } from "react";
import {
  adminClearQuotaLimit,
  adminResetQuota,
  adminSetQuotaLimit,
  adminUpdatePolicy,
  readAdminToken,
} from "@/lib/api";
import type { FullPolicy, QuotaDashboard, QuotaUserRow } from "@/lib/types";
import { Card, Stat, Toggle, fmtTime } from "./ui";

function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("id-ID");
}

/** Batas 0 berarti tanpa batas — bedakan dari "habis" agar tidak menyesatkan. */
function limitLabel(limit: number): string {
  return limit > 0 ? fmtNum(limit) : "∞";
}

function usageBar(used: number, limit: number): {
  pct: number;
  tone: string;
} {
  if (limit <= 0) return { pct: 0, tone: "bg-zinc-300" };
  const pct = Math.min(100, Math.round((used / limit) * 100));
  const tone =
    pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-emerald-500";
  return { pct, tone };
}

export default function QuotaTab({
  data,
  policy,
  onPolicyChange,
  onChanged,
}: {
  data: QuotaDashboard | null;
  policy: FullPolicy;
  onPolicyChange: (p: FullPolicy) => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<{
    daily_tokens: string;
    weekly_tokens: string;
    daily_requests: string;
    note: string;
  }>({ daily_tokens: "", weekly_tokens: "", daily_requests: "", note: "" });

  const quota = policy.quota;

  async function patchPolicy(patch: Partial<FullPolicy["quota"]>) {
    setBusy(true);
    setNote(null);
    try {
      const next = await adminUpdatePolicy(readAdminToken(), { quota: patch });
      onPolicyChange(next);
      setNote("Kebijakan kuota disimpan.");
      onChanged();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  function startEdit(row: QuotaUserRow) {
    setEditing(row.user_key);
    const own = row.limits.source === "override";
    setDraft({
      daily_tokens: own ? String(row.limits.daily_tokens) : "",
      weekly_tokens: own ? String(row.limits.weekly_tokens) : "",
      daily_requests: own ? String(row.limits.daily_requests) : "",
      note: row.limits.note || "",
    });
  }

  async function saveOverride(userKey: string) {
    setBusy(true);
    setNote(null);
    try {
      const num = (v: string) =>
        v.trim() === "" ? null : Math.max(0, Number(v));
      await adminSetQuotaLimit(readAdminToken(), userKey, {
        daily_tokens: num(draft.daily_tokens),
        weekly_tokens: num(draft.weekly_tokens),
        daily_requests: num(draft.daily_requests),
        note: draft.note,
      });
      setEditing(null);
      setNote(`Batas khusus untuk ${userKey} disimpan.`);
      onChanged();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setNote(null);
    try {
      await fn();
      setNote(message);
      onChanged();
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  const ov = data?.overview;

  return (
    <div className="space-y-4">
      {note && (
        <p className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-[13px] text-zinc-600">
          {note}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Token hari ini"
          value={fmtNum(ov?.today.tokens ?? 0)}
          hint={`${fmtNum(ov?.today.runs ?? 0)} run · ${ov?.today.day_key ?? ""}`}
          tone="indigo"
        />
        <Stat
          label="Token pekan ini"
          value={fmtNum(ov?.this_week.tokens ?? 0)}
          hint={`${fmtNum(ov?.this_week.runs ?? 0)} run · ${
            ov?.this_week.week_key ?? ""
          }`}
        />
        <Stat
          label="End user"
          value={fmtNum(ov?.users ?? 0)}
          hint={`${fmtNum(ov?.overrides ?? 0)} punya batas khusus`}
        />
        <Stat
          label="Ditolak hari ini"
          value={fmtNum(ov?.blocked_today ?? 0)}
          hint="request yang kena limit"
          tone={(ov?.blocked_today ?? 0) > 0 ? "amber" : "zinc"}
        />
      </div>

      <Card
        title="Kebijakan kuota global"
        subtitle="Berlaku untuk semua end user. Nilai 0 = tanpa batas. Periode memakai kalender, jadi reset otomatis tiap tengah malam (harian) dan Senin (mingguan)."
      >
        <div className="space-y-3">
          <Toggle
            checked={quota.enabled}
            onChange={(v) => patchPolicy({ enabled: v })}
            label="Aktifkan pembatasan kuota"
            hint="Dimatikan = pemakaian tidak dicatat sebagai batas (tetap direkam untuk statistik)."
          />
          <Toggle
            checked={quota.block_on_exceed}
            onChange={(v) => patchPolicy({ block_on_exceed: v })}
            label="Blokir saat kuota habis"
            hint="Dimatikan = mode pemantauan: request tetap dilayani tetapi kelebihannya dilaporkan. Berguna untuk menakar batas sebelum diberlakukan."
          />
          <div className="grid gap-3 sm:grid-cols-3">
            {(
              [
                ["daily_tokens", "Token / hari"],
                ["weekly_tokens", "Token / pekan"],
                ["daily_requests", "Permintaan / hari"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="block">
                <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                  {label}
                </span>
                <input
                  type="number"
                  min={0}
                  defaultValue={quota[key]}
                  disabled={busy}
                  onBlur={(e) => {
                    const v = Math.max(0, Number(e.target.value));
                    if (v !== quota[key]) patchPolicy({ [key]: v });
                  }}
                  className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px] text-zinc-700 focus:border-accent focus:outline-none"
                />
              </label>
            ))}
          </div>
        </div>
      </Card>

      {ov && (ov.by_provider.length > 0 || ov.by_mode.length > 0) && (
        <Card
          title="Pemakaian menurut provider & mode"
          subtitle="Dari seluruh riwayat — membantu menentukan di mana token habis."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {([
              ["Provider", ov.by_provider.map((r) => [r.provider, r.tokens, r.runs] as const)],
              ["Mode", ov.by_mode.map((r) => [r.mode, r.tokens, r.runs] as const)],
            ] as const).map(([title, rows]) => (
              <div key={title}>
                <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-zinc-400">
                  {title}
                </p>
                <ul className="space-y-1">
                  {rows.length === 0 && (
                    <li className="text-[13px] text-zinc-400">belum ada data</li>
                  )}
                  {rows.map(([name, tokens, runs]) => (
                    <li
                      key={name || "—"}
                      className="flex items-baseline justify-between gap-2 text-[13px]"
                    >
                      <span className="text-zinc-600">{name || "(kosong)"}</span>
                      <span className="text-zinc-400">
                        {fmtNum(tokens)} token · {fmtNum(runs)} run
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card
        title="End user & pemakaiannya"
        subtitle="Identitas diambil dari header X-User-Id; pemanggil tanpa header dicatat sebagai ip:<alamat>."
      >
        {!data?.users.length ? (
          <p className="text-[13px] text-zinc-500">
            Belum ada pemakaian tercatat. Angka muncul otomatis setelah ada chat
            yang berjalan.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="text-[11.5px] uppercase tracking-wide text-zinc-400">
                  <th className="py-2 pr-3 font-medium">End user</th>
                  <th className="py-2 pr-3 font-medium">Hari ini</th>
                  <th className="py-2 pr-3 font-medium">Pekan ini</th>
                  <th className="py-2 pr-3 font-medium">Batas</th>
                  <th className="py-2 pr-3 font-medium">Terakhir</th>
                  <th className="py-2 font-medium">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((row) => {
                  const bar = usageBar(row.day_tokens, row.limits.daily_tokens);
                  const isEditing = editing === row.user_key;
                  return (
                    <tr
                      key={row.user_key}
                      className="border-t border-zinc-100 align-top"
                    >
                      <td className="py-2.5 pr-3">
                        <span className="font-medium text-zinc-700">
                          {row.user_key}
                        </span>
                        {row.over_limit && (
                          <span className="ml-1.5 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10.5px] font-medium text-red-600">
                            kuota habis
                          </span>
                        )}
                        {row.limits.source === "override" && (
                          <span className="ml-1.5 rounded border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10.5px] font-medium text-indigo-600">
                            batas khusus
                          </span>
                        )}
                        {row.limits.note && (
                          <span className="mt-0.5 block text-[11.5px] text-zinc-400">
                            {row.limits.note}
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-zinc-600">
                          {fmtNum(row.day_tokens)}
                        </span>
                        <span className="block text-[11.5px] text-zinc-400">
                          {fmtNum(row.day_requests)} run
                        </span>
                        {row.limits.daily_tokens > 0 && (
                          <span className="mt-1 block h-1.5 w-24 overflow-hidden rounded-full bg-zinc-100">
                            <span
                              className={`block h-full ${bar.tone}`}
                              style={{ width: `${bar.pct}%` }}
                            />
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 pr-3 text-zinc-600">
                        {fmtNum(row.week_tokens)}
                      </td>
                      <td className="py-2.5 pr-3 text-[12px] text-zinc-500">
                        {isEditing ? (
                          <div className="space-y-1.5">
                            {(
                              [
                                ["daily_tokens", "hari"],
                                ["weekly_tokens", "pekan"],
                                ["daily_requests", "run/hari"],
                              ] as const
                            ).map(([key, label]) => (
                              <label
                                key={key}
                                className="flex items-center gap-1.5"
                              >
                                <span className="w-16 text-[11px] text-zinc-400">
                                  {label}
                                </span>
                                <input
                                  type="number"
                                  min={0}
                                  placeholder="global"
                                  value={draft[key]}
                                  onChange={(e) =>
                                    setDraft({ ...draft, [key]: e.target.value })
                                  }
                                  className="w-24 rounded-lg border border-zinc-200 px-2 py-1 text-[12px]"
                                />
                              </label>
                            ))}
                            <input
                              placeholder="catatan (mis. paket pro)"
                              value={draft.note}
                              onChange={(e) =>
                                setDraft({ ...draft, note: e.target.value })
                              }
                              className="w-full rounded-lg border border-zinc-200 px-2 py-1 text-[12px]"
                            />
                          </div>
                        ) : (
                          <>
                            {limitLabel(row.limits.daily_tokens)} / hari
                            <span className="block">
                              {limitLabel(row.limits.weekly_tokens)} / pekan
                            </span>
                          </>
                        )}
                      </td>
                      <td className="py-2.5 pr-3 text-[12px] text-zinc-400">
                        {fmtTime(row.last_seen)}
                      </td>
                      <td className="py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {isEditing ? (
                            <>
                              <button
                                disabled={busy}
                                onClick={() => saveOverride(row.user_key)}
                                className="rounded-lg bg-accent px-2 py-1 text-[11.5px] font-medium text-white disabled:opacity-50"
                              >
                                Simpan
                              </button>
                              <button
                                onClick={() => setEditing(null)}
                                className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-500"
                              >
                                Batal
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => startEdit(row)}
                                className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-600 hover:bg-zinc-50"
                              >
                                Batas khusus
                              </button>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  act(
                                    () =>
                                      adminResetQuota(
                                        readAdminToken(),
                                        row.user_key,
                                        "day"
                                      ),
                                    `Kuota harian ${row.user_key} direset.`
                                  )
                                }
                                className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                              >
                                Reset hari
                              </button>
                              {row.limits.source === "override" && (
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    act(
                                      () =>
                                        adminClearQuotaLimit(
                                          readAdminToken(),
                                          row.user_key
                                        ),
                                      `${row.user_key} kembali ke kebijakan global.`
                                    )
                                  }
                                  className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-500 hover:bg-zinc-50 disabled:opacity-50"
                                >
                                  Hapus batas khusus
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Request yang ditolak"
        subtitle="Bukti bahwa batas benar-benar ditegakkan di server — dan indikator apakah batasnya terlalu ketat."
      >
        {!data?.rejections.length ? (
          <p className="text-[13px] text-zinc-500">
            Belum ada request yang ditolak.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {data.rejections.slice(0, 20).map((r) => (
              <li key={r.id} className="py-2 text-[13px]">
                <span className="font-medium text-zinc-700">{r.user_key}</span>
                {r.mode && (
                  <span className="ml-1.5 rounded bg-zinc-100 px-1.5 py-0.5 text-[10.5px] text-zinc-500">
                    {r.mode}
                  </span>
                )}
                <span className="ml-2 text-[11.5px] text-zinc-400">
                  {fmtTime(r.ts)}
                </span>
                <span className="mt-0.5 block text-[12px] text-zinc-500">
                  {r.reason}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
