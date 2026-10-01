"use client";
/* Editor kecil untuk isi task yang dulu hanya bisa dibaca: workflow, wireframe,
   bukti, label, dan prasyarat. Tiap editor memegang drafnya sendiri dan baru
   mengirim perubahan saat tombol Simpan ditekan — supaya satu suntingan =
   satu PATCH, bukan satu PATCH per ketukan. Induk memberi `key` yang berubah
   saat data server berubah sehingga draf selalu mulai dari nilai tersimpan. */
import { useState } from "react";
import type { TaskWorkflowStep } from "@/lib/tasks";

const FIELD =
  "w-full rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12.5px] text-zinc-800 focus:border-accent focus:outline-none";

export type WorkflowDraft = { actor: string; action: string; result: string };

function SaveBar({
  busy,
  dirty,
  onSave,
  onCancel,
  saveLabel = "Simpan",
}: {
  busy: boolean;
  dirty: boolean;
  onSave: () => void;
  onCancel: () => void;
  saveLabel?: string;
}) {
  return (
    <div className="mt-3 flex items-center justify-end gap-2">
      <button
        type="button"
        onClick={onCancel}
        className="rounded-lg border border-zinc-200 px-3 py-1.5 text-[12px] text-zinc-600 hover:bg-zinc-50"
      >
        Batal
      </button>
      <button
        type="button"
        disabled={busy || !dirty}
        onClick={onSave}
        className="rounded-lg bg-accent px-3.5 py-1.5 text-[12px] font-medium text-white disabled:opacity-40"
      >
        {busy ? "Menyimpan…" : saveLabel}
      </button>
    </div>
  );
}

