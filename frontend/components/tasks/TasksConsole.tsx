"use client";
/* Halaman Task Management (/tasks) — papan kerja developer, ringkas tapi
   fungsional seperti Jira/ClickUp:

     * papan kanban drag & drop (atau daftar tabel) untuk seluruh task rencana
       RAG + pekerjaan platform,
     * filter fase/status/assignee/prioritas/label + pencarian,
     * detail task: edit cepat, checklist kriteria, komentar, dependency,
       nama branch GitLab siap salin,
     * sinkronisasi git: branch/commit yang memuat ASK-NNN menaikkan status,
       berkas `evidence` yang ada menandai task siap review.

   Endpoint /api/tasks memakai pengaman yang sama dengan konsol admin: bila
   backend diset ASK_ADMIN_TOKEN, isi token di kolom 🔑 (disimpan di
   localStorage browser ini). */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { readAdminToken, writeAdminToken } from "@/lib/api";
import {
  COLUMNS,
  EMPTY_FILTERS,
  STATUS_META,
  fetchTask,
  fetchTasks,
  filterTasks,
  formatDays,
  groupByPhase,
  moveTask,
  patchTask,
  seedTasks,
  syncTasks,
  type Task,
  type TaskFilters,
  type TaskPhase,
  type TaskStats,
  type TaskStatus,
} from "@/lib/tasks";
import TaskBoard from "./TaskBoard";
import TaskDetail from "./TaskDetail";
import TaskForm from "./TaskForm";
import TaskList from "./TaskList";

