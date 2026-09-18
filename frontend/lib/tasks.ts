/* Task management (/tasks) — tipe data, pemanggilan API, dan helper tampilan.

   Papan ini adalah proyeksi `backend/app/tasks_plan.py`: seluruh task rencana
   RAG + pekerjaan platform sudah ter-seed otomatis, dan **id task (ASK-NNN)
   dipakai sebagai nama branch GitLab** (`feat/ASK-012-judul-singkat`).
   Helper `suggestBranch()`/`slugify()` di sini meniru logika backend supaya
   form pembuatan task bisa menampilkan nama branch sebelum disimpan. */

import { adminHeaders, fetchJson, readAdminToken } from "./api";

export type TaskStatus = "backlog" | "todo" | "in_progress" | "review" | "done";
export type TaskPriority = "low" | "medium" | "high" | "critical";

export interface TaskAcceptance {
  text: string;
  done: boolean;
}

export interface TaskCommit {
  sha: string;
  subject: string;
}

export interface TaskComment {
  id: string;
  task_id: string;
  author: string;
  kind: "comment" | "activity" | string;
  body: string;
  created_at: number;
}

export interface TaskDep {
  id: string;
  title: string;
  status: string;
  missing?: boolean;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  phase: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee: string;
  estimate: number;
  labels: string[];
  acceptance: TaskAcceptance[];
  depends_on: string[];
  evidence: string[];
  source: string;
  branch: string;
  mr_url: string;
  commits: TaskCommit[];
  position: number;
  seeded: boolean;
  created_at: number;
  updated_at: number;
  completed_at: number;
  // turunan dari backend
  branch_name: string;
  git_command: string;
  acceptance_done: number;
  acceptance_total: number;
  progress: number;
  blocked_by: string[];
  ready: boolean;
  // hanya pada detail
  comments?: TaskComment[];
  depends_on_tasks?: TaskDep[];
  dependents?: TaskDep[];
}

export interface TaskStats {
  total: number;
  done: number;
  open: number;
  progress: number;
  per_status: Record<string, number>;
  per_phase: Record<string, { total: number; done: number }>;
  per_priority: Record<string, number>;
  estimate_total: number;
  estimate_done: number;
  assignees: Record<string, number>;
  labels: Record<string, number>;
  blocked: number;
  ready: number;
  statuses: TaskStatus[];
  status_labels: Record<string, string>;
  phases: TaskPhase[];
  priorities: TaskPriority[];
}

export interface TaskPhase {
  id: string;
  name: string;
  subtitle: string;
}

export interface TaskPlan {
  phases: TaskPhase[];
  total: number;
  per_phase: Record<string, number>;
  per_priority: Record<string, number>;
  estimate_days: number;
}

export interface TaskListResponse {
  tasks: Task[];
  stats: TaskStats;
  plan: TaskPlan;
  statuses: TaskStatus[];
  repo: string;
}

export interface SyncReport {
  repo: string;
  is_repo: boolean;
  branches: number;
  commits: number;
  changed: Array<{ id: string; status: string; notes: string }>;
  note?: string;
  stats: TaskStats;
  tasks: Task[];
}

export interface TaskFilters {
  q: string;
  phase: string;
  status: string;
  assignee: string;
  priority: string;
  label: string;
  mine?: boolean;
}

export const EMPTY_FILTERS: TaskFilters = {
  q: "",
  phase: "",
  status: "",
  assignee: "",
  priority: "",
  label: "",
};

// ---------------------------------------------------------------------------
// Meta tampilan
// ---------------------------------------------------------------------------

export const STATUS_META: Record<
  TaskStatus,
  { label: string; chip: string; dot: string; ring: string }
> = {
  backlog: {
    label: "Backlog",
    chip: "bg-zinc-100 text-zinc-600 border-zinc-200",
    dot: "bg-zinc-400",
    ring: "border-zinc-200",
  },
  todo: {
    label: "To do",
    chip: "bg-sky-50 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
    ring: "border-sky-200",
  },
  in_progress: {
    label: "In progress",
    chip: "bg-indigo-50 text-indigo-700 border-indigo-200",
    dot: "bg-indigo-500",
    ring: "border-indigo-200",
  },
  review: {
    label: "Review",
    chip: "bg-amber-50 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
    ring: "border-amber-200",
  },
  done: {
    label: "Done",
    chip: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
    ring: "border-emerald-200",
  },
};

export const PRIORITY_META: Record<
  TaskPriority,
  { label: string; chip: string; bar: string }
> = {
  low: { label: "Low", chip: "bg-zinc-100 text-zinc-500", bar: "bg-zinc-300" },
  medium: { label: "Medium", chip: "bg-sky-100 text-sky-700", bar: "bg-sky-400" },
  high: { label: "High", chip: "bg-amber-100 text-amber-800", bar: "bg-amber-500" },
  critical: {
    label: "Critical",
    chip: "bg-rose-100 text-rose-700",
    bar: "bg-rose-500",
  },
};

/** Kolom papan, urut. */
export const COLUMNS: TaskStatus[] = ["backlog", "todo", "in_progress", "review", "done"];

export function statusMeta(status: string) {
  return STATUS_META[(status as TaskStatus) in STATUS_META ? (status as TaskStatus) : "todo"];
}

export function priorityMeta(priority: string) {
  return (
    PRIORITY_META[
      (priority as TaskPriority) in PRIORITY_META ? (priority as TaskPriority) : "medium"
    ] || PRIORITY_META.medium
  );
}

export function nextStatus(status: TaskStatus): TaskStatus {
  const i = COLUMNS.indexOf(status);
  return COLUMNS[Math.min(i + 1, COLUMNS.length - 1)];
}

