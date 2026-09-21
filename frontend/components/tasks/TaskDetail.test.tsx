import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { Task } from "@/lib/tasks";

vi.mock("@/lib/tasks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/tasks")>();
  return {
    ...actual,
    patchTask: vi.fn(),
    addTaskComment: vi.fn(),
    setAcceptance: vi.fn(),
    deleteTask: vi.fn(),
  };
});

import TaskDetail from "./TaskDetail";

const PHASES = [{ id: "i4", name: "Fase 4 — Token, Kuota & Feedback", subtitle: "" }];

function task(over: Partial<Task> = {}): Task {
  return {
    id: "INT-026",
    title: "Feedback 👍/👎 per jawaban",
    description: "Mekanisme kualitas yang jadi bahan bakar perbaikan.",
    phase: "i4",
    status: "todo",
    priority: "critical",
    assignee: "intern2",
    estimate: 1.5,
    labels: ["feedback"],
    acceptance: [{ text: "Satu penilaian per pesan", done: false }],
    depends_on: ["INT-017"],
    evidence: ["projects/ai-agent/backend/app/api/feedback.py"],
    source: "docs/internship/05-kriteria-sukses-dan-demo.md",
    workflow: [
      { step: 1, actor: "Pengguna", action: "Klik 👎", result: "Dialog alasan terbuka" },
      { step: 2, actor: "Backend", action: "UPSERT unik", result: "Tidak menggandakan baris" },
    ],
    wireframe: "+--- DIALOG SETELAH 👎 ---+",
    branch: "",
    mr_url: "",
    commits: [],
    position: 0,
    seeded: true,
    created_at: 0,
    updated_at: 0,
    completed_at: 0,
    branch_name: "feat/INT-026-feedback",
    git_command: "git checkout -b feat/INT-026-feedback",
    acceptance_done: 0,
    acceptance_total: 1,
    progress: 0,
    blocked_by: [],
    ready: true,
    comments: [],
    depends_on_tasks: [{ id: "INT-017", title: "Sitasi", status: "done" }],
    dependents: [],
    ...over,
  };
}

function renderDetail(over: Partial<Task> = {}) {
  return render(
    <TaskDetail
      task={task(over)}
      phases={PHASES}
      priorities={["low", "medium", "high", "critical"]}
      token=""
      onClose={() => undefined}
      onChanged={() => undefined}
      onDeleted={() => undefined}
      onError={() => undefined}
    />
  );
}

afterEach(cleanup);

describe("TaskDetail — tab detail task", () => {
  it("membuka tab Ringkasan lebih dulu dengan deskripsi & prasyarat", () => {
    renderDetail();
    expect((screen.getByLabelText("Deskripsi") as HTMLTextAreaElement).value).toBe(
      "Mekanisme kualitas yang jadi bahan bakar perbaikan."
    );
    expect(screen.getByText("INT-017")).toBeTruthy();
    // tab lain belum dirender — panel tidak ramai
    expect(screen.queryByTestId("task-workflow")).toBeNull();
    expect(screen.queryByTestId("task-wireframe")).toBeNull();
  });

  it("menampilkan langkah workflow bernomor lengkap dengan aktor & hasil", () => {
    renderDetail();
    fireEvent.click(screen.getByRole("tab", { name: /Workflow/ }));
    const list = screen.getByTestId("task-workflow");
    expect(list).toBeTruthy();
    expect(screen.getByText("Pengguna")).toBeTruthy();
    expect(screen.getByText("Klik 👎")).toBeTruthy();
    expect(screen.getByText("Dialog alasan terbuka")).toBeTruthy();
    expect(list.querySelectorAll("li").length).toBe(2);
  });

  it("menampilkan wireframe apa adanya dan daftar berkas bukti", () => {
    renderDetail();
    fireEvent.click(screen.getByRole("tab", { name: /Wireframe/ }));
    expect(screen.getByTestId("task-wireframe").textContent).toContain(
      "DIALOG SETELAH"
    );
    expect(
      screen.getByText("projects/ai-agent/backend/app/api/feedback.py")
    ).toBeTruthy();
  });

  it("memberi pesan jelas bila task belum punya workflow/wireframe", () => {
    renderDetail({ workflow: [], wireframe: "" });
    fireEvent.click(screen.getByRole("tab", { name: /Workflow/ }));
    expect(screen.getByText(/Belum ada workflow/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Wireframe/ }));
    expect(screen.getByText(/Belum ada wireframe/)).toBeTruthy();
  });

  it("memindahkan branch & komentar ke tab Aktivitas", () => {
    renderDetail();
    expect(screen.queryByLabelText("Komentar baru")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /Aktivitas/ }));
    expect(screen.getByLabelText("Komentar baru")).toBeTruthy();
    expect(
      screen.getByText("git checkout -b feat/INT-026-feedback")
    ).toBeTruthy();
  });
});
