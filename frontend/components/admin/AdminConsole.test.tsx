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
    rag: {
      chunk_size: 1200,
      chunk_overlap: 150,
      top_k: 4,
      max_upload_mb: 25,
      ocr_enabled: true,
      ocr_engine: "auto",
      ocr_min_chars: 80,
      ocr_dpi: 200,
      ocr_max_pages: 40,
      ocr_deskew: true,
      retrieval_mode: "hybrid",
      retrieval_candidates: 50,
      mmr_lambda: 0.7,
      min_score: 0,
      context_neighbors: 0,
    },
    feedback: { enabled: true, auto_guidance: true, max_guidance: 8 },
    interpreter: { always_on: true, record_logprobs: true, record_tool_payloads: true },
    artifacts: { max_artifacts: 500, retention_days: 30 },
    quota: {
      enabled: true,
      daily_tokens: 100000,
      weekly_tokens: 500000,
      daily_requests: 300,
      block_on_exceed: true,
    },
    instructions: { enabled: true, max_active: 3, max_chars: 4000 },
  },
  provider: "mock",
  model: "mock-agent (offline demo)",
  admin_protected: false,
}));

/** Dashboard kuota minimal — konsol harus tetap render walau kosong. */
const QUOTA = vi.hoisted(() => ({
  overview: {
    policy: {
      enabled: true,
      daily_tokens: 100000,
      weekly_tokens: 500000,
      daily_requests: 300,
      block_on_exceed: true,
    },
    users: 2,
    overrides: 1,
    totals: {
      runs: 5,
      tokens: 1234,
      prompt_tokens: 1000,
      completion_tokens: 234,
    },
    today: { runs: 2, tokens: 500, day_key: "2026-03-05" },
    this_week: { runs: 5, tokens: 1234, week_key: "2026-W10" },
    by_provider: [{ provider: "mock", runs: 5, tokens: 1234 }],
    by_mode: [{ mode: "text", runs: 5, tokens: 1234 }],
    blocked_today: 1,
  },
  users: [
    {
      user_key: "user-1",
      first_seen: 1,
      last_seen: 2,
      day_tokens: 500,
      day_requests: 2,
      week_tokens: 1234,
      week_requests: 5,
      total_tokens: 1234,
      total_requests: 5,
      limits: {
        daily_tokens: 100000,
        weekly_tokens: 500000,
        daily_requests: 300,
        source: "policy",
      },
      remaining: { day_tokens: 99500, week_tokens: 498766 },
      over_limit: false,
    },
  ],
  rejections: [
    {
      id: "rj1",
      user_key: "user-9",
      mode: "text",
      reason: "Kuota token harian sudah habis",
      day_key: "2026-03-05",
      ts: 3,
    },
  ],
}));

const INSTRUCTIONS = vi.hoisted(() => ({
  playbooks: [
    {
      id: "pb1",
      name: "Analis Hukum",
      domain: "hukum",
      persona: "analis hukum",
      method: "",
      theory: "irac",
      rules: "",
      output_format: "",
      triggers: ["pasal"],
      modes: [],
      activation: "keywords",
      priority: 200,
      enabled: true,
      created_at: 1,
      updated_at: 1,
    },
  ],
  stats: {
    total: 1,
    enabled: 1,
    by_activation: { always: 0, keywords: 1, manual: 0 },
    activations_total: 4,
    top_used: [
      { playbook_id: "pb1", playbook_name: "Analis Hukum", runs: 4, last_used: 9 },
    ],
    never_used: [],
  },
  theories: [
    {
      key: "irac",
      label: "IRAC (analisis hukum)",
      domain_hint: "hukum",
      method: "1. ISU …",
    },
  ],
  activations: [
    {
      id: "ac1",
      playbook_id: "pb1",
      playbook_name: "Analis Hukum",
      conversation_id: "c1",
      run_id: "r1",
      mode: "text",
      match_reason: "pemicu: pasal",
      ts: 9,
    },
  ],
  policy: { enabled: true, max_active: 3, max_chars: 4000 },
}));

