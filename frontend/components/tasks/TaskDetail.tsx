"use client";
/* Panel detail task (drawer kanan) — dirapikan menjadi empat tab supaya
   tidak lagi menampilkan semuanya sekaligus:

     Ringkasan  → tujuan, kriteria selesai, prasyarat
     Workflow   → alur kerja bernomor (aktor → aksi → hasil)
     Wireframe  → sketsa layout / bentuk data (monospace)
     Aktivitas  → komentar, riwayat, branch, bukti implementasi

   Baris kendali (status, prioritas, fase, estimasi, assignee) tetap terlihat
   di semua tab karena itu yang paling sering diubah saat standup. */
import { useEffect, useMemo, useState } from "react";
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

type Tab = "ringkasan" | "workflow" | "wireframe" | "aktivitas";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "ringkasan", label: "Ringkasan" },
  { id: "workflow", label: "Workflow" },
  { id: "wireframe", label: "Wireframe" },
  { id: "aktivitas", label: "Aktivitas" },
];

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
  const [tab, setTab] = useState<Tab>("ringkasan");
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

  // Kembali ke tab pertama saat berpindah task supaya tidak mendarat di tab
  // kosong (task lama punya workflow, task buatan tangan mungkin belum).
  useEffect(() => setTab("ringkasan"), [task.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const workflow = useMemo(() => task.workflow || [], [task.workflow]);
  const counts = {
    workflow: workflow.length,
    wireframe: task.wireframe ? 1 : 0,
    aktivitas: (task.comments || []).length,
  };

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
  const phaseName = phases.find((p) => p.id === task.phase)?.name || task.phase;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-zinc-900/30 backdrop-blur-sm">
      <button
        aria-label="Tutup detail task"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <aside
        data-testid="task-detail"
        className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl"
      >
        {/* ---------------------------------------------------------- header */}
        <header className="shrink-0 border-b border-zinc-200 bg-white px-4 pt-3">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 rounded-md bg-zinc-900 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
              {task.id}
            </span>
            <div className="min-w-0 flex-1">
              <input
                aria-label="Judul task"
                value={title}
                disabled={readOnly}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={() => title !== task.title && patch({ title })}
                className="w-full rounded-lg border border-transparent px-1 py-0.5 text-[15px] font-semibold text-zinc-800 hover:border-zinc-200 focus:border-accent focus:outline-none"
              />
              <p className="px-1 text-[11.5px] text-zinc-400">
                {phaseName} · {formatDays(task.estimate)} · diperbarui{" "}
                {relativeTime(task.updated_at)}
              </p>
            </div>
            <button
              onClick={onClose}
              aria-label="Tutup panel"
              className="rounded-lg border border-zinc-200 px-2 py-1 text-[12px] text-zinc-500 hover:bg-zinc-50"
            >
              Tutup
            </button>
          </div>

          {/* baris kendali — selalu terlihat, ringkas satu baris */}
          <div className="mt-2.5 grid grid-cols-2 gap-1.5 md:grid-cols-5">
            <select
              aria-label="Status"
              value={task.status}
              onChange={(e) => patch({ status: e.target.value as TaskStatus })}
              className={`rounded-lg border px-2 py-1.5 text-[11.5px] font-medium ${
                STATUS_META[task.status].chip
              }`}
            >
              {COLUMNS.map((s) => (
                <option key={s} value={s}>
                  {STATUS_META[s].label}
                </option>
              ))}
            </select>
            <select
              aria-label="Prioritas"
              disabled={readOnly}
              value={task.priority}
              onChange={(e) => patch({ priority: e.target.value })}
              className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[11.5px] text-zinc-600"
            >
              {priorities.map((p) => (
                <option key={p} value={p}>
                  {priorityMeta(p).label}
                </option>
              ))}
            </select>
            <select
              aria-label="Fase"
              disabled={readOnly}
              value={task.phase}
              onChange={(e) => patch({ phase: e.target.value })}
              className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[11.5px] text-zinc-600"
            >
              {phases.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              aria-label="Assignee"
              disabled={readOnly}
              value={assignee}
              placeholder="assignee"
              onChange={(e) => setAssignee(e.target.value)}
              onBlur={() => assignee !== task.assignee && patch({ assignee })}
              className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[11.5px] text-zinc-700"
            />
            <input
              aria-label="Estimasi"
              disabled={readOnly}
              value={estimate}
              placeholder="hari"
              onChange={(e) => setEstimate(e.target.value)}
              onBlur={() =>
                Number(estimate) !== task.estimate &&
                patch({ estimate: Number(estimate) || 0 })
              }
              className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[11.5px] text-zinc-700"
            />
          </div>

          {/* tab */}
          <nav className="mt-2.5 flex gap-1" role="tablist">
            {TABS.map((t) => {
              const badge = t.id === "ringkasan" ? 0 : counts[t.id];
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={`relative -mb-px rounded-t-lg border-b-2 px-3 py-1.5 text-[12.5px] font-medium transition ${
                    tab === t.id
                      ? "border-accent text-accent"
                      : "border-transparent text-zinc-500 hover:text-zinc-700"
                  }`}
                >
                  {t.label}
                  {badge > 0 && (
                    <span className="ml-1.5 rounded bg-zinc-100 px-1 font-mono text-[10px] text-zinc-500">
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </header>

        {/* ------------------------------------------------------- isi tab */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {readOnly && (
            <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
              Anda melihat task ini sebagai <b>member</b>: status, checklist, dan
              komentar bisa diubah; penugasan, fase, prioritas, dan penghapusan
              hanya oleh admin.
            </p>
          )}

          {/* ------------------------------------------------ RINGKASAN */}
          {tab === "ringkasan" && (
            <div className="space-y-4">
              <section>
                <h4 className="text-[12px] font-semibold text-zinc-700">
                  Tujuan &amp; konteks
                </h4>
                {readOnly ? (
                  <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-600">
                    {task.description || "Belum ada deskripsi."}
                  </p>
                ) : (
                  <textarea
                    aria-label="Deskripsi"
                    value={description}
                    rows={6}
                    placeholder="Apa yang dibangun, keputusan teknis yang sudah ditetapkan, dan batasannya…"
                    onChange={(e) => setDescription(e.target.value)}
                    onBlur={() =>
                      description !== task.description && patch({ description })
                    }
                    className={`mt-1.5 ${field} leading-relaxed`}
                  />
                )}
              </section>

              <section>
                <h4 className="flex items-center gap-2 text-[12px] font-semibold text-zinc-700">
                  Kriteria selesai
                  <span className="rounded-md bg-zinc-100 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500">
                    {task.acceptance_done}/{task.acceptance_total}
                  </span>
                </h4>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-100">
                  <div
                    className={`h-full rounded-full ${
                      task.progress === 100 ? "bg-emerald-500" : "bg-accent"
                    }`}
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
                <ul className="mt-2 space-y-1.5">
                  {task.acceptance.map((item, index) => (
                    <li
                      key={`${task.id}-acc-${index}`}
                      className="flex items-start gap-2"
                    >
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
                      {!readOnly && (
                        <button
                          onClick={async () => {
                            try {
                              onChanged(
                                await setAcceptance(token, task.id, {
                                  index,
                                  remove: true,
                                })
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
                      )}
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

              <section className="rounded-xl border border-zinc-200 p-3">
                <h4 className="text-[12px] font-semibold text-zinc-700">Prasyarat</h4>
                <ul className="mt-1.5 space-y-1 text-[11.5px]">
                  {(task.depends_on_tasks || []).map((d) => {
                    const st = (d.status as TaskStatus) in STATUS_META
                      ? (d.status as TaskStatus)
                      : "todo";
                    return (
                      <li key={d.id} className="flex items-center gap-1.5">
                        <span className="font-mono text-zinc-500">{d.id}</span>
                        <span className="truncate text-zinc-600">{d.title || "—"}</span>
                        <span
                          className={`ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] ${STATUS_META[st].chip}`}
                        >
                          {STATUS_META[st].label}
                        </span>
                      </li>
                    );
                  })}
                  {!(task.depends_on_tasks || []).length && (
                    <li className="text-zinc-400">
                      Tidak ada prasyarat — bisa langsung dikerjakan.
                    </li>
                  )}
                </ul>
                {(task.dependents || []).length > 0 && (
                  <p className="mt-2 text-[11.5px] text-zinc-500">
                    Ditunggu oleh:{" "}
                    <span className="font-mono text-zinc-600">
                      {(task.dependents || []).map((d) => d.id).join(", ")}
                    </span>
                  </p>
                )}
              </section>
            </div>
          )}

          {/* ------------------------------------------------- WORKFLOW */}
          {tab === "workflow" && (
            <div>
              <p className="text-[12px] text-zinc-500">
                Alur kerja task ini: siapa melakukan apa, dan apa hasilnya. Ikuti
                urutannya dari atas ke bawah.
              </p>
              {workflow.length ? (
                <ol className="mt-3 space-y-2" data-testid="task-workflow">
                  {workflow.map((step) => (
                    <li
                      key={step.step}
                      className="relative rounded-xl border border-zinc-200 bg-white p-3 pl-10"
                    >
                      <span className="absolute left-3 top-3 grid h-5 w-5 place-items-center rounded-full bg-accent-soft font-mono text-[11px] font-semibold text-accent">
                        {step.step}
                      </span>
                      {step.actor && (
                        <span className="inline-block rounded-md bg-zinc-100 px-1.5 py-0.5 text-[10.5px] font-medium text-zinc-600">
                          {step.actor}
                        </span>
                      )}
                      <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-800">
                        {step.action}
                      </p>
                      {step.result && (
                        <p className="mt-1 flex gap-1.5 text-[11.5px] leading-relaxed text-emerald-700">
                          <span aria-hidden>→</span>
                          <span>{step.result}</span>
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-3 rounded-xl border border-dashed border-zinc-300 px-3 py-8 text-center text-[12.5px] text-zinc-400">
                  Belum ada workflow untuk task ini. Task rencana hasil seed sudah
                  memuat alur kerja lengkap.
                </p>
              )}
            </div>
          )}

          {/* ------------------------------------------------ WIREFRAME */}
          {tab === "wireframe" && (
            <div>
              <p className="text-[12px] text-zinc-500">
                Sketsa tampilan atau bentuk data yang harus dihasilkan task ini —
                acuan visual, bukan desain final.
              </p>
              {task.wireframe ? (
                <pre
                  data-testid="task-wireframe"
                  className="mt-3 overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-950 px-3.5 py-3 font-mono text-[11.5px] leading-[1.55] text-zinc-100"
                >
                  {task.wireframe}
                </pre>
              ) : (
                <p className="mt-3 rounded-xl border border-dashed border-zinc-300 px-3 py-8 text-center text-[12.5px] text-zinc-400">
                  Belum ada wireframe untuk task ini.
                </p>
              )}
              {!!task.evidence.length && (
                <section className="mt-4 rounded-xl border border-zinc-200 p-3">
                  <h4 className="text-[12px] font-semibold text-zinc-700">
                    Berkas yang harus ada
                  </h4>
                  <ul className="mt-1.5 space-y-1 font-mono text-[11px] text-zinc-500">
                    {task.evidence.map((path) => (
                      <li key={path} className="truncate" title={path}>
                        {path}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}

          {/* ------------------------------------------------ AKTIVITAS */}
          {tab === "aktivitas" && (
            <div className="space-y-4">
              <section className="rounded-xl border border-zinc-200 bg-zinc-50/70 p-3">
                <h4 className="text-[12px] font-semibold text-zinc-700">
                  Branch git
                </h4>
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
                </div>
                <input
                  aria-label="URL merge request"
                  value={mrUrl}
                  disabled={readOnly}
                  placeholder="tempel URL merge request (opsional)"
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
                {task.commits.length > 0 && (
                  <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-500">
                    {task.commits.slice(-5).map((c) => (
                      <li key={c.sha} className="truncate" title={c.subject}>
                        <span className="font-mono text-zinc-400">{c.sha}</span>{" "}
                        {c.subject}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h4 className="text-[12px] font-semibold text-zinc-700">
                  Komentar &amp; riwayat
                </h4>
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
                <ul className="mt-3 space-y-2">
                  {(task.comments || [])
                    .slice()
                    .reverse()
                    .map((c) => (
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
                        <p className="mt-0.5 whitespace-pre-wrap leading-relaxed">
                          {c.body}
                        </p>
                      </li>
                    ))}
                  {!(task.comments || []).length && (
                    <li className="text-[12px] text-zinc-400">Belum ada komentar.</li>
                  )}
                </ul>
              </section>
            </div>
          )}
        </div>

        {/* ---------------------------------------------------------- footer */}
        <footer className="flex shrink-0 items-center justify-between border-t border-zinc-200 bg-white px-4 py-2.5 text-[11.5px] text-zinc-400">
          <span>
            dibuat {formatDate(task.created_at)}
            {task.source ? ` · ${task.source}` : ""}
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
      </aside>
    </div>
  );
}