/** Alur kerja: daftar langkah {aktor, aksi, hasil} yang bisa ditambah/dihapus/diurutkan. */
export function WorkflowEditor({
  steps,
  busy,
  onSave,
  onCancel,
}: {
  steps: TaskWorkflowStep[];
  busy: boolean;
  onSave: (steps: WorkflowDraft[]) => void;
  onCancel: () => void;
}) {
  const initial: WorkflowDraft[] = steps.map((s) => ({
    actor: s.actor || "",
    action: s.action || "",
    result: s.result || "",
  }));
  const [draft, setDraft] = useState<WorkflowDraft[]>(initial);
  const clean = draft.filter((s) => s.action.trim());
  const dirty = JSON.stringify(clean) !== JSON.stringify(initial);

  const update = (i: number, key: keyof WorkflowDraft, value: string) =>
    setDraft((d) => d.map((s, idx) => (idx === i ? { ...s, [key]: value } : s)));
  const move = (i: number, dir: -1 | 1) =>
    setDraft((d) => {
      const j = i + dir;
      if (j < 0 || j >= d.length) return d;
      const next = d.slice();
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  return (
    <div data-testid="workflow-editor">
      <ol className="space-y-2">
        {draft.map((step, i) => (
          <li
            key={i}
            className="rounded-xl border border-zinc-200 bg-white p-2.5"
          >
            <div className="flex items-center gap-1.5">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent-soft font-mono text-[11px] font-semibold text-accent">
                {i + 1}
              </span>
              <input
                aria-label={`Aktor langkah ${i + 1}`}
                value={step.actor}
                placeholder="aktor (mis. Intern)"
                onChange={(e) => update(i, "actor", e.target.value)}
                className={`${FIELD} !w-40`}
              />
              <span className="ml-auto flex gap-1">
                <button
                  type="button"
                  aria-label={`Naikkan langkah ${i + 1}`}
                  disabled={i === 0}
                  onClick={() => move(i, -1)}
                  className="rounded border border-zinc-200 px-1.5 text-[11px] text-zinc-500 hover:bg-zinc-50 disabled:opacity-30"
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Turunkan langkah ${i + 1}`}
                  disabled={i === draft.length - 1}
                  onClick={() => move(i, 1)}
                  className="rounded border border-zinc-200 px-1.5 text-[11px] text-zinc-500 hover:bg-zinc-50 disabled:opacity-30"
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-label={`Hapus langkah ${i + 1}`}
                  onClick={() => setDraft((d) => d.filter((_, idx) => idx !== i))}
                  className="rounded border border-zinc-200 px-1.5 text-[11px] text-zinc-400 hover:text-rose-500"
                >
                  ×
                </button>
              </span>
            </div>
            <input
              aria-label={`Aksi langkah ${i + 1}`}
              value={step.action}
              placeholder="aksi yang dilakukan"
              onChange={(e) => update(i, "action", e.target.value)}
              className={`mt-1.5 ${FIELD}`}
            />
            <input
              aria-label={`Hasil langkah ${i + 1}`}
              value={step.result}
              placeholder="hasil yang diharapkan (opsional)"
              onChange={(e) => update(i, "result", e.target.value)}
              className={`mt-1.5 ${FIELD}`}
            />
          </li>
        ))}
        {!draft.length && (
          <li className="rounded-xl border border-dashed border-zinc-300 px-3 py-6 text-center text-[12.5px] text-zinc-400">
            Belum ada langkah.
          </li>
        )}
      </ol>
      <button
        type="button"
        onClick={() =>
          setDraft((d) => [...d, { actor: "", action: "", result: "" }])
        }
        className="mt-2 rounded-lg border border-dashed border-zinc-300 px-3 py-1.5 text-[12px] font-medium text-zinc-600 hover:bg-zinc-50"
      >
        + Tambah langkah
      </button>
      <SaveBar
        busy={busy}
        dirty={dirty}
        onSave={() => onSave(clean)}
        onCancel={onCancel}
        saveLabel="Simpan alur kerja"
      />
    </div>
  );
}

/** Wireframe (teks monospace) + daftar berkas bukti (satu per baris). */
export function WireframeEditor({
  wireframe,
  evidence,
  busy,
  onSave,
  onCancel,
}: {
  wireframe: string;
  evidence: string[];
  busy: boolean;
  onSave: (value: { wireframe: string; evidence: string[] }) => void;
  onCancel: () => void;
}) {
  const [wire, setWire] = useState(wireframe);
  const [files, setFiles] = useState(evidence.join("\n"));
  const nextEvidence = files
    .split("\n")
    .map((f) => f.trim())
    .filter(Boolean);
  const dirty =
    wire !== wireframe ||
    JSON.stringify(nextEvidence) !== JSON.stringify(evidence);

  return (
    <div data-testid="wireframe-editor">
      <label className="block text-[11px] font-medium text-zinc-500">
        Wireframe (teks / ASCII)
        <textarea
          aria-label="Wireframe"
          value={wire}
          rows={14}
          spellCheck={false}
          onChange={(e) => setWire(e.target.value)}
          className={`mt-1 ${FIELD} bg-zinc-950 font-mono text-[11.5px] leading-[1.55] text-zinc-100`}
        />
      </label>
      <label className="mt-3 block text-[11px] font-medium text-zinc-500">
        Berkas yang harus ada (satu per baris)
        <textarea
          aria-label="Berkas bukti"
          value={files}
          rows={4}
          spellCheck={false}
          onChange={(e) => setFiles(e.target.value)}
          className={`mt-1 ${FIELD} font-mono text-[11.5px]`}
        />
      </label>
      <SaveBar
        busy={busy}
        dirty={dirty}
        onSave={() => onSave({ wireframe: wire, evidence: nextEvidence })}
        onCancel={onCancel}
      />
    </div>
  );
}

/** Daftar teks pendek dipisah koma (label, prasyarat) — disimpan saat fokus keluar. */
export function CommaListField({
  label,
  ariaLabel,
  values,
  placeholder,
  disabled,
  transform,
  onCommit,
}: {
  label: string;
  ariaLabel: string;
  values: string[];
  placeholder?: string;
  disabled?: boolean;
  transform?: (value: string) => string;
  onCommit: (values: string[]) => void;
}) {
  const [text, setText] = useState(values.join(", "));
  const parse = (raw: string) =>
    raw
      .split(",")
      .map((v) => (transform ? transform(v.trim()) : v.trim()))
      .filter(Boolean);
  return (
    <label className="block text-[11px] font-medium text-zinc-500">
      {label}
      <input
        aria-label={ariaLabel}
        value={text}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          const next = parse(text);
          if (JSON.stringify(next) !== JSON.stringify(values)) onCommit(next);
        }}
        className={`mt-1 ${FIELD}`}
      />
    </label>
  );
}
