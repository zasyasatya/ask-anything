"use client";
/* Panel detail task (drawer kanan): edit cepat, checklist kriteria, komentar,
   dependency, dan info branch GitLab yang bisa langsung disalin. */
import { useEffect, useState } from "react";
import {
  COLUMNS,
  STATUS_META,
  addTaskComment,
  deleteTask,
  formatDate,
  formatDays,
  patchTask,
  priorityMeta,
  relativeTime,
  setAcceptance,
  type Task,
  type TaskStatus,
} from "@/lib/tasks";

export default function TaskDetail({
  task,
  phases,
  priorities,
  token,
  onClose,
  onChanged,
  onDeleted,
  onError,
  readOnly = false,
}: {
  task: Task;
  phases: Array<{ id: string; name: string; subtitle: string }>;
  priorities: string[];
  token: string;
  onClose: () => void;
  onChanged: (task: Task) => void;
  onDeleted: (id: string) => void;
  onError: (message: string) => void;
  /** Member: hanya boleh memindahkan status/komentar — field lain dikunci. */
  readOnly?: boolean;
}) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);
  const [assignee, setAssignee] = useState(task.assignee);
  const [estimate, setEstimate] = useState(String(task.estimate ?? 0));
  const [mrUrl, setMrUrl] = useState(task.mr_url);
  const [comment, setComment] = useState("");
  const [newCriterion, setNewCriterion] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setTitle(task.title);
    setDescription(task.description);
    setAssignee(task.assignee);
    setEstimate(String(task.estimate ?? 0));
    setMrUrl(task.mr_url);
    setCopied(false);
  }, [task.id, task.title, task.description, task.assignee, task.estimate,
      task.mr_url]);

  const patch = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      onChanged(await patchTask(token, task.id, body));
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const copyBranch = async () => {
    const text = task.git_command || `git checkout -b ${task.branch_name}`;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard diblokir browser — teks tetap terlihat untuk disalin manual */
    }
    setCopied(true);
  };

  const addComment = async () => {
    if (!comment.trim()) return;
    setBusy(true);
    try {
      const comments = await addTaskComment(token, task.id, comment, "dev");
      onChanged({ ...task, comments });
      setComment("");
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12.5px] text-zinc-800 focus:border-accent focus:outline-none";

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-zinc-900/30 backdrop-blur-sm">
      <button
        aria-label="Tutup detail task"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <aside
        data-testid="task-detail"
        className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white shadow-2xl"
      >
        <header className="sticky top-0 z-10 flex items-start gap-2 border-b border-zinc-200 bg-white/95 px-4 py-3 backdrop-blur">
          <span className="mt-0.5 rounded-md bg-zinc-900 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
            {task.id}
          </span>
          <div className="min-w-0 flex-1">
            <input
              aria-label="Judul task"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => title !== task.title && patch({ title })}
              className="w-full rounded-lg border border-transparent px-1 py-0.5 text-[14.5px] font-semibold text-zinc-800 hover:border-zinc-200 focus:border-accent focus:outline-none"
            />
            <p className="px-1 text-[11.5px] text-zinc-400">
              {phases.find((p) => p.id === task.phase)?.name} · diperbarui{" "}
              {relativeTime(task.updated_at)} · {task.source || "tanpa rujukan"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-200 px-2 py-1 text-[12px] text-zinc-500 hover:bg-zinc-50"
          >
            Tutup
          </button>
        </header>

        <div className="space-y-4 px-4 py-4">
          {readOnly && (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              Anda melihat task ini sebagai <b>member</b>: status, checklist, dan
              komentar bisa diubah; penugasan, fase, prioritas, dan penghapusan
              hanya oleh admin.
            </p>
          )}
          {/* baris kontrol utama */}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <label className="text-[11px] font-medium text-zinc-500">
              Status
              <select
                aria-label="Status"
                value={task.status}
                onChange={(e) => patch({ status: e.target.value as TaskStatus })}
                className={`mt-1 w-full rounded-lg border px-2 py-1.5 text-[12px] font-medium ${
                  STATUS_META[task.status].chip
                }`}
              >
                {COLUMNS.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_META[s].label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-medium text-zinc-500">
              Prioritas
              <select
                aria-label="Prioritas"
                disabled={readOnly}
                value={task.priority}
                onChange={(e) => patch({ priority: e.target.value })}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px]"
              >
                {priorities.map((p) => (
                  <option key={p} value={p}>
                    {priorityMeta(p).label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-medium text-zinc-500">
              Fase
              <select
                aria-label="Fase"
                disabled={readOnly}
                value={task.phase}
                onChange={(e) => patch({ phase: e.target.value })}
                className="mt-1 w-full rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px]"
              >
                {phases.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-medium text-zinc-500">
              Estimasi (hari)
              <input
                aria-label="Estimasi"
                disabled={readOnly}
                value={estimate}
                onChange={(e) => setEstimate(e.target.value)}
                onBlur={() =>
                  Number(estimate) !== task.estimate &&
                  patch({ estimate: Number(estimate) || 0 })
                }
                className={`mt-1 ${field}`}
              />
            </label>
          </div>

          <label className="block text-[11px] font-medium text-zinc-500">
            Assignee
            <input
              aria-label="Assignee"
              disabled={readOnly}
              value={assignee}
              placeholder="nama developer"
              onChange={(e) => setAssignee(e.target.value)}
              onBlur={() => assignee !== task.assignee && patch({ assignee })}
              className={`mt-1 ${field}`}
            />
          </label>

          <label className="block text-[11px] font-medium text-zinc-500">
            Deskripsi
            <textarea
              aria-label="Deskripsi"
              disabled={readOnly}
              value={description}
              rows={3}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={() => description !== task.description && patch({ description })}
              className={`mt-1 ${field} leading-relaxed`}
            />
          </label>

          {/* branch GitLab */}
          <section className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3">
            <h4 className="text-[12px] font-semibold text-zinc-700">
              🌿 Branch GitLab
            </h4>
            <p className="mt-0.5 text-[11.5px] text-zinc-500">
              Pakai id task di nama branch supaya papan ini bisa menandai progres
              otomatis saat sync.
            </p>
            <code className="mt-2 block overflow-x-auto rounded-lg bg-zinc-900 px-2.5 py-1.5 font-mono text-[11.5px] text-emerald-200">
              {task.git_command || `git checkout -b ${task.branch_name}`}
            </code>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                onClick={copyBranch}
                className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1 text-[11.5px] font-medium text-zinc-600 hover:bg-zinc-50"
              >
                {copied ? "✓ Tersalin" : "Salin perintah"}
              </button>
              {task.branch && (
                <span className="rounded-md bg-emerald-50 px-2 py-0.5 font-mono text-[11px] text-emerald-700">
                  aktif: {task.branch}
                </span>
              )}
              {task.commits.length > 0 && (
                <span className="text-[11px] text-zinc-500">
                  {task.commits.length} commit menyebut {task.id}
                </span>
              )}
            </div>
            <input
              aria-label="URL merge request"
              value={mrUrl}
              placeholder="tempel URL merge request GitLab (opsional)"
              onChange={(e) => setMrUrl(e.target.value)}
              onBlur={() => mrUrl !== task.mr_url && patch({ mr_url: mrUrl })}
              className={`mt-2 ${field}`}
            />
            {task.mr_url && (
              <a
                href={task.mr_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-[11.5px] font-medium text-accent hover:underline"
              >
                Buka merge request ↗
              </a>
            )}
          </section>

          {/* checklist */}
          <section>
            <h4 className="flex items-center gap-2 text-[12px] font-semibold text-zinc-700">
              ✅ Kriteria selesai
              <span className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500">
                {task.acceptance_done}/{task.acceptance_total}
              </span>
            </h4>
            <ul className="mt-2 space-y-1.5">
              {task.acceptance.map((item, index) => (
                <li key={`${task.id}-acc-${index}`} className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    aria-label={item.text}
                    checked={item.done}
                    onChange={async (e) => {
                      setBusy(true);
                      try {
                        onChanged(
                          await setAcceptance(token, task.id, {
                            index,
                            done: e.target.checked,
                          })
                        );
                      } catch (err) {
                        onError(String(err));
                      } finally {
                        setBusy(false);
                      }
                    }}
                    className="mt-0.5 h-4 w-4 accent-indigo-500"
                  />
                  <span
                    className={`flex-1 text-[12.5px] leading-relaxed ${
                      item.done ? "text-zinc-400 line-through" : "text-zinc-700"
                    }`}
                  >
                    {item.text}
                  </span>
                  <button
                    onClick={async () => {
                      try {
                        onChanged(
                          await setAcceptance(token, task.id, { index, remove: true })
                        );
                      } catch (err) {
                        onError(String(err));
                      }
                    }}
                    aria-label={`Hapus kriteria ${index + 1}`}
                    className="text-[11px] text-zinc-300 hover:text-rose-500"
                  >
                    ×
                  </button>
                </li>
              ))}
              {!task.acceptance.length && (
                <li className="text-[12px] text-zinc-400">Belum ada kriteria.</li>
              )}
            </ul>
            <div className="mt-2 flex gap-2">
              <input
                aria-label="Kriteria baru"
                value={newCriterion}
                placeholder="tambah kriteria selesai…"
                onChange={(e) => setNewCriterion(e.target.value)}
                className={field}
              />
              <button
                disabled={busy || !newCriterion.trim()}
                onClick={async () => {
                  try {
                    onChanged(
                      await setAcceptance(token, task.id, { text: newCriterion })
                    );
                    setNewCriterion("");
                  } catch (err) {
                    onError(String(err));
                  }
                }}
                className="shrink-0 rounded-lg bg-zinc-900 px-3 py-1.5 text-[12px] font-medium text-white disabled:opacity-40"
              >
                Tambah
              </button>
            </div>
          </section>

          {/* dependency & bukti */}
          <div className="grid gap-3 md:grid-cols-2">
            <section className="rounded-xl border border-zinc-200 p-3">
              <h4 className="text-[12px] font-semibold text-zinc-700">
                🔗 Prasyarat
              </h4>
              <ul className="mt-1.5 space-y-1 text-[11.5px]">
                {(task.depends_on_tasks || []).map((d) => (
                  <li key={d.id} className="flex items-center gap-1.5">
                    <span className="font-mono text-zinc-500">{d.id}</span>
                    <span className="truncate text-zinc-600">{d.title || "—"}</span>
                    <span
                      className={`ml-auto rounded px-1.5 py-0.5 text-[10px] ${
                        STATUS_META[(d.status as TaskStatus) in STATUS_META
                          ? (d.status as TaskStatus)
                          : "todo"].chip
                      }`}
                    >
                      {STATUS_META[(d.status as TaskStatus) in STATUS_META
                        ? (d.status as TaskStatus)
                        : "todo"].label}
                    </span>
                  </li>
                ))}
                {!(task.depends_on_tasks || []).length && (
                  <li className="text-zinc-400">Tidak ada prasyarat.</li>
                )}
              </ul>
              {(task.dependents || []).length > 0 && (
                <>
                  <h5 className="mt-2 text-[11px] font-semibold text-zinc-500">
                    Ditunggu oleh
                  </h5>
                  <p className="text-[11.5px] text-zinc-600">
                    {(task.dependents || []).map((d) => d.id).join(", ")}
                  </p>
                </>
              )}
            </section>

            <section className="rounded-xl border border-zinc-200 p-3">
              <h4 className="text-[12px] font-semibold text-zinc-700">
                📎 Bukti implementasi
              </h4>
              <ul className="mt-1.5 space-y-1 font-mono text-[11px] text-zinc-500">
                {task.evidence.map((path) => (
                  <li key={path} className="truncate" title={path}>
                    {path}
                  </li>
                ))}
                {!task.evidence.length && (
                  <li className="text-zinc-400">Belum ditentukan.</li>
                )}
              </ul>
              <h5 className="mt-2 text-[11px] font-semibold text-zinc-500">
                Commit terkait
              </h5>
              <ul className="mt-0.5 space-y-0.5 text-[11px] text-zinc-500">
                {task.commits.slice(-4).map((c) => (
                  <li key={c.sha} className="truncate" title={c.subject}>
                    <span className="font-mono text-zinc-400">{c.sha}</span>{" "}
                    {c.subject}
                  </li>
                ))}
                {!task.commits.length && <li className="text-zinc-400">—</li>}
              </ul>
            </section>
          </div>

          {/* komentar & aktivitas */}
          <section>
            <h4 className="text-[12px] font-semibold text-zinc-700">
              💬 Komentar &amp; aktivitas
            </h4>
            <ul className="mt-2 space-y-2">
              {(task.comments || []).map((c) => (
                <li
                  key={c.id}
                  className={`rounded-xl border px-3 py-2 text-[12px] ${
                    c.kind === "activity"
                      ? "border-zinc-100 bg-zinc-50 text-zinc-500"
                      : "border-zinc-200 bg-white text-zinc-700"
                  }`}
                >
                  <div className="flex items-center gap-2 text-[10.5px] text-zinc-400">
                    <b className="text-zinc-600">{c.author}</b>
                    <span>{relativeTime(c.created_at)}</span>
                    {c.kind === "activity" && (
                      <span className="rounded bg-zinc-200/60 px-1">sistem</span>
                    )}
                  </div>
                  <p className="mt-0.5 whitespace-pre-wrap leading-relaxed">{c.body}</p>
                </li>
              ))}
              {!(task.comments || []).length && (
                <li className="text-[12px] text-zinc-400">Belum ada komentar.</li>
              )}
            </ul>
            <div className="mt-2 flex gap-2">
              <textarea
                aria-label="Komentar baru"
                value={comment}
                rows={2}
                placeholder="tulis progres / catatan review…"
                onChange={(e) => setComment(e.target.value)}
                className={`${field} leading-relaxed`}
              />
              <button
                disabled={busy || !comment.trim()}
                onClick={addComment}
                className="shrink-0 self-end rounded-lg bg-accent px-3 py-1.5 text-[12px] font-medium text-white disabled:opacity-40"
              >
                Kirim
              </button>
            </div>
          </section>

          <footer className="flex items-center justify-between border-t border-zinc-200 pt-3 text-[11.5px] text-zinc-400">
            <span>
              dibuat {formatDate(task.created_at)} · estimasi{" "}
              {formatDays(task.estimate)}
              {task.seeded ? " · dari rencana RAG" : ""}
            </span>
            {!readOnly && (
              <button
                onClick={async () => {
                  if (
                    typeof window !== "undefined" &&
                    !window.confirm(`Hapus task ${task.id}?`)
                  )
                    return;
                  try {
                    await deleteTask(token, task.id);
                    onDeleted(task.id);
                  } catch (e) {
                    onError(String(e));
                  }
                }}
                className="rounded-lg border border-rose-200 px-2.5 py-1 font-medium text-rose-600 hover:bg-rose-50"
              >
                Hapus task
              </button>
            )}
          </footer>
        </div>
      </aside>
    </div>
  );
}
