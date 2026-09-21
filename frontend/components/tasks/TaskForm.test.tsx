import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import TaskForm from "./TaskForm";

const PHASES = [
  { id: "f0", name: "Fase 0" },
  { id: "f1", name: "Fase 1" },
];

function mockFetch(nextId: string, createdId?: string) {
  const calls: Array<{ url: string; body?: unknown }> = [];
  const stub = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({
      url,
      body: init?.body ? JSON.parse(init.body as string) : undefined,
    });
    if (url.includes("/api/tasks/next-id")) {
      return {
        ok: true,
        json: async () => ({ next_id: nextId, track: "platform" }),
      } as Response;
    }
    return {
      ok: true,
      json: async () => ({
        task: {
          id: createdId || nextId,
          title: "Coba",
          branch_name: `feat/${createdId || nextId}-coba`,
        },
      }),
    } as Response;
  });
  vi.stubGlobal("fetch", stub);
  return { stub, calls };
}

function setup(track = "platform") {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  const onError = vi.fn();
  render(
    <TaskForm
      token=""
      track={track}
      phases={PHASES}
      defaultPhase="f0"
      suggestions={{ assignees: ["dev"], labels: [] }}
      onClose={onClose}
      onCreated={onCreated}
      onError={onError}
    />
  );
  return { onClose, onCreated, onError };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TaskForm — ID otomatis", () => {
  it("menampilkan nomor tergenerate + pratinjau branch memakainya", async () => {
    mockFetch("ASK-055");
    setup();
    await waitFor(() =>
      expect(screen.getByText("ASK-055")).toBeTruthy()
    );
    expect(
      screen.getByLabelText("Task ID otomatis").textContent
    ).toContain("tergenerate otomatis");
    fireEvent.change(screen.getByLabelText("Judul task baru"), {
      target: { value: "Tambah grafik" },
    });
    expect(screen.getByText(/branch:/).textContent).toContain(
      "feat/ASK-055-tambah-grafik"
    );
  });

  it("papan internship memakai prefix INT", async () => {
    mockFetch("INT-037");
    setup("internship");
    await waitFor(() =>
      expect(screen.getByText("INT-037")).toBeTruthy()
    );
    expect(screen.getByText(/branch:/).textContent).toContain("INT-037");
  });

  it("menyimpan tanpa task_id (backend yang mengisi) + membawa track", async () => {
    const { calls } = mockFetch("ASK-055");
    const { onCreated } = setup("internship");
    await waitFor(() =>
      expect(screen.getByText("ASK-055")).toBeTruthy()
    );
    fireEvent.change(screen.getByLabelText("Judul task baru"), {
      target: { value: "Coba" },
    });
    fireEvent.click(screen.getByText("Buat task"));
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    const post = calls.find((c) => c.url === "/api/tasks");
    expect(post).toBeTruthy();
    const body = post!.body as Record<string, unknown>;
    expect(body.track).toBe("internship");
    expect(body.task_id ?? "").toBe("");
    expect(onCreated.mock.calls[0][0].id).toBe("ASK-055");
  });

  it("tetap bisa disimpan bila pratinjau nomor gagal dimuat", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).includes("/api/tasks/next-id")) {
          return { ok: false, status: 500 } as Response;
        }
        return {
          ok: true,
          json: async () => ({ task: { id: "ASK-099", title: "Coba" } }),
        } as Response;
      })
    );
    const { onCreated } = setup();
    await waitFor(() => expect(screen.getByText("otomatis")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Judul task baru"), {
      target: { value: "Coba" },
    });
    fireEvent.click(screen.getByText("Buat task"));
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
  });
});
