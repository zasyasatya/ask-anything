"use client";
/* Tab Instruksi — kelola playbook domain + teori cara menjawab.

   Satu playbook = PERAN (domain) + METODE (teori cara menjawab) + BATASAN +
   FORMAT KELUARAN. Playbook yang aktif dirangkai ke system prompt setiap run.

   Dua hal yang membuat pipeline ini bisa benar-benar dikelola:
     * "Uji pemicu" memanggil /preview — memperlihatkan playbook mana yang akan
       menyala untuk sebuah pertanyaan TANPA memanggil model, jadi kata pemicu
       bisa diverifikasi sebelum dilepas ke pengguna.
     * Statistik pemakaian NYATA (bukan hanya daftar), termasuk daftar playbook
       aktif yang belum pernah terpakai — penanda pemicunya salah. */
import { useState } from "react";
import {
  adminCreatePlaybook,
  adminDeletePlaybook,
  adminPreviewPlaybooks,
  adminUpdatePolicy,
  adminUpdatePlaybook,
  readAdminToken,
} from "@/lib/api";
import type {
  FullPolicy,
  InstructionDashboard,
  Playbook,
  PlaybookInput,
} from "@/lib/types";
import { Card, Stat, Toggle, fmtTime } from "./ui";

const ACTIVATIONS = [
  { id: "always", label: "Selalu aktif", hint: "dipakai di setiap pertanyaan" },
  {
    id: "keywords",
    label: "Kata pemicu",
    hint: "hanya bila pesan memuat salah satu kata",
  },
  {
    id: "manual",
    label: "Manual",
    hint: "hanya bila dipilih eksplisit saat mengirim chat",
  },
] as const;

const EMPTY: PlaybookInput = {
  name: "",
  domain: "",
  persona: "",
  theory: "",
  method: "",
  rules: "",
  output_format: "",
  triggers: [],
  activation: "keywords",
  priority: 100,
  enabled: true,
};

