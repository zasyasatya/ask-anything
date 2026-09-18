import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import TaskBoard from "./TaskBoard";
import type { Task } from "@/lib/tasks";

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

const TASKS: Task[] = [
  task({ id: "ASK-001", title: "Tab Pipeline", status: "todo" }),
  task({
    id: "ASK-030",
    title: "Tool retrieve_knowledge",
    status: "in_progress",
    priority: "critical",
    assignee: "zasya",
    acceptance: [
      { text: "tool terdaftar", done: true },
      { text: "argumen tervalidasi", done: false },
    ],
    acceptance_done: 1,
    acceptance_total: 2,
    progress: 50,
    blocked_by: ["ASK-024"],
  }),
];

afterEach(cleanup);

describe("TaskBoard — papan kanban", () => {
  it("menaruh kartu di kolom sesuai status & menampilkan kolom kosong", () => {
    render(<TaskBoard tasks={TASKS} onOpen={vi.fn()} onMove={vi.fn()} />);
    const todo = screen.getByTestId("task-column-todo");
    const progress = screen.getByTestId("task-column-in_progress");
    const done = screen.getByTestId("task-column-done");

    expect(todo.textContent).toContain("Tab Pipeline");
    expect(progress.textContent).toContain("Tool retrieve_knowledge");
    expect(progress.textContent).toContain("50%");
    expect(progress.textContent).toContain("⛔ 1");        // penanda blocker
    expect(done.textContent).toContain("Tarik kartu ke sini");
  });

  it("drag & drop memindahkan kartu ke kolom lain", () => {
    const onMove = vi.fn();
    render(<TaskBoard tasks={TASKS} onOpen={vi.fn()} onMove={onMove} />);
    const card = screen.getByTestId("task-card-ASK-001");

    fireEvent.dragStart(card, { dataTransfer: { setData: vi.fn() } });
    fireEvent.dragOver(screen.getByTestId("task-column-review"));
    fireEvent.drop(screen.getByTestId("task-column-review"));
    expect(onMove).toHaveBeenCalledWith(
      expect.objectContaining({ id: "ASK-001" }),
      "review",
      null
    );
  });

  it("tombol → memindahkan ke status berikutnya (tanpa mouse)", () => {
    const onMove = vi.fn();
    render(<TaskBoard tasks={TASKS} onOpen={vi.fn()} onMove={onMove} />);
    fireEvent.click(screen.getByLabelText("Pindahkan ASK-001 ke In progress"));
    expect(onMove).toHaveBeenCalledWith(
      expect.objectContaining({ id: "ASK-001" }),
      "in_progress",
      null
    );
  });

  it("klik judul membuka detail", () => {
    const onOpen = vi.fn();
    render(<TaskBoard tasks={TASKS} onOpen={onOpen} onMove={vi.fn()} />);
    fireEvent.click(screen.getByTestId("task-open-ASK-030"));
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "ASK-030" }));
  });
});
