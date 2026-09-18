"use client";
/* Papan kanban: kolom per status + drag & drop antar kolom.

   Drag memakai state React (bukan hanya dataTransfer) supaya tetap berfungsi
   di lingkungan uji tanpa DataTransfer lengkap, dan tetap ada tombol "→" di
   setiap kartu sebagai jalur alternatif tanpa tetikus.
*/
import { useState } from "react";
import TaskCard from "./TaskCard";
import {
  COLUMNS,
  STATUS_META,
  type Task,
  type TaskStatus,
} from "@/lib/tasks";

export default function TaskBoard({
  tasks,
  onOpen,
  onMove,
  columnOrder = false,
}: {
  tasks: Task[];
  onOpen: (task: Task) => void;
  onMove: (task: Task, status: TaskStatus, beforeId?: string | null) => void;
  /** true = tampilkan fase di dalam kartu (dipakai saat tidak dikelompokkan per fase) */
  columnOrder?: boolean;
}) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  const drop = (status: TaskStatus, beforeId?: string | null) => {
    const task = tasks.find((t) => t.id === dragId);
    setDragId(null);
    setHover(null);
    if (task && (task.status !== status || beforeId)) onMove(task, status, beforeId);
  };

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      {COLUMNS.map((status) => {
        const column = tasks.filter((t) => t.status === status);
        const meta = STATUS_META[status];
        const days = column.reduce((sum, t) => sum + (t.estimate || 0), 0);
        return (
          <section
            key={status}
            data-testid={`task-column-${status}`}
            onDragOver={(e) => {
              e.preventDefault();
              setHover(status);
            }}
            onDragLeave={() => setHover((h) => (h === status ? null : h))}
            onDrop={(e) => {
              e.preventDefault();
              drop(status, null);
            }}
            className={`flex min-h-[160px] flex-col rounded-2xl border bg-zinc-50/60 p-2 transition ${
              hover === status && dragId
                ? "border-accent bg-accent-soft/40"
                : "border-zinc-200"
            }`}
          >
            <header className="flex items-center gap-2 px-1.5 py-1.5">
              <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
              <h3 className="text-[12.5px] font-semibold text-zinc-700">
                {meta.label}
              </h3>
              <span className="rounded-md bg-white px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-500 ring-1 ring-zinc-200">
                {column.length}
              </span>
              {days > 0 && (
                <span className="ml-auto text-[10.5px] text-zinc-400">
                  {days % 1 === 0 ? days : days.toFixed(1)} hari
                </span>
              )}
            </header>

            <div className="flex flex-1 flex-col gap-2">
              {column.map((task) => (
                <div
                  key={task.id}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    drop(status, task.id);
                  }}
                >
                  <TaskCard
                    task={task}
                    onOpen={onOpen}
                    onMove={(t, s) => onMove(t, s, null)}
                    onDragStart={(t) => setDragId(t.id)}
                    dragging={dragId === task.id}
                    compact={!columnOrder}
                  />
                </div>
              ))}
              {!column.length && (
                <p className="rounded-xl border border-dashed border-zinc-200 px-3 py-6 text-center text-[11.5px] text-zinc-400">
                  Tarik kartu ke sini
                </p>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
