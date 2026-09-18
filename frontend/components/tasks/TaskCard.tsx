"use client";
/* Kartu task — unit terkecil papan kanban.

   Menampilkan hal yang paling sering dibutuhkan saat daily standup: id (kode
   branch), judul, prioritas, progres checklist, assignee, penanda blocker, dan
   tombol cepat untuk memindahkan status (alternatif keyboard dari drag & drop).
*/
import type { DragEvent } from "react";
import {
  priorityMeta,
  statusMeta,
  formatDays,
  initials,
  nextStatus,
  STATUS_META,
  type Task,
} from "@/lib/tasks";

export default function TaskCard({
  task,
  onOpen,
  onMove,
  onDragStart,
  dragging,
  compact = false,
}: {
  task: Task;
  onOpen: (task: Task) => void;
  onMove?: (task: Task, status: Task["status"]) => void;
  onDragStart?: (task: Task) => void;
  dragging?: boolean;
  compact?: boolean;
}) {
  const prio = priorityMeta(task.priority);
  const next = nextStatus(task.status);
  const branch = task.branch || task.branch_name;

  return (
    <article
      draggable
      data-testid={`task-card-${task.id}`}
      onDragStart={(e: DragEvent<HTMLElement>) => {
        e.dataTransfer?.setData("text/plain", task.id);
        onDragStart?.(task);
      }}
      className={`group cursor-grab rounded-xl border bg-white p-3 text-left shadow-card transition active:cursor-grabbing ${
        dragging ? "opacity-50" : "hover:border-accent-ring"
      } border-zinc-200`}
    >
      <div className="flex items-start gap-2">
        <button
          onClick={() => onOpen(task)}
          className="min-w-0 flex-1 text-left"
          data-testid={`task-open-${task.id}`}
        >
          <div className="flex items-center gap-1.5">
            <span className="rounded-md bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white">
              {task.id}
            </span>
            <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${prio.chip}`}>
              {prio.label}
            </span>
            {task.blocked_by.length > 0 && (
              <span
                title={`Menunggu: ${task.blocked_by.join(", ")}`}
                className="rounded-md bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-600"
              >
                ⛔ {task.blocked_by.length}
              </span>
            )}
          </div>
          <h4 className="mt-1.5 line-clamp-2 text-[13px] font-medium leading-snug text-zinc-800">
            {task.title}
          </h4>
        </button>
        {onMove && task.status !== "done" && (
          <button
            onClick={() => onMove(task, next)}
            title={`Pindahkan ke ${STATUS_META[next].label}`}
            aria-label={`Pindahkan ${task.id} ke ${STATUS_META[next].label}`}
            className="rounded-md border border-zinc-200 px-1.5 py-0.5 text-[11px] text-zinc-400 opacity-0 transition hover:bg-zinc-50 hover:text-zinc-700 group-hover:opacity-100"
          >
            →
          </button>
        )}
      </div>

      {!compact && task.description && (
        <p className="mt-1.5 line-clamp-2 text-[11.5px] leading-relaxed text-zinc-500">
          {task.description}
        </p>
      )}

      <div className="mt-2 flex items-center gap-1.5 text-[10.5px] text-zinc-500">
        <span className={`h-1.5 w-1.5 rounded-full ${statusMeta(task.status).dot}`} />
        <span>{statusMeta(task.status).label}</span>
        <span className="text-zinc-300">•</span>
        <span>{formatDays(task.estimate)}</span>
      </div>

      {task.acceptance_total > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-[10px] text-zinc-400">
            <span>
              checklist {task.acceptance_done}/{task.acceptance_total}
            </span>
            <span>{task.progress}%</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-100">
            <div
              className={`h-full rounded-full ${
                task.progress === 100 ? "bg-emerald-500" : "bg-accent"
              }`}
              style={{ width: `${task.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-1">
        {task.labels.slice(0, 3).map((label) => (
          <span
            key={label}
            className="rounded-md bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500"
          >
            #{label}
          </span>
        ))}
        {task.commits.length > 0 && (
          <span
            title={task.commits.map((c) => c.subject).join("\n")}
            className="rounded-md bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700"
          >
            {task.commits.length} commit
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-zinc-100 pt-2">
        <span
          className="truncate font-mono text-[10px] text-zinc-400"
          title={branch}
        >
          {branch}
        </span>
        {task.assignee ? (
          <span
            title={task.assignee}
            className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent-soft text-[9.5px] font-semibold text-accent"
          >
            {initials(task.assignee)}
          </span>
        ) : (
          <span className="text-[10px] text-zinc-300">belum di-assign</span>
        )}
      </div>
    </article>
  );
}