const OCR = vi.hoisted(() => ({
  deps: {
    available: true,
    engines: ["rapidocr"],
    pdf_render: true,
    pillow: true,
    install_hint: null,
  },
  engine_selected: "rapidocr",
  policy: { ocr_enabled: true },
  accepts: [".pdf", ".png"],
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
  adminQuota: vi.fn(),
  adminInstructions: vi.fn(),
  ocrStatus: vi.fn(),
  adminSetQuotaLimit: vi.fn(),
  adminClearQuotaLimit: vi.fn(),
  adminResetQuota: vi.fn(),
  adminCreatePlaybook: vi.fn(),
  adminUpdatePlaybook: vi.fn(),
  adminDeletePlaybook: vi.fn(),
  adminPreviewPlaybooks: vi.fn(),
  readAdminToken: vi.fn(() => ""),
}));



import AdminConsole from "./AdminConsole";
import {
  adminArtifacts,
  adminFeedback,
  adminInstructions,
  adminMemories,
  adminOverview,
  adminQuota,
  adminUpdatePolicy,
  ocrStatus,
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
  vi.mocked(adminQuota).mockResolvedValue(QUOTA as never);
  vi.mocked(adminInstructions).mockResolvedValue(INSTRUCTIONS as never);
  vi.mocked(ocrStatus).mockResolvedValue(OCR as never);
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

  it("Ringkasan memuat status tiap pipeline baru (kuota, instruksi, OCR)", async () => {
    render(<AdminConsole />);
    expect(await screen.findByText("Status tiap pipeline")).toBeTruthy();
    // kuota: token hari ini + jumlah yang ditolak
    expect(screen.getByText(/2 end user · 1 ditolak/)).toBeTruthy();
    // instruksi: playbook aktif & berapa kali dipakai
    expect(screen.getByText(/4 kali dipakai/)).toBeTruthy();
    // OCR siap + mesin yang dipilih
    expect(screen.getByText(/mesin: rapidocr/)).toBeTruthy();
  });

  it("tab Kuota token menampilkan pemakaian per end user dan penolakan", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Kuota token" }));
    expect(await screen.findByText("End user & pemakaiannya")).toBeTruthy();
    expect(screen.getByText("user-1")).toBeTruthy();
    // penolakan terlihat — bukti batas benar-benar ditegakkan
    expect(screen.getByText("user-9")).toBeTruthy();
    expect(
      screen.getByText(/Kuota token harian sudah habis/)
    ).toBeTruthy();
  });

  it("tab Instruksi menampilkan playbook + teori dan katalog teori terisi", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Instruksi" }));
    expect(await screen.findByText("Playbook terdaftar")).toBeTruthy();
    // muncul di daftar playbook DAN di riwayat aktivasi
    expect(screen.getAllByText("Analis Hukum").length).toBeGreaterThan(0);
    // label teori dari katalog ikut ditampilkan sebagai badge
    expect(screen.getAllByText(/IRAC/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/pemicu: pasal/).length).toBeGreaterThan(0);
    // uji pemicu tersedia tanpa memanggil model
    expect(screen.getByText("Uji pemicu")).toBeTruthy();
  });

  it("tab Pipeline memuat kontrol OCR dan strategi retrieval", async () => {
    render(<AdminConsole />);
    fireEvent.click(screen.getByRole("button", { name: "Pipeline" }));
    await waitFor(() => screen.getByText("Kecerdasan retrieval"));
    expect(
      screen.getByText("OCR — dokumen hasil scan & gambar")
    ).toBeTruthy();
    const ocrSwitch = screen.getByRole("switch", { name: /Aktifkan OCR/ });
    expect(ocrSwitch.getAttribute("aria-checked")).toBe("true");

    fireEvent.click(ocrSwitch);
    await waitFor(() => expect(adminUpdatePolicy).toHaveBeenCalled());
    expect(adminUpdatePolicy).toHaveBeenCalledWith("", {
      rag: { ocr_enabled: false },
    });
  });
});
