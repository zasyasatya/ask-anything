import { describe, expect, it } from "vitest";
import {
  filterTasks,
  formatDays,
  groupByPhase,
  initials,
  nextStatus,
  priorityMeta,
  slugify,
  statusMeta,
  suggestBranch,
  type Task,
} from "./tasks";

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

describe("helper task (id → nama branch GitLab)", () => {
  it("slugify merapikan judul Indonesia menjadi slug aman", () => {
    expect(slugify("Tab Feedback: 👍/👎 + 'Jadikan pedoman'")).toBe(
      "tab-feedback-jadikan-pedoman"
    );
    expect(slugify("   ")).toBe("task");
  });

  it("suggestBranch memakai prefix sesuai label, default feat", () => {
    expect(suggestBranch("ASK-012", "Halaman task management")).toBe(
      "feat/ASK-012-halaman-task-management"
    );
    expect(suggestBranch("ASK-050", "Perbaiki prompt", ["bugfix"])).toBe(
      "fix/ASK-050-perbaiki-prompt"
    );
    expect(suggestBranch("ASK-053", "Dokumentasi env", ["docs"])).toBe(
      "docs/ASK-053-dokumentasi-env"
    );
  });

  it("nextStatus tidak melewati kolom terakhir", () => {
    expect(nextStatus("todo")).toBe("in_progress");
    expect(nextStatus("review")).toBe("done");
    expect(nextStatus("done")).toBe("done");
  });

  it("meta status/prioritas punya fallback aman", () => {
    expect(statusMeta("ngawur").label).toBe("To do");
    expect(statusMeta("review").label).toBe("Review");
    expect(priorityMeta("").label).toBe("Medium");
  });

  it("formatDays & initials enak dibaca", () => {
    expect(formatDays(0)).toBe("—");
    expect(formatDays(2)).toBe("2 hari");
    expect(formatDays(1.5)).toBe("1.5 hari");
    expect(initials("zasya satya")).toBe("ZS");
    expect(initials("")).toBe("?");
  });
});

describe("filter & pengelompokan task", () => {
  const tasks = [
    task({ id: "ASK-001", title: "Tab Pipeline", phase: "f0", labels: ["admin"] }),
    task({
      id: "ASK-030",
      title: "Tool retrieve_knowledge",
      phase: "f3",
      status: "in_progress",
      priority: "critical",
      assignee: "zasya",
      branch: "feat/ASK-030-tool-retrieve-knowledge",
    }),
    task({ id: "ASK-040", title: "ChartRenderer", phase: "f4", labels: ["frontend"] }),
  ];

  it("mencari di id, judul, label, dan nama branch", () => {
    expect(filterTasks(tasks, { ...emptyFilters(), q: "ask-030" }).map((t) => t.id)).toEqual([
      "ASK-030",
    ]);
    expect(filterTasks(tasks, { ...emptyFilters(), q: "chart" }).map((t) => t.id)).toEqual([
      "ASK-040",
    ]);
    expect(
      filterTasks(tasks, { ...emptyFilters(), q: "retrieve_knowledge" }).map((t) => t.id)
    ).toEqual(["ASK-030"]);
  });

  it("kombinasi filter fase + status + prioritas", () => {
    const out = filterTasks(tasks, {
      ...emptyFilters(),
      phase: "f3",
      status: "in_progress",
      priority: "critical",
    });
    expect(out.map((t) => t.id)).toEqual(["ASK-030"]);
  });

  it("groupByPhase menjaga urutan fase dan mengisi yang kosong", () => {
    const phases = [
      { id: "f0", name: "Fase 0", subtitle: "" },
      { id: "f1", name: "Fase 1", subtitle: "" },
      { id: "f3", name: "Fase 3", subtitle: "" },
    ];
    const grouped = groupByPhase(tasks, phases);
    expect(grouped.map((g) => g.phase.id)).toEqual(["f0", "f1", "f3"]);
    expect(grouped[1].tasks).toEqual([]);
    expect(grouped[2].tasks.map((t) => t.id)).toEqual(["ASK-030"]);
  });

  function emptyFilters() {
    return { q: "", phase: "", status: "", assignee: "", priority: "", label: "" };
  }
});
