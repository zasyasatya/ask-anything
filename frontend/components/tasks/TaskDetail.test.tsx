import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Task } from "@/lib/tasks";

vi.mock("@/lib/tasks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/tasks")>();
  return {
    ...actual,
    patchTask: vi.fn(),
    fetchTask: vi.fn(),
    addTaskComment: vi.fn(),
    setAcceptance: vi.fn(),
    deleteTask: vi.fn(),
  };
});

import { fetchTask, patchTask } from "@/lib/tasks";
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

function renderDetail(
  over: Partial<Task> = {},
  extra: { onChanged?: (t: Task) => void; readOnly?: boolean } = {}
) {
  return render(
    <TaskDetail
      task={task(over)}
      phases={PHASES}
      priorities={["low", "medium", "high", "critical"]}
      token=""
      onClose={() => undefined}
      onChanged={extra.onChanged ?? (() => undefined)}
      onDeleted={() => undefined}
      onError={() => undefined}
      readOnly={extra.readOnly}
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

describe("TaskDetail — task bisa disunting", () => {
  it("mengubah alur kerja: tambah, hapus, urutkan, lalu simpan sekali", async () => {
    vi.mocked(patchTask).mockClear();
    vi.mocked(patchTask).mockResolvedValue(task({ edited: true }));
    const onChanged = vi.fn();
    renderDetail({}, { onChanged });
    fireEvent.click(screen.getByRole("tab", { name: /Workflow/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ubah alur kerja" }));
    expect(screen.getByTestId("workflow-editor")).toBeTruthy();

    // belum ada perubahan -> tombol simpan nonaktif
    const save = screen.getByRole("button", {
      name: "Simpan alur kerja",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);

    // hapus langkah 1, tambah langkah baru
    fireEvent.click(screen.getByRole("button", { name: "Hapus langkah 1" }));
    fireEvent.click(screen.getByRole("button", { name: "+ Tambah langkah" }));
    fireEvent.change(screen.getByLabelText("Aksi langkah 2"), {
      target: { value: "Tulis test kontrak" },
    });
    fireEvent.change(screen.getByLabelText("Aktor langkah 2"), {
      target: { value: "Intern" },
    });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);

    await waitFor(() => expect(patchTask).toHaveBeenCalledTimes(1));
    expect(patchTask).toHaveBeenCalledWith("", "INT-026", {
      workflow: [
        { actor: "Backend", action: "UPSERT unik", result: "Tidak menggandakan baris" },
        { actor: "Intern", action: "Tulis test kontrak", result: "" },
      ],
    });
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    // editor menutup diri setelah tersimpan
    await waitFor(() => expect(screen.queryByTestId("workflow-editor")).toBeNull());
  });

  it("langkah kosong tidak dianggap perubahan", () => {
    renderDetail();
    fireEvent.click(screen.getByRole("tab", { name: /Workflow/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ubah alur kerja" }));
    fireEvent.click(screen.getByRole("button", { name: "+ Tambah langkah" }));
    // langkah ke-3 dibiarkan kosong -> sama dengan kondisi awal -> tidak ada yang disimpan
    const save = screen.getByRole("button", {
      name: "Simpan alur kerja",
    }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });

  it("mengubah wireframe dan berkas bukti dalam satu PATCH", async () => {
    vi.mocked(patchTask).mockClear();
    vi.mocked(patchTask).mockResolvedValue(task({ edited: true }));
    renderDetail();
    fireEvent.click(screen.getByRole("tab", { name: /Wireframe/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ubah wireframe" }));
    fireEvent.change(screen.getByLabelText("Wireframe"), {
      target: { value: "+--- BARU ---+" },
    });
    fireEvent.change(screen.getByLabelText("Berkas bukti"), {
      target: { value: "a/b.py\n\n  c/d.tsx  \n" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Simpan" }));
    await waitFor(() =>
      expect(patchTask).toHaveBeenCalledWith("", "INT-026", {
        wireframe: "+--- BARU ---+",
        evidence: ["a/b.py", "c/d.tsx"],
      })
    );
  });

  it("membatalkan suntingan tidak memanggil API", () => {
    vi.mocked(patchTask).mockClear();
    renderDetail();
    fireEvent.click(screen.getByRole("tab", { name: /Wireframe/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ubah wireframe" }));
    fireEvent.change(screen.getByLabelText("Wireframe"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(screen.queryByTestId("wireframe-editor")).toBeNull();
    expect(screen.getByTestId("task-wireframe")).toBeTruthy();
    expect(patchTask).not.toHaveBeenCalled();
  });

  it("mengubah teks kriteria selesai tanpa mengubah centangnya", async () => {
    vi.mocked(patchTask).mockClear();
    vi.mocked(patchTask).mockResolvedValue(task({ edited: true }));
    renderDetail({
      acceptance: [
        { text: "Satu penilaian per pesan", done: true },
        { text: "Kriteria kedua", done: false },
      ],
      acceptance_total: 2,
      acceptance_done: 1,
    });
    fireEvent.click(screen.getByLabelText("Ubah teks kriteria 1"));
    const input = screen.getByLabelText("Ubah kriteria 1");
    fireEvent.change(input, {
      target: { value: "Satu penilaian per pesan per pengguna" },
    });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() =>
      expect(patchTask).toHaveBeenCalledWith("", "INT-026", {
        acceptance: [
          { text: "Satu penilaian per pesan per pengguna", done: true },
          { text: "Kriteria kedua", done: false },
        ],
      })
    );
  });

  it("menyimpan prasyarat huruf besar dan memuat ulang detail lengkap", async () => {
    vi.mocked(patchTask).mockClear();
    vi.mocked(patchTask).mockResolvedValue(task());
    vi.mocked(fetchTask).mockResolvedValue(
      task({ depends_on: ["INT-005", "INT-007"] })
    );
    const onChanged = vi.fn();
    renderDetail({}, { onChanged });
    const field = screen.getByLabelText("Prasyarat");
    fireEvent.change(field, { target: { value: "int-005, int-007" } });
    fireEvent.blur(field);
    await waitFor(() =>
      expect(patchTask).toHaveBeenCalledWith("", "INT-026", {
        depends_on: ["INT-005", "INT-007"],
      })
    );
    await waitFor(() => expect(fetchTask).toHaveBeenCalledWith("", "INT-026"));
    await waitFor(() =>
      expect(onChanged).toHaveBeenCalledWith(
        expect.objectContaining({ depends_on: ["INT-005", "INT-007"] })
      )
    );
  });

  it("label yang tidak berubah tidak memicu PATCH", () => {
    vi.mocked(patchTask).mockClear();
    renderDetail();
    fireEvent.blur(screen.getByLabelText("Label"));
    expect(patchTask).not.toHaveBeenCalled();
  });

  it("task rencana yang sudah disunting diberi penanda", () => {
    renderDetail({ edited: true });
    expect(screen.getByTestId("task-edited-badge")).toBeTruthy();
    cleanup();
    renderDetail({ edited: false });
    expect(screen.queryByTestId("task-edited-badge")).toBeNull();
  });

  it("member tidak melihat satu pun kontrol sunting isi", () => {
    renderDetail({}, { readOnly: true });
    expect(screen.queryByLabelText("Prasyarat")).toBeNull();
    expect(screen.queryByLabelText("Label")).toBeNull();
    expect(screen.queryByLabelText("Ubah teks kriteria 1")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /Workflow/ }));
    expect(screen.queryByRole("button", { name: "Ubah alur kerja" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /Wireframe/ }));
    expect(screen.queryByRole("button", { name: "Ubah wireframe" })).toBeNull();
  });
});