export default function TasksConsole() {
  const [token, setToken] = useState("");
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [plan, setPlan] = useState<{ phases: TaskPhase[]; estimate_days: number } | null>(
    null
  );
  const [repo, setRepo] = useState("");
  const [filters, setFilters] = useState<TaskFilters>(EMPTY_FILTERS);
  const [view, setView] = useState<"board" | "list">("board");
  const [grouped, setGrouped] = useState(false);
  const [detail, setDetail] = useState<Task | null>(null);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(
    async (tk = token) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchTasks(tk);
        setTasks(data.tasks);
        setStats(data.stats);
        setPlan({ phases: data.plan.phases, estimate_days: data.plan.estimate_days });
        setRepo(data.repo);
      } catch (e) {
        setError(
          String(e).includes("401")
            ? "Backend meminta token admin (ASK_ADMIN_TOKEN). Isi lewat tombol 🔑."
            : `${e} — pastikan backend berjalan (python run.py).`
        );
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  useEffect(() => {
    const saved = readAdminToken();
    setToken(saved);
    load(saved);
    // hanya saat mount: refresh berikutnya dipicu aksi user / tombol muat ulang
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const phases = plan?.phases || [];
  const visible = useMemo(() => filterTasks(tasks, filters), [tasks, filters]);
  const assignees = useMemo(
    () => Object.keys(stats?.assignees || {}).sort(),
    [stats]
  );
  const labels = useMemo(() => Object.keys(stats?.labels || {}).sort(), [stats]);

  const replaceTask = (updated: Task) => {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)));
    setDetail((d) => (d && d.id === updated.id ? { ...d, ...updated } : d));
  };

  const applyResult = (res: { tasks: Task[]; stats: TaskStats }) => {
    setTasks(res.tasks);
    setStats(res.stats);
  };

  const handleMove = async (
    task: Task,
    status: TaskStatus,
    beforeId?: string | null
  ) => {
    // optimistis: kartu langsung pindah, lalu diselaraskan dengan server
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status } : t))
    );
    try {
      const res = await moveTask(token, task.id, status, beforeId);
      applyResult(res);
      if (detail?.id === task.id) setDetail({ ...detail, ...res.task });
    } catch (e) {
      setError(String(e));
      load();
    }
  };

  const handleSync = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const report = await syncTasks(token);
      setTasks(report.tasks);
      setStats(report.stats);
      setNotice(
        report.changed.length
          ? `Sync selesai: ${report.changed.length} task diperbarui (${report.branches} branch, ${report.commits} commit diperiksa).`
          : `Sync selesai: tidak ada perubahan (${report.branches} branch, ${report.commits} commit diperiksa).`
      );
      if (report.note) setNotice((n) => `${n} ${report.note}`);
      if (detail) setDetail(await fetchTask(token, detail.id));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleSeed = async (reset: boolean) => {
    if (
      reset &&
      typeof window !== "undefined" &&
      !window.confirm(
        "Kembalikan task rencana RAG ke kondisi awal? Task buatan sendiri tetap aman."
      )
    )
      return;
    setBusy(true);
    try {
      const report = await seedTasks(token, reset);
      await load();
      setNotice(
        report.created.length
          ? `${report.created.length} task rencana dimuat.`
          : "Semua task rencana sudah ada (tidak ada yang dibuat ulang)."
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const openDetail = async (task: Task) => {
    setDetail(task);
    try {
      setDetail(await fetchTask(token, task.id));
    } catch (e) {
      setError(String(e));
    }
  };

  const statusChips = COLUMNS.map((s) => ({
    status: s,
    count: stats?.per_status?.[s] ?? 0,
  }));

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-5 py-3">
          <Link
            href="/"
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
          >
            ← Chat
          </Link>
          <h1 className="text-[15px] font-semibold text-zinc-800">
            Task Management — Rencana RAG &amp; Platform
          </h1>
          <span
            className="hidden rounded-lg border border-zinc-200 px-2 py-1 font-mono text-[11px] text-zinc-400 lg:inline"
            title="Folder repo yang dipakai untuk sinkronisasi branch/commit"
          >
            {repo || "repo: —"}
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button
              onClick={() => setTokenOpen((v) => !v)}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
              title="Token admin (ASK_ADMIN_TOKEN) bila backend dilindungi"
            >
              🔑 Token
            </button>
            <button
              onClick={() => handleSeed(false)}
              disabled={busy}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
            >
              Muat rencana RAG
            </button>
            <button
              onClick={() => handleSeed(true)}
              disabled={busy}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
              title="Hapus task rencana lalu buat ulang dari tasks_plan.py"
            >
              Reset rencana
            </button>
            <button
              onClick={handleSync}
              disabled={busy}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-40"
              title="Selaraskan status dengan branch/commit git & berkas implementasi"
            >
              {busy ? "…" : "⟳ Sync git"}
            </button>
            <button
              onClick={() => setCreating(true)}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:brightness-95"
            >
              + Task baru
            </button>
          </div>
        </div>

        {tokenOpen && (
          <div className="mx-auto flex max-w-7xl items-center gap-2 px-5 pb-2">
            <input
              aria-label="Token admin"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="ASK_ADMIN_TOKEN (kosongkan bila konsol terbuka)"
              className="w-80 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12px]"
            />
            <button
              onClick={() => {
                writeAdminToken(token);
                setTokenOpen(false);
                load();
              }}
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-[12px] font-medium text-white"
            >
              Simpan
            </button>
          </div>
        )}

        {/* statistik ringkas */}
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-5 pb-2">
          <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-1.5">
            <span className="text-[11px] text-zinc-500">Progres</span>
            <div className="h-2 w-28 overflow-hidden rounded-full bg-zinc-100">
              <div
                className="h-full rounded-full bg-emerald-500"
                style={{ width: `${stats?.progress ?? 0}%` }}
              />
            </div>
            <b className="text-[12px] text-zinc-700">{stats?.progress ?? 0}%</b>
          </div>
          {statusChips.map(({ status, count }) => (
            <button
              key={status}
              onClick={() => setFilters((f) => ({ ...f, status: f.status === status ? "" : status }))}
              className={`rounded-xl border px-2.5 py-1.5 text-[11.5px] font-medium transition ${
                filters.status === status
                  ? STATUS_META[status].chip
                  : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50"
              }`}
              title={`Saring kolom ${STATUS_META[status].label}`}
            >
              {STATUS_META[status].label} {count}
            </button>
          ))}
          <span className="rounded-xl border border-zinc-200 bg-white px-2.5 py-1.5 text-[11.5px] text-zinc-500">
            {formatDays(plan?.estimate_days ?? 0)} total rencana
          </span>
          {!!stats?.blocked && (
            <span className="rounded-xl border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-[11.5px] text-rose-600">
              ⛔ {stats.blocked} task menunggu prasyarat
            </span>
          )}
          {!!stats?.ready && (
            <span className="rounded-xl border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-[11.5px] text-emerald-700">
              ▶ {stats.ready} siap dikerjakan
            </span>
          )}
        </div>

        {/* filter */}
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-5 pb-3">
          <input
            aria-label="Cari task"
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
            placeholder="cari id, judul, label, branch…"
            className="w-56 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-[12px]"
          />
          <select
            aria-label="Filter fase"
            value={filters.phase}
            onChange={(e) => setFilters((f) => ({ ...f, phase: e.target.value }))}
            className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px] text-zinc-600"
          >
            <option value="">Semua fase</option>
            {phases.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter assignee"
            value={filters.assignee}
            onChange={(e) => setFilters((f) => ({ ...f, assignee: e.target.value }))}
            className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px] text-zinc-600"
          >
            <option value="">Semua orang</option>
            {assignees.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter prioritas"
            value={filters.priority}
            onChange={(e) => setFilters((f) => ({ ...f, priority: e.target.value }))}
            className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px] text-zinc-600"
          >
            <option value="">Semua prioritas</option>
            {["low", "medium", "high", "critical"].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {!!labels.length && (
            <select
              aria-label="Filter label"
              value={filters.label}
              onChange={(e) => setFilters((f) => ({ ...f, label: e.target.value }))}
              className="rounded-lg border border-zinc-200 px-2 py-1.5 text-[12px] text-zinc-600"
            >
              <option value="">Semua label</option>
              {labels.map((l) => (
                <option key={l} value={l}>
                  #{l}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => setFilters(EMPTY_FILTERS)}
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[12px] text-zinc-500 hover:bg-zinc-50"
          >
            Bersihkan
          </button>
          <div className="ml-auto flex items-center gap-1 rounded-lg border border-zinc-200 bg-white p-0.5">
            {(["board", "list"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-md px-2.5 py-1 text-[12px] font-medium ${
                  view === v ? "bg-accent-soft text-accent" : "text-zinc-500"
                }`}
              >
                {v === "board" ? "Papan" : "Daftar"}
              </button>
            ))}
          </div>
          {view === "board" && (
            <label className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-[12px] text-zinc-500">
              <input
                type="checkbox"
                checked={grouped}
                onChange={(e) => setGrouped(e.target.checked)}
                className="h-3.5 w-3.5 accent-indigo-500"
              />
              Kelompokkan per fase
            </label>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-5">
        {error && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700">
            {error}
          </p>
        )}
        {notice && (
          <p className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-[13px] text-emerald-800">
            <span className="flex-1">{notice}</span>
            <button onClick={() => setNotice(null)} className="text-emerald-600">
              ×
            </button>
          </p>
        )}

        {loading && !tasks.length && (
          <p className="rounded-2xl border border-zinc-200 bg-white px-4 py-10 text-center text-[13px] text-zinc-400">
            Memuat papan task…
          </p>
        )}

        {!loading && !tasks.length && (
          <div className="rounded-2xl border border-dashed border-zinc-300 bg-white px-4 py-12 text-center">
            <p className="text-[13.5px] text-zinc-500">
              Papan masih kosong. Muat rencana RAG (54 task) untuk mulai tracking.
            </p>
            <button
              onClick={() => handleSeed(false)}
              className="mt-3 rounded-lg bg-accent px-3.5 py-2 text-[13px] font-medium text-white"
            >
              Muat rencana RAG
            </button>
          </div>
        )}

        {!loading && !!tasks.length && (
          <>
            <p data-testid="task-count" className="mb-3 text-[12px] text-zinc-500">
              {visible.length} dari {tasks.length} task tampil
              {filters.q || filters.phase || filters.status || filters.assignee ||
              filters.priority || filters.label
                ? " (difilter)"
                : ""}
              {" · "}
              <button
                onClick={() => load()}
                className="font-medium text-accent hover:underline"
              >
                muat ulang
              </button>
            </p>

            {view === "list" ? (
              <TaskList
                tasks={visible}
                phases={phases}
                onOpen={openDetail}
                onMove={(task, status) => handleMove(task, status, null)}
              />
            ) : grouped ? (
              <div className="space-y-6">
                {groupByPhase(visible, phases).map(({ phase, tasks: phaseTasks }) => {
                  const done = phaseTasks.filter((t) => t.status === "done").length;
                  return (
                    <section key={phase.id}>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <h2 className="text-[13px] font-semibold text-zinc-700">
                          {phase.name}
                        </h2>
                        <span className="text-[11.5px] text-zinc-400">
                          {phase.subtitle}
                        </span>
                        <span className="ml-auto rounded-md bg-white px-2 py-0.5 font-mono text-[11px] text-zinc-500 ring-1 ring-zinc-200">
                          {done}/{phaseTasks.length} selesai
                        </span>
                      </div>
                      {phaseTasks.length ? (
                        <TaskBoard
                          tasks={phaseTasks}
                          onOpen={openDetail}
                          onMove={handleMove}
                          columnOrder
                        />
                      ) : (
                        <p className="rounded-xl border border-dashed border-zinc-200 bg-white px-3 py-4 text-center text-[12px] text-zinc-400">
                          Tidak ada task di fase ini untuk filter aktif.
                        </p>
                      )}
                    </section>
                  );
                })}
              </div>
            ) : (
              <TaskBoard tasks={visible} onOpen={openDetail} onMove={handleMove} />
            )}
          </>
        )}
      </main>

      {detail && (
        <TaskDetail
          task={detail}
          token={token}
          phases={phases}
          priorities={["low", "medium", "high", "critical"]}
          onClose={() => setDetail(null)}
          onChanged={(task) => replaceTask(task)}
          onDeleted={(id) => {
            setTasks((prev) => prev.filter((t) => t.id !== id));
            setDetail(null);
            load();
          }}
          onError={(m) => setError(m)}
        />
      )}

      {creating && (
        <TaskForm
          token={token}
          phases={phases}
          defaultPhase={filters.phase || phases[0]?.id || "f0"}
          suggestions={{
            assignees: assignees.length ? assignees : ["dev"],
            labels,
          }}
          onClose={() => setCreating(false)}
          onCreated={async (task) => {
            setCreating(false);
            setNotice(`Task ${task.id} dibuat — branch: ${task.branch_name}`);
            const refreshed = await fetchTasks(token);
            setTasks(refreshed.tasks);
            setStats(refreshed.stats);
            setDetail(await fetchTask(token, task.id));
          }}
          onError={(m) => setError(m)}
        />
      )}
    </div>
  );
}

/** Helper kecil yang dipakai halaman saat mengubah status dari daftar. */
export async function patchStatus(token: string, id: string, status: TaskStatus) {
  return patchTask(token, id, { status });
}
