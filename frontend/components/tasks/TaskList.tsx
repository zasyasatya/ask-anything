"use client";
/* Tampilan daftar (list view) — lebih enak untuk menyaring & menyortir banyak
   task sekaligus, seperti tabel backlog di Jira. */
import {
  COLUMNS,
  STATUS_META,
  formatDays,
  priorityMeta,
  relativeTime,
  type Task,
  type TaskStatus,
} from "@/lib/tasks";

export default function TaskList({
  tasks,
  phases,
  onOpen,
  onMove,
}: {
  tasks: Task[];
  phases: Array<{ id: string; name: string }>;
  onOpen: (task: Task) => void;
  onMove: (task: Task, status: TaskStatus) => void;
}) {
  const phaseName = (id: string) =>
    phases.find((p) => p.id === id)?.name.replace(/^Fase \d+ — /, "") || id;

  return (
    <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-white">
      <table className="w-full min-w-[860px] border-collapse text-[12.5px]">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-400">
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">Task</th>
            <th className="px-3 py-2">Fase</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Prioritas</th>
            <th className="px-3 py-2">Owner</th>
            <th className="px-3 py-2">Estimasi</th>
            <th className="px-3 py-2">Diperbarui</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id} className="border-b border-zinc-100 hover:bg-zinc-50/70">
              <td className="px-3 py-2">
                <button
                  onClick={() => onOpen(task)}
                  className="rounded-md bg-zinc-900 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-white"
                >
                  {task.id}
                </button>
              </td>
              <td className="max-w-[360px] px-3 py-2">
                <button
                  onClick={() => onOpen(task)}
                  className="block truncate text-left font-medium text-zinc-800 hover:text-accent"
                >
                  {task.title}
                </button>
                <span className="font-mono text-[10.5px] text-zinc-400">
                  {task.branch || task.branch_name}
                </span>
              </td>
              <td className="px-3 py-2 text-zinc-500">{phaseName(task.phase)}</td>
              <td className="px-3 py-2">
                <select
                  aria-label={`Status ${task.id}`}
                  value={task.status}
                  onChange={(e) => onMove(task, e.target.value as TaskStatus)}
                  className={`rounded-lg border px-2 py-1 text-[11.5px] font-medium ${
                    STATUS_META[task.status].chip
                  }`}
                >
                  {COLUMNS.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-2">
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10.5px] font-medium ${
                    priorityMeta(task.priority).chip
                  }`}
                >
                  {priorityMeta(task.priority).label}
                </span>
              </td>
              <td className="px-3 py-2 text-zinc-600">{task.assignee || "—"}</td>
              <td className="px-3 py-2 text-zinc-500">{formatDays(task.estimate)}</td>
              <td className="px-3 py-2 text-zinc-400">{relativeTime(task.updated_at)}</td>
            </tr>
          ))}
          {!tasks.length && (
            <tr>
              <td colSpan={8} className="px-3 py-10 text-center text-zinc-400">
                Tidak ada task yang cocok dengan filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