export default function InstructionsTab({
  data,
  policy,
  onPolicyChange,
  onChanged,
}: {
  data: InstructionDashboard | null;
  policy: FullPolicy;
  onPolicyChange: (p: FullPolicy) => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [form, setForm] = useState<PlaybookInput>(EMPTY);
  const [triggerText, setTriggerText] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [probe, setProbe] = useState("");
  const [probeResult, setProbeResult] = useState<{
    count: number;
    block: string;
    selected: Playbook[];
  } | null>(null);

  const theories = data?.theories ?? [];
  const stats = data?.stats;

  function resetForm() {
    setForm(EMPTY);
    setTriggerText("");
    setEditingId(null);
  }

  async function run(fn: () => Promise<unknown>, message: string) {
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

  async function save() {
    const payload: PlaybookInput = {
      ...form,
      name: form.name.trim(),
      triggers: triggerText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    if (!payload.name) {
      setNote("Nama playbook wajib diisi.");
      return;
    }
    await run(async () => {
      if (editingId) {
        await adminUpdatePlaybook(readAdminToken(), editingId, payload);
      } else {
        await adminCreatePlaybook(readAdminToken(), payload);
      }
      resetForm();
    }, editingId ? "Playbook diperbarui." : "Playbook dibuat.");
  }

  function startEdit(p: Playbook) {
    setEditingId(p.id);
    setForm({
      name: p.name,
      domain: p.domain,
      persona: p.persona,
      theory: p.theory,
      method: p.method,
      rules: p.rules,
      output_format: p.output_format,
      activation: p.activation,
      priority: p.priority,
      enabled: p.enabled,
    });
    setTriggerText(p.triggers.join(", "));
  }

  async function doProbe() {
    setBusy(true);
    setNote(null);
    try {
      setProbeResult(
        await adminPreviewPlaybooks(readAdminToken(), { message: probe })
      );
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  }

  const chosenTheory = theories.find((t) => t.key === form.theory);

  return (
    <div className="space-y-4">
      {note && (
        <p className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-[13px] text-zinc-600">
          {note}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Playbook"
          value={stats?.total ?? 0}
          hint={`${stats?.enabled ?? 0} aktif`}
          tone="indigo"
        />
        <Stat
          label="Kali dipakai"
          value={stats?.activations_total ?? 0}
          hint="aktivasi nyata pada run"
        />
        <Stat
          label="Selalu aktif"
          value={stats?.by_activation?.always ?? 0}
          hint={`${stats?.by_activation?.keywords ?? 0} pakai kata pemicu`}
        />
        <Stat
          label="Belum pernah dipakai"
          value={stats?.never_used?.length ?? 0}
          hint="biasanya kata pemicunya salah"
          tone={(stats?.never_used?.length ?? 0) > 0 ? "amber" : "green"}
        />
      </div>

      <Card
        title="Kebijakan pipeline instruksi"
        subtitle="Playbook mengatur CARA menjawab. Ia bukan sumber fakta dan tidak pernah disitasi sebagai sumber."
      >
        <div className="space-y-3">
          <Toggle
            checked={policy.instructions.enabled}
            onChange={(v) =>
              run(async () => {
                const next = await adminUpdatePolicy(readAdminToken(), {
                  instructions: { enabled: v },
                });
                onPolicyChange(next);
              }, "Kebijakan instruksi disimpan.")
            }
            label="Aktifkan instruksi advanced"
            hint="Dimatikan = tidak ada playbook yang disisipkan ke system prompt."
          />
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                ["max_active", "Maksimum playbook aktif bersamaan"],
                ["max_chars", "Batas panjang blok instruksi (karakter)"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="block">
                <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                  {label}
                </span>
                <input
                  type="number"
                  min={1}
                  defaultValue={policy.instructions[key]}
                  disabled={busy}
                  onBlur={(e) => {
                    const v = Math.max(1, Number(e.target.value));
                    if (v !== policy.instructions[key])
                      run(async () => {
                        const next = await adminUpdatePolicy(readAdminToken(), {
                          instructions: { [key]: v },
                        });
                        onPolicyChange(next);
                      }, "Kebijakan instruksi disimpan.");
                  }}
                  className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px] text-zinc-700 focus:border-accent focus:outline-none"
                />
              </label>
            ))}
          </div>
        </div>
      </Card>

      <Card
        title={editingId ? "Ubah playbook" : "Buat playbook baru"}
        subtitle="Pilih teori cara menjawab dari katalog, atau tulis metode sendiri."
        right={
          editingId && (
            <button
              onClick={resetForm}
              className="rounded-lg border border-zinc-200 px-2.5 py-1 text-[12px] text-zinc-500 hover:bg-zinc-50"
            >
              Batal ubah
            </button>
          )
        }
      >
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Nama playbook
              </span>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="mis. Analis Hukum Perdata"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Domain
              </span>
              <input
                value={form.domain}
                onChange={(e) => setForm({ ...form, domain: e.target.value })}
                placeholder="mis. hukum, kesehatan, keuangan"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              />
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-zinc-500">
              Peran (persona)
            </span>
            <textarea
              rows={2}
              value={form.persona}
              onChange={(e) => setForm({ ...form, persona: e.target.value })}
              placeholder="mis. analis hukum perdata Indonesia yang berhati-hati"
              className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-zinc-500">
              Teori cara menjawab
            </span>
            <select
              value={form.theory}
              onChange={(e) => setForm({ ...form, theory: e.target.value })}
              className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
            >
              <option value="">— tanpa teori (pakai metode bebas) —</option>
              {theories.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label} · {t.domain_hint}
                </option>
              ))}
            </select>
          </label>
          {chosenTheory && (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-xl border border-indigo-100 bg-indigo-50/50 px-3 py-2 text-[12px] leading-5 text-zinc-600">
              {chosenTheory.method}
            </pre>
          )}

          <label className="block">
            <span className="mb-1 block text-[12px] font-medium text-zinc-500">
              Metode tambahan (opsional)
            </span>
            <textarea
              rows={2}
              value={form.method}
              onChange={(e) => setForm({ ...form, method: e.target.value })}
              className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Batasan
              </span>
              <textarea
                rows={2}
                value={form.rules}
                onChange={(e) => setForm({ ...form, rules: e.target.value })}
                placeholder="mis. jangan memberi nasihat hukum final"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Format keluaran
              </span>
              <textarea
                rows={2}
                value={form.output_format}
                onChange={(e) =>
                  setForm({ ...form, output_format: e.target.value })
                }
                placeholder="mis. Isu / Aturan / Analisis / Simpulan"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Aktivasi
              </span>
              <select
                value={form.activation}
                onChange={(e) =>
                  setForm({
                    ...form,
                    activation: e.target.value as PlaybookInput["activation"],
                  })
                }
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              >
                {ACTIVATIONS.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} — {a.hint}
                  </option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Kata pemicu (pisahkan dengan koma)
              </span>
              <input
                value={triggerText}
                onChange={(e) => setTriggerText(e.target.value)}
                disabled={form.activation !== "keywords"}
                placeholder="pasal, wanprestasi, kontrak"
                className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-[13px] disabled:bg-zinc-50"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="block">
              <span className="mb-1 block text-[12px] font-medium text-zinc-500">
                Prioritas
              </span>
              <input
                type="number"
                value={form.priority}
                onChange={(e) =>
                  setForm({ ...form, priority: Number(e.target.value) })
                }
                className="w-28 rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
              />
            </label>
            <button
              disabled={busy}
              onClick={save}
              className="rounded-xl bg-accent px-4 py-2 text-[13px] font-medium text-white disabled:opacity-50"
            >
              {editingId ? "Simpan perubahan" : "Buat playbook"}
            </button>
          </div>
        </div>
      </Card>

      <Card
        title="Uji pemicu"
        subtitle="Lihat playbook mana yang akan menyala untuk sebuah pertanyaan — tanpa memanggil model."
      >
        <div className="flex flex-wrap gap-2">
          <input
            value={probe}
            onChange={(e) => setProbe(e.target.value)}
            placeholder="mis. apa akibat wanprestasi kontrak?"
            className="min-w-[240px] flex-1 rounded-xl border border-zinc-200 px-3 py-2 text-[13px]"
          />
          <button
            disabled={busy || !probe.trim()}
            onClick={doProbe}
            className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-[13px] font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
          >
            Uji
          </button>
        </div>
        {probeResult && (
          <div className="mt-3">
            <p className="text-[13px] text-zinc-600">
              {probeResult.count === 0
                ? "Tidak ada playbook yang menyala untuk pertanyaan ini."
                : `${probeResult.count} playbook menyala: ` +
                  probeResult.selected
                    .map((p) => `${p.name} (${p.match_reason ?? ""})`)
                    .join(", ")}
            </p>
            {probeResult.block && (
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-[12px] leading-5 text-zinc-600">
                {probeResult.block}
              </pre>
            )}
          </div>
        )}
      </Card>

      <Card
        title="Playbook terdaftar"
        subtitle="Urut prioritas menurun — yang di atas menang bila beberapa aktif bersamaan."
      >
        {!data?.playbooks.length ? (
          <p className="text-[13px] text-zinc-500">
            Belum ada playbook. Buat satu di atas untuk mengarahkan AI ke domain
            tertentu.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {data.playbooks.map((p) => {
              const used = stats?.top_used?.find(
                (u) => u.playbook_id === p.id
              );
              const theory = theories.find((t) => t.key === p.theory);
              return (
                <li key={p.id} className="py-2.5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[13px] font-medium text-zinc-800">
                      {p.name}
                    </span>
                    {p.domain && (
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10.5px] text-zinc-500">
                        {p.domain}
                      </span>
                    )}
                    {theory && (
                      <span className="rounded border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10.5px] text-indigo-600">
                        {theory.label}
                      </span>
                    )}
                    <span className="rounded border border-zinc-200 px-1.5 py-0.5 text-[10.5px] text-zinc-500">
                      {ACTIVATIONS.find((a) => a.id === p.activation)?.label ??
                        p.activation}
                    </span>
                    {!p.enabled && (
                      <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10.5px] text-amber-700">
                        nonaktif
                      </span>
                    )}
                    <span className="ml-auto text-[11.5px] text-zinc-400">
                      prioritas {p.priority} ·{" "}
                      {used ? `dipakai ${used.runs}×` : "belum pernah dipakai"}
                      {used ? ` · ${fmtTime(used.last_used)}` : ""}
                    </span>
                  </div>
                  {p.triggers.length > 0 && (
                    <p className="mt-0.5 text-[11.5px] text-zinc-400">
                      pemicu: {p.triggers.join(", ")}
                    </p>
                  )}
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    <button
                      onClick={() => startEdit(p)}
                      className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-600 hover:bg-zinc-50"
                    >
                      Ubah
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        run(
                          () =>
                            adminUpdatePlaybook(readAdminToken(), p.id, {
                              enabled: !p.enabled,
                            }),
                          p.enabled ? "Playbook dimatikan." : "Playbook diaktifkan."
                        )
                      }
                      className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                    >
                      {p.enabled ? "Matikan" : "Aktifkan"}
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        run(
                          () => adminDeletePlaybook(readAdminToken(), p.id),
                          "Playbook dihapus."
                        )
                      }
                      className="rounded-lg border border-zinc-200 px-2 py-1 text-[11.5px] text-red-500 hover:bg-red-50 disabled:opacity-50"
                    >
                      Hapus
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {data?.activations?.length ? (
        <Card
          title="Aktivasi terakhir"
          subtitle="Playbook yang benar-benar membentuk jawaban — bukan hanya yang terdaftar."
        >
          <ul className="divide-y divide-zinc-100">
            {data.activations.slice(0, 15).map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-baseline gap-2 py-1.5 text-[13px]"
              >
                <span className="font-medium text-zinc-700">
                  {a.playbook_name}
                </span>
                {a.mode && (
                  <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10.5px] text-zinc-500">
                    {a.mode}
                  </span>
                )}
                <span className="text-[11.5px] text-zinc-400">
                  {a.match_reason}
                </span>
                <span className="ml-auto text-[11.5px] text-zinc-400">
                  {fmtTime(a.ts)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
