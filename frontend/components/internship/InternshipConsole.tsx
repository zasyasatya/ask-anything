"use client";
/* Halaman /internship — papan & materi proyek "AI chatbot + RAG dari nol".
 *
 *   * admin melihat seluruh papan (semua intern),
 *   * member (peserta) hanya melihat task yang ditugaskan kepadanya — sama
 *     seperti penegakan di server (`tasks_scope=assigned`),
 *   * dokumen materi (`docs/internship/*.md`) dibaca langsung dari backend
 *     lewat /api/internship/docs sehingga satu sumber kebenaran,
 *   * status task bisa dipindahkan dari sini (member boleh, untuk task-nya).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  internshipDoc,
  internshipOverview,
  type InternshipDoc,
  type InternshipOverview,
} from "@/lib/api";
import { STATUS_META, fetchTasks, moveTask, type Task } from "@/lib/tasks";
import { useCapabilities } from "@/lib/auth";
import { Spinner } from "@/components/LoadingScreen";

const STATUS_ORDER = ["backlog", "todo", "in_progress", "review", "done"] as const;

function TaskRow({
  task,
  canWrite,
  onMove,
}: {
  task: Task;
  canWrite: boolean;
  onMove: (id: string, status: string) => void;
}) {
  const meta = STATUS_META[task.status];
  const next = STATUS_ORDER[Math.min(STATUS_ORDER.indexOf(task.status) + 1,
                                     STATUS_ORDER.length - 1)];
  return (
    <li className="rounded-xl border border-zinc-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-zinc-400">{task.id}</span>
        <span className={`rounded-md border px-1.5 py-0.5 text-[10.5px] font-medium ${meta.chip}`}>
          {meta.label}
        </span>
        <span className="text-[10.5px] text-zinc-400">{task.assignee || "—"}</span>
        {task.blocked_by?.length ? (
          <span className="rounded-md bg-rose-50 px-1.5 py-0.5 text-[10.5px] text-rose-600">
            tunggu {task.blocked_by.join(", ")}
          </span>
        ) : null}
        <span className="text-[10.5px] text-zinc-400">
          {task.acceptance_done}/{task.acceptance_total} kriteria
        </span>
        {canWrite && task.status !== "done" && (
          <button
            onClick={() => onMove(task.id, next)}
            className="ml-auto rounded-md border border-zinc-200 px-2 py-1 text-[10.5px] font-medium text-zinc-600 hover:bg-zinc-50"
            title={`Pindah ke ${STATUS_META[next].label}`}
          >
            → {STATUS_META[next].label}
          </button>
        )}
      </div>
      <p className="mt-1.5 text-[13px] font-medium text-zinc-800">{task.title}</p>
      <p className="mt-0.5 line-clamp-2 text-[12px] leading-5 text-zinc-500">
        {task.description}
      </p>
      <p className="mt-1 font-mono text-[11px] text-zinc-400">
        {task.git_command || `git checkout -b ${task.branch_name}`}
      </p>
    </li>
  );
}

export default function InternshipConsole() {
  const caps = useCapabilities();
  const [data, setData] = useState<InternshipOverview | null>(null);
  const [board, setBoard] = useState<Task[]>([]);
  const [doc, setDoc] = useState<{ title: string; markdown: string } | null>(null);
  const [activePhase, setActivePhase] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [overview, tasksRes] = await Promise.all([
        internshipOverview(),
        fetchTasks("", { track: "internship" }),
      ]);
      setData(overview);
      setBoard(tasksRes.tasks as unknown as Task[]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const phases = data?.plan?.phases ?? [];
  const visible = useMemo(
    () => board.filter((t) => activePhase === "all" || t.phase === activePhase),
    [board, activePhase]
  );

  async function openDoc(docItem: InternshipDoc) {
    try {
      const full = await internshipDoc(docItem.name);
      setDoc({ title: full.title, markdown: full.markdown });
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleMove(id: string, status: string) {
    setBoard((prev) => prev.map((t) => (t.id === id ? { ...t, status: status as Task["status"] } : t)));
    try {
      const res = await moveTask("", id, status as Task["status"]);
      setBoard(res.tasks as unknown as Task[]);
    } catch (e) {
      setError(String(e));
      load();
    }
  }

  const progress = data?.stats ? Number((data.stats as Record<string, number>).progress) : 0;

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-5 py-3">
          <a
            href="/"
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
          >
            ← Chat
          </a>
          <h1 className="text-[15px] font-semibold text-zinc-800">
            Proyek Internship — AI Chatbot + RAG dari Nol
          </h1>
          <span className="rounded-lg border border-zinc-200 px-2 py-1 font-mono text-[11px] text-zinc-400">
            {data?.project_dir || "projects/rag-agent"}
          </span>
          <div className="ml-auto flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-1.5">
            <span className="text-[11px] text-zinc-500">Progres</span>
            <div className="h-2 w-24 overflow-hidden rounded-full bg-zinc-100">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${progress}%` }} />
            </div>
            <b className="text-[12px] text-zinc-700">{progress}%</b>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-5">
        {loading && (
          <p className="flex items-center gap-2 text-sm text-zinc-500">
            <Spinner size={13} className="text-zinc-400" /> Memuat papan internship…
          </p>
        )}
        {error && (
          <p className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">
            {error}
          </p>
        )}

        {data && (
          <>
            <section className="mb-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-zinc-200 bg-white p-4 md:col-span-2">
                <h2 className="text-[13px] font-semibold text-zinc-800">
                  Cara kerja proyek ini
                </h2>
                <p className="mt-1 text-[12.5px] leading-6 text-zinc-600">
                  Bangun prototipe chatbot agentik <b>dari awal</b> di folder{" "}
                  <code className="rounded bg-zinc-100 px-1">{data.project_dir}</code>{" "}
                  sesuai slide <i>RAG + AI Agent</i>: upload dokumen → parser
                  structure-aware → chunking → embedding → vector store → retrieval →
                  tool <code className="rounded bg-zinc-100 px-1">retrieve_knowledge</code> →
                  jawaban bersitasi → visual web native (chart/table/timeline/graph).
                  Memori &amp; sesi percakapan juga dibangun sendiri. Baca dokumen{" "}
                  <b>01–06</b> di bawah sebelum menulis kode.
                </p>
                <p className="mt-2 text-[12px] text-zinc-500">
                  Papan ini terpisah dari papan platform (<code>ASK-NNN</code>);
                  id task di sini (<code>INT-NNN</code>) dipakai sebagai nama branch.
                  Anda melihat:{" "}
                  <b>{data.scope === "all" ? "seluruh papan (admin)" : "hanya task Anda"}</b>.
                </p>
              </div>

              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <h2 className="text-[13px] font-semibold text-zinc-800">Materi &amp; slide</h2>
                <ul className="mt-2 space-y-1.5">
                  {data.docs.map((d) => (
                    <li key={d.name}>
                      <button
                        onClick={() => openDoc(d)}
                        className="w-full truncate rounded-lg border border-zinc-200 px-2.5 py-1.5 text-left text-[12px] text-zinc-700 hover:bg-zinc-50"
                        title={d.name}
                      >
                        📄 {d.title}
                      </button>
                    </li>
                  ))}
                  {!data.docs.length && (
                    <li className="text-[11.5px] text-zinc-400">
                      Dokumen materi belum ada di <code>docs/internship/</code>.
                    </li>
                  )}
                  {data.slides.map((s) => (
                    <li key={s.href}>
                      <a
                        href={s.href}
                        target="_blank"
                        rel="noreferrer"
                        className="block truncate rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12px] text-zinc-700 hover:bg-zinc-50"
                        title={s.note}
                      >
                        🎬 {s.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            <section className="mb-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <h2 className="text-[13px] font-semibold text-zinc-800">Pembagian kerja</h2>
                <ul className="mt-2 space-y-1.5 text-[12px]">
                  {Object.entries(data.per_assignee).map(([who, s]) => (
                    <li key={who} className="flex items-center justify-between gap-2">
                      <span className="text-zinc-600">{who}</span>
                      <span className="text-zinc-400">
                        {s.done}/{s.total} selesai · {s.in_progress} jalan
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[11px] leading-5 text-zinc-400">
                  Estimasi total {data.plan.estimate_days} hari kerja. Admin bisa
                  memindahkan penanggung jawab di papan /tasks (track internship).
                </p>
              </div>

              <div className="rounded-2xl border border-zinc-200 bg-white p-4 md:col-span-2">
                <h2 className="text-[13px] font-semibold text-zinc-800">Sprint</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    onClick={() => setActivePhase("all")}
                    className={`rounded-lg border px-2.5 py-1.5 text-[11.5px] ${
                      activePhase === "all"
                        ? "border-zinc-900 bg-zinc-900 text-white"
                        : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                    }`}
                  >
                    Semua ({board.length})
                  </button>
                  {phases.map((p) => {
                    const count = board.filter((t) => t.phase === p.id).length;
                    return (
                      <button
                        key={p.id}
                        onClick={() => setActivePhase(p.id)}
                        title={p.subtitle}
                        className={`rounded-lg border px-2.5 py-1.5 text-[11.5px] ${
                          activePhase === p.id
                            ? "border-zinc-900 bg-zinc-900 text-white"
                            : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                        }`}
                      >
                        {p.name} ({count})
                      </button>
                    );
                  })}
                </div>
              </div>
            </section>

            <section>
              <h2 className="mb-2 text-[13px] font-semibold text-zinc-800">
                Task {activePhase === "all" ? "semua sprint" : activePhase}
              </h2>
              <ul className="grid gap-2 md:grid-cols-2">
                {visible.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    canWrite={caps.allow_task_write}
                    onMove={handleMove}
                  />
                ))}
              </ul>
              {!visible.length && (
                <p className="rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-8 text-center text-[12.5px] text-zinc-400">
                  Belum ada task di fase ini untuk Anda.
                </p>
              )}
            </section>
          </>
        )}
      </main>

      {doc && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-zinc-900/40 p-4 backdrop-blur-sm">
          <div className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
              <h3 className="text-sm font-semibold text-zinc-900">{doc.title}</h3>
              <button
                onClick={() => setDoc(null)}
                className="rounded-lg border border-zinc-200 px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-50"
              >
                Tutup
              </button>
            </div>
            <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap px-5 py-4 text-[12.5px] leading-6 text-zinc-700">
              {doc.markdown}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
