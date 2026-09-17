import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AdminOverview } from "@/lib/types";

/* Mock seluruh lapisan API — konsol diuji sebagai UI murni.
   `vi.hoisted` menaikkan OVERVIEW ke atas hoist vi.mock (factory dipanggil
   sebelum deklarasi const biasa dieksekusi). */
const OVERVIEW = vi.hoisted(() => ({
  counts: {
    conversations: 3,
    messages: 12,
    trace_events: 240,
    memories: 1,
    artifacts: 1,
    artifact_bytes: 42000,
    feedback_total: 1,
    feedback_up: 0,
    feedback_down: 1,
    rag_documents: 1,
    rag_documents_ready: 1,
  },
  feedback: { total: 1, up: 0, down: 1, ratio_up: 0, by_status: { new: 1 } },
  policy: {
    modes: { text: true, image: true, diagram: true, ppt: true, rag: false, research: true },
    tools: { web_search: true, fetch_url: true, create_diagram: true, calculator: true, generate_image: false, generate_ppt: true, save_memory: true },
    memory: { enabled: true, allow_ai_write: true },
    rag: { chunk_size: 1200, chunk_overlap: 150, top_k: 4, max_upload_mb: 25 },
    feedback: { enabled: true, auto_guidance: true, max_guidance: 8 },
    interpreter: { always_on: true, record_logprobs: true, record_tool_payloads: true },
    artifacts: { max_artifacts: 500, retention_days: 30 },
  },
  provider: "mock",
  model: "mock-agent (offline demo)",
  admin_protected: false,
}));

vi.mock("@/lib/api", () => ({
  adminOverview: vi.fn(),
  adminMemories: vi.fn(),
  adminArtifacts: vi.fn(),
  adminFeedback: vi.fn(),
  adminCreateMemory: vi.fn(),
  adminUpdateMemory: vi.fn(),
  adminDeleteMemory: vi.fn(),
  adminDeleteArtifact: vi.fn(),
  adminSetFeedbackStatus: vi.fn(),
  adminApplyFeedback: vi.fn(),
  adminDeleteFeedback: vi.fn(),
  adminUpdatePolicy: vi.fn(),
}));



import AdminConsole from "./AdminConsole";
import {
  adminArtifacts,
  adminFeedback,
  adminMemories,
  adminOverview,
  adminUpdatePolicy,
} from "@/lib/api";

afterEach(cleanup);

const MEMORY_FIXTURE = [
  {
    id: "mm1",
    scope: "global",
    key: "tone",
    content: "Jawab ringkas",
    source: "admin",
    enabled: true,
    created_at: 1,
    updated_at: 1,
  },
];

const ARTIFACT_FIXTURE = [
  {
    id: "a1",
    conversation_id: "c1",
    run_id: "r1",
    kind: "pptx",
    title: "Deck onboarding",
    filename: "deck.pptx",
    mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    size_bytes: 42000,
    meta: { generator: "pptx" },
    created_at: 1,
    url: "/api/artifacts/a1/download",
  },
];

const FEEDBACK_FIXTURE = {
  feedback: [
    {
      id: "fb1",
      conversation_id: "c1",
      message_id: "m1",
      rating: "down",
      comment: "Terlalu panjang",
      context: { mode: "text", answer_snippet: "bla" },
      status: "new",
      guidance_memory_id: "",
      created_at: 1,
    },
  ],
  stats: { total: 1, up: 0, down: 1, ratio_up: 0 },
};

beforeEach(() => {
  // restoreMocks:true di vitest.config menghapus stub dari factory —
  // implementasi dipasang di sini agar aktif untuk setiap tes.
  vi.mocked(adminOverview).mockResolvedValue(OVERVIEW as never);
  vi.mocked(adminMemories).mockResolvedValue(MEMORY_FIXTURE as never);
  vi.mocked(adminArtifacts).mockResolvedValue(ARTIFACT_FIXTURE as never);
  vi.mocked(adminFeedback).mockResolvedValue(FEEDBACK_FIXTURE as never);
  vi.mocked(adminUpdatePolicy).mockResolvedValue(OVERVIEW.policy as never);
});

describe("AdminConsole — halaman admin pipeline", () => {
  it("tab Ringkasan menampilkan statistik & checklist publish", async () => {
    render(<AdminConsole />);
    expect(await screen.findByText("240")).toBeTruthy(); // event interpreter
    expect(screen.getByText(/Checklist cepat/)).toBeTruthy();
    expect(screen.getByText(/Dokumen RAG siap/)).toBeTruthy();
  });

  it("tab Pipeline menampilkan mode & tool dari policy, toggle memanggil update", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Pipeline" }));
    await waitFor(() => screen.getByText("Mode pipeline"));
    // mode RAG dimatikan di policy → tampil dinonaktifkan
    const ragSwitch = screen.getByRole("switch", { name: /RAG \(rag\)/ });
    expect(ragSwitch.getAttribute("aria-checked")).toBe("false");
    // interpreter terkunci selalu-on
    const lockSwitch = screen.getByRole("switch", {
      name: /Selalu merecord semua langkah/,
    });
    expect(lockSwitch.getAttribute("aria-checked")).toBe("true");

    // nyalakan RAG → PUT /api/admin/policy
    fireEvent.click(ragSwitch);
    await waitFor(() => expect(adminUpdatePolicy).toHaveBeenCalled());
    expect(adminUpdatePolicy).toHaveBeenCalledWith("", {
      modes: { rag: true },
    });
  });

  it("tab Memori & Feedback menampilkan data + aksi jadikan pedoman", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Memori" }));
    expect(await screen.findByText("Jawab ringkas")).toBeTruthy();

    fireEvent.click(screen.getByText("Feedback"));
    expect(await screen.findByText(/“Terlalu panjang”/)).toBeTruthy();
    expect(screen.getByText("✓ Jadikan pedoman")).toBeTruthy();
  });

  it("tab Artifact menampilkan deck PPT dengan tautan unduh", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Artifact" }));
    expect(await screen.findByText("Deck onboarding")).toBeTruthy();
    expect(screen.getByText("Buka ↗")).toBeTruthy();
  });
});
