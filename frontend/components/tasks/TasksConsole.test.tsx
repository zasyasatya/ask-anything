import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Task, TaskListResponse } from "@/lib/tasks";

vi.mock("@/lib/tasks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/tasks")>();
  return {
    ...actual,
    fetchTasks: vi.fn(),
    fetchTask: vi.fn(),
    moveTask: vi.fn(),
    syncTasks: vi.fn(),
    seedTasks: vi.fn(),
    createTask: vi.fn(),
    patchTask: vi.fn(),
    addTaskComment: vi.fn(),
    setAcceptance: vi.fn(),
    deleteTask: vi.fn(),
  };
});

import TasksConsole from "./TasksConsole";
import { fetchTasks, moveTask, syncTasks, type SyncReport } from "@/lib/tasks";

function task(over: Partial<Task>): Task {
  return {
    id: "ASK-001",
    title: "Contoh",
    description: "",
    phase: "f0",
    status: "todo",
    priority: "medium",
    assignee: "",
    estimate: 1,
    labels: [],
    acceptance: [],
    depends_on: [],
    evidence: [],
    source: "",
    branch: "",
    mr_url: "",
    commits: [],
    position: 0,
    seeded: true,
    created_at: 0,
    updated_at: 0,
    completed_at: 0,
    branch_name: "feat/ASK-001-contoh",
    git_command: "git checkout -b feat/ASK-001-contoh",
    acceptance_done: 0,
    acceptance_total: 0,
    progress: 0,
    blocked_by: [],
    ready: true,
    ...over,
  };
}

const PHASES = [
  { id: "f0", name: "Fase 0 — Platform", subtitle: "admin" },
  { id: "solo", name: "Fase 1 — Ingest", subtitle: "parser" },
];

function response(tasks: Task[]): TaskListResponse {
  return {
    tasks,
    stats: {
      total: tasks.length,
      done: tasks.filter((t) => t.status === "done").length,
      open: tasks.filter((t) => t.status !== "done").length,
      progress: 40,
      per_status: { backlog: 0, todo: 1, in_progress: 1, review: 0, done: 0 },
      per_phase: { f0: { total: 1, done: 0 }, solo: { total: 1, done: 0 } },
      per_priority: { low: 0, medium: 1, high: 0, critical: 1 },
      estimate_total: 5,
      estimate_done: 1,
      assignees: { zasya: 1 },
      labels: { admin: 1 },
      blocked: 0,
      ready: 0,
      statuses: ["backlog", "todo", "in_progress", "review", "done"],
      status_labels: {},
      phases: PHASES,
      priorities: ["low", "medium", "high", "critical"],
    },
    plan: {
      phases: PHASES,
      total: tasks.length,
      per_phase: { f0: 1, solo: 1 },
      per_priority: {},
      estimate_days: 5,
    },
    statuses: ["backlog", "todo", "in_progress", "review", "done"],
    repo: "/repo/ask-anything",
  };
}

const TASKS: Task[] = [
  task({ id: "ASK-001", title: "Tab Pipeline", phase: "f0", labels: ["admin"] }),
  task({
    id: "ASK-030",
    title: "Tool retrieve_knowledge",
    phase: "solo",
    status: "in_progress",
    priority: "critical",
    assignee: "zasya",
  }),
];

beforeEach(() => {
  vi.mocked(fetchTasks).mockResolvedValue(response(TASKS));
  vi.mocked(syncTasks).mockResolvedValue({
    repo: "/repo/ask-anything",
    is_repo: true,
    branches: 3,
    commits: 12,
    changed: [{ id: "ASK-030", status: "review", notes: "branch terdeteksi" }],
    stats: response(TASKS).stats,
    tasks: TASKS,
  } satisfies SyncReport);
  vi.mocked(moveTask).mockResolvedValue({
    task: { ...TASKS[0], status: "in_progress" },
    tasks: TASKS,
    stats: response(TASKS).stats,
  });
  window.localStorage.clear();
});

afterEach(cleanup);

describe("TasksConsole — halaman /tasks", () => {
  it("memuat papan dari API dan menampilkan statistik + repo", async () => {
    render(<TasksConsole />);
    await waitFor(() => expect(fetchTasks).toHaveBeenCalled());
    expect(await screen.findByText("Tab Pipeline")).toBeTruthy();
    expect(screen.getByText("Tool retrieve_knowledge")).toBeTruthy();
    expect(screen.getByText("/repo/ask-anything")).toBeTruthy();
    expect(screen.getByTestId("task-count").textContent).toContain("2 dari 2 task tampil");
    expect(screen.getByText("40%")).toBeTruthy();
  });

  it("pencarian & filter mempersempit kartu yang tampil", async () => {
    render(<TasksConsole />);
    await screen.findByText("Tab Pipeline");

    fireEvent.change(screen.getByLabelText("Cari task"), {
      target: { value: "retrieve" },
    });
    await waitFor(() => expect(screen.queryByText("Tab Pipeline")).toBeNull());
    expect(screen.getByText("Tool retrieve_knowledge")).toBeTruthy();
    expect(screen.getByTestId("task-count").textContent).toContain(
      "1 dari 2 task tampil (difilter)"
    );
  });

  it("memindahkan kartu ke kolom lain memanggil API move", async () => {
    render(<TasksConsole />);
    await screen.findByText("Tab Pipeline");
    fireEvent.click(screen.getByLabelText("Pindahkan ASK-001 ke In progress"));
    await waitFor(() =>
      expect(moveTask).toHaveBeenCalledWith("", "ASK-001", "in_progress", null)
    );
  });

  it("sync git melaporkan berapa task yang berubah", async () => {
    render(<TasksConsole />);
    await screen.findByText("Tab Pipeline");
    fireEvent.click(screen.getByTitle(/Selaraskan status dengan branch/));
    expect(await screen.findByText(/Sync selesai: 1 task diperbarui/)).toBeTruthy();
    expect(syncTasks).toHaveBeenCalledWith("");
  });

  it("membuka detail menampilkan perintah branch GitLab siap salin", async () => {
    const { fetchTask } = await import("@/lib/tasks");
    vi.mocked(fetchTask).mockResolvedValue({
      ...TASKS[1],
      comments: [
        {
          id: "c1",
          task_id: "ASK-030",
          author: "dev",
          kind: "comment",
          body: "mulai dari filter metadata",
          created_at: Date.now() / 1000,
        },
      ],
      depends_on_tasks: [
        { id: "ASK-024", title: "API rag/query", status: "review" },
      ],
      dependents: [],
      git_command: "git checkout -b feat/ASK-030-tool-retrieve-knowledge",
    });
    render(<TasksConsole />);
    await screen.findByText("Tool retrieve_knowledge");

    fireEvent.click(screen.getByTestId("task-open-ASK-030"));
    await waitFor(() => expect(fetchTask).toHaveBeenCalledWith("", "ASK-030"));
    expect(await screen.findByTestId("task-detail")).toBeTruthy();
    expect(
      screen.getByText("git checkout -b feat/ASK-030-tool-retrieve-knowledge")
    ).toBeTruthy();
    expect(screen.getByText("mulai dari filter metadata")).toBeTruthy();
    expect(screen.getByText("ASK-024")).toBeTruthy();
  });
});
