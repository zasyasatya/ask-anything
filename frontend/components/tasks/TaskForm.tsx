"use client";
/* Dialog "Task baru" — seperlunya saja: judul, fase, status, prioritas,
   estimasi, label, prasyarat, dan kriteria selesai (satu per baris).
   Nama branch yang disarankan ditampilkan langsung (mengikuti pola backend). */
import { useState } from "react";
import {
  COLUMNS,
  STATUS_META,
  createTask,
  suggestBranch,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/lib/tasks";

export default function TaskForm({
  token,
  phases,
  defaultPhase,
  suggestions,
  onClose,
  onCreated,
  onError,
}: {
  token: string;
  phases: Array<{ id: string; name: string }>;
  defaultPhase: string;
  suggestions: { assignees: string[]; labels: string[] };
  onClose: () => void;
  onCreated: (task: Task) => void;
  onError: (message: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [phase, setPhase] = useState(defaultPhase);
  const [status, setStatus] = useState<TaskStatus>("todo");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [assignee, setAssignee] = useState("");
  const [estimate, setEstimate] = useState("1");
  const [labels, setLabels] = useState("");
  const [dependsOn, setDependsOn] = useState("");
  const [acceptance, setAcceptance] = useState("");
  const [busy, setBusy] = useState(false);

  const field =
    "mt-1 w-full rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12.5px] text-zinc-800 focus:border-accent focus:outline-none";
  const label = "block text-[11px] font-medium text-zinc-500";
  const labelList = labels
    .split(",")
    .map((l) => l.trim())
    .filter(Boolean);

  const submit = async () => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      onCreated(
        await createTask(token, {
          title,
          description,
          phase,
          status,
          priority,
          assignee,
          estimate: Number(estimate) || 0,
          labels: labelList,
          depends_on: dependsOn
            .split(",")
            .map((d) => d.trim().toUpperCase())
            .filter(Boolean),
          acceptance: acceptance
            .split("\n")
            .map((a) => a.trim())
            .filter(Boolean),
        })
      );
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-900/30 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-label="Task baru"
        className="w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-4 shadow-2xl"
      >
        <header className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold text-zinc-800">Task baru</h3>
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-200 px-2 py-1 text-[12px] text-zinc-500 hover:bg-zinc-50"
          >
            Batal
          </button>
        </header>

        <div className="mt-3 space-y-3">
          <label className={label}>
            Judul *
            <input
              autoFocus
              aria-label="Judul task baru"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="mis. Tambah tool create_chart"
              className={field}
            />
          </label>
          <p className="rounded-lg bg-zinc-50 px-2.5 py-1.5 font-mono text-[11px] text-zinc-500">
            branch: {suggestBranch("ASK-NEW", title, labelList)}
          </p>

          <div className="grid grid-cols-2 gap-2">
            <label className={label}>
              Fase
              <select
                aria-label="Fase task baru"
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className={field}
              >
                {phases.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Status
              <select
                aria-label="Status task baru"
                value={status}
                onChange={(e) => setStatus(e.target.value as TaskStatus)}
                className={field}
              >
                {COLUMNS.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_META[s].label}
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Prioritas
              <select
                aria-label="Prioritas task baru"
                value={priority}
                onChange={(e) => setPriority(e.target.value as TaskPriority)}
                className={field}
              >
                {(["low", "medium", "high", "critical"] as TaskPriority[]).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Estimasi (hari)
              <input
                aria-label="Estimasi task baru"
                value={estimate}
                onChange={(e) => setEstimate(e.target.value)}
                className={field}
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <label className={label}>
              Assignee
              <input
                aria-label="Assignee task baru"
                list="task-assignees"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                className={field}
              />
              <datalist id="task-assignees">
                {suggestions.assignees.map((a) => (
                  <option key={a} value={a} />
                ))}
              </datalist>
            </label>
            <label className={label}>
              Label (pisahkan koma)
              <input
                aria-label="Label task baru"
                value={labels}
                onChange={(e) => setLabels(e.target.value)}
                placeholder="frontend, rag"
                className={field}
              />
            </label>
          </div>

          <label className={label}>
            Deskripsi
            <textarea
              aria-label="Deskripsi task baru"
              value={description}
              rows={2}
              onChange={(e) => setDescription(e.target.value)}
              className={`${field} leading-relaxed`}
            />
          </label>

          <label className={label}>
            Prasyarat (id, pisahkan koma)
            <input
              aria-label="Prasyarat task baru"
              value={dependsOn}
              onChange={(e) => setDependsOn(e.target.value)}
              placeholder="ASK-024, ASK-030"
              className={field}
            />
          </label>

          <label className={label}>
            Kriteria selesai (satu per baris)
            <textarea
              aria-label="Kriteria task baru"
              value={acceptance}
              rows={3}
              onChange={(e) => setAcceptance(e.target.value)}
              className={`${field} leading-relaxed`}
            />
          </label>
        </div>

        <footer className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-[12.5px] text-zinc-600 hover:bg-zinc-50"
          >
            Batal
          </button>
          <button
            disabled={busy || !title.trim()}
            onClick={submit}
            className="rounded-lg bg-accent px-3.5 py-1.5 text-[12.5px] font-medium text-white disabled:opacity-40"
          >
            {busy ? "Menyimpan…" : "Buat task"}
          </button>
        </footer>
      </div>
    </div>
  );
}