// ---------------------------------------------------------------------------
// Helper (meniru backend — dipakai untuk pratinjau branch & ringkasan)
// ---------------------------------------------------------------------------

export function slugify(text: string, maxLen = 42): string {
  const slug = (text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug.slice(0, maxLen).replace(/-+$/g, "") || "task";
}

/** Nama branch yang disarankan backend: `feat/ASK-012-judul-singkat`. */
export function suggestBranch(
  id: string,
  title: string,
  labels: string[] = []
): string {
  const map: Record<string, string> = {
    bug: "fix",
    bugfix: "fix",
    docs: "docs",
    test: "test",
    testing: "test",
    performance: "perf",
  };
  const key = labels.find((l) => map[l]);
  const prefix = key ? map[key] : "feat";
  return `${prefix}/${(id || "ASK-NEW").toUpperCase()}-${slugify(title)}`;
}

export function filterTasks(tasks: Task[], f: TaskFilters): Task[] {
  const q = f.q.trim().toLowerCase();
  return tasks.filter((t) => {
    if (f.phase && t.phase !== f.phase) return false;
    if (f.status && t.status !== f.status) return false;
    if (f.assignee && t.assignee !== f.assignee) return false;
    if (f.priority && t.priority !== f.priority) return false;
    if (f.label && !t.labels.includes(f.label)) return false;
    if (!q) return true;
    const haystack = [
      t.id,
      t.title,
      t.description,
      t.assignee,
      t.branch,
      t.branch_name,
      t.labels.join(" "),
      t.source,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

export function groupByPhase(
  tasks: Task[],
  phases: TaskPhase[]
): Array<{ phase: TaskPhase; tasks: Task[] }> {
  return phases.map((phase) => ({
    phase,
    tasks: tasks.filter((t) => t.phase === phase.id),
  }));
}

export function initials(name: string): string {
  const parts = (name || "?").trim().split(/[\s._-]+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase();
}

export function formatDays(days: number): string {
  if (!days) return "—";
  return `${Number.isInteger(days) ? days : days.toFixed(1)} hari`;
}

export function formatDate(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toLocaleDateString("id-ID", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
    });
  } catch {
    return String(ts);
  }
}

export function relativeTime(ts: number): string {
  if (!ts) return "—";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "baru saja";
  if (diff < 3600) return `${Math.floor(diff / 60)} menit lalu`;
  if (diff < 86_400) return `${Math.floor(diff / 3600)} jam lalu`;
  if (diff < 2_592_000) return `${Math.floor(diff / 86_400)} hari lalu`;
  return formatDate(ts);
}

// ---------------------------------------------------------------------------
// API (endpoint dilindungi ASK_ADMIN_TOKEN bila diset di backend)
// ---------------------------------------------------------------------------

function headers(token: string): Record<string, string> {
  return adminHeaders(token || readAdminToken());
}

export interface NewTaskInput {
  title: string;
  description?: string;
  phase?: string;
  status?: string;
  priority?: string;
  assignee?: string;
  estimate?: number;
  labels?: string[];
  acceptance?: Array<string | TaskAcceptance>;
  depends_on?: string[];
  source?: string;
}

export async function fetchTasks(
  token: string,
  params: Partial<Record<string, string>> = {}
): Promise<TaskListResponse> {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v) as [string, string][]
  ).toString();
  return fetchJson<TaskListResponse>(`/api/tasks${qs ? `?${qs}` : ""}`, {
    headers: headers(token),
  });
}

export async function fetchTask(
  token: string,
  id: string
): Promise<Task> {
  const d = await fetchJson<{ task: Task }>(`/api/tasks/${id}`, {
    headers: headers(token),
  });
  return d.task;
}

export async function createTask(
  token: string,
  input: NewTaskInput
): Promise<Task> {
  const d = await fetchJson<{ task: Task }>("/api/tasks", {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(input),
  });
  return d.task;
}

export async function patchTask(
  token: string,
  id: string,
  patch: Record<string, unknown>
): Promise<Task> {
  const d = await fetchJson<{ task: Task }>(`/api/tasks/${id}`, {
    method: "PATCH",
    headers: headers(token),
    body: JSON.stringify(patch),
  });
  return d.task;
}

export async function deleteTask(token: string, id: string): Promise<void> {
  await fetchJson(`/api/tasks/${id}`, { method: "DELETE", headers: headers(token) });
}

export async function moveTask(
  token: string,
  id: string,
  status: TaskStatus,
  beforeId?: string | null
): Promise<{ task: Task; stats: TaskStats; tasks: Task[] }> {
  return fetchJson(`/api/tasks/${id}/move`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ status, before_id: beforeId || null }),
  });
}

export async function addTaskComment(
  token: string,
  id: string,
  body: string,
  author = "dev"
): Promise<TaskComment[]> {
  const d = await fetchJson<{ comments: TaskComment[] }>(
    `/api/tasks/${id}/comments`,
    {
      method: "POST",
      headers: headers(token),
      body: JSON.stringify({ body, author }),
    }
  );
  return d.comments;
}

export async function setAcceptance(
  token: string,
  id: string,
  action: { index?: number; done?: boolean; text?: string; remove?: boolean }
): Promise<Task> {
  const d = await fetchJson<{ task: Task }>(`/api/tasks/${id}/acceptance`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify(action),
  });
  return d.task;
}

export async function syncTasks(token: string): Promise<SyncReport> {
  return fetchJson<SyncReport>("/api/tasks/sync", {
    method: "POST",
    headers: headers(token),
  });
}

export async function seedTasks(
  token: string,
  reset = false
): Promise<{ created: string[]; total: number; stats: TaskStats }> {
  return fetchJson(`/api/tasks/seed?reset=${reset ? "true" : "false"}`, {
    method: "POST",
    headers: headers(token),
  });
}
