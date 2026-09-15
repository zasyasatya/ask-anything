/* Alur streaming → status live.
   Fixture di bawah adalah bentuk event nyata dari `POST /api/chat` (mock
   provider + fake search server), dipangkas. Yang dijaga:
   - sumber bernomor tersedia **selama** run (marker [n] tidak ditandai liar);
   - diagram tool masuk ke status live dari payload tool_result/agent_done,
     bukan dari fence ```mermaid di teks jawaban. */
import { describe, expect, it } from "vitest";
import { EMPTY_LIVE, reduceLive, reduceLiveAll } from "./live";

const SEARCH_EVENTS = [
  { type: "start", conversation_id: "c1" },
  { type: "thinking", text: "Perlu browsing dulu." },
  {
    type: "tool_call",
    id: "call_mock_1",
    name: "web_search",
    source: "browser",
    arguments: { query: "berita teknologi terkini" },
  },
  {
    type: "tool_result",
    id: "call_mock_1",
    name: "web_search",
    source: "browser",
    ok: true,
    hits: 3,
    duration_ms: 412,
    summary: "web_search 'berita teknologi terkini': 3 hasil",
    data: {
      query: "berita teknologi terkini",
      results: [
        { title: "Apa itu agent loop", url: "http://127.0.0.1:8099/page/agent-loop", snippet: "…" },
        { title: "Mekanisme sitasi", url: "http://127.0.0.1:8099/page/mekanisme-sitasi", snippet: "…" },
      ],
    },
  },
  {
    type: "sources",
    total: 2,
    items: [
      { index: 1, url: "http://127.0.0.1:8099/page/agent-loop", title: "Apa itu agent loop", tool: "web_search", origin: "browser", snippet: "", read: false, cited: false },
      { index: 2, url: "http://127.0.0.1:8099/page/mekanisme-sitasi", title: "Mekanisme sitasi", tool: "web_search", origin: "browser", snippet: "", read: false, cited: false },
    ],
  },
  { type: "delta", text: "Hasil browsing berasal dari sumber bernomor [1]." },
  {
    type: "citations",
    status: "cited",
    total: 2,
    cited: [1],
    uncited: [2],
    invalid: [],
    detail: "1/2 sumber dikutip inline.",
    sources: [
      { index: 1, url: "http://127.0.0.1:8099/page/agent-loop", title: "Apa itu agent loop", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
      { index: 2, url: "http://127.0.0.1:8099/page/mekanisme-sitasi", title: "Mekanisme sitasi", tool: "web_search", origin: "browser", snippet: "", read: false, cited: false },
    ],
  },
  {
    type: "agent_done",
    answer: "Hasil browsing berasal dari sumber bernomor [1].",
    sources: [
      { index: 1, url: "http://127.0.0.1:8099/page/agent-loop", title: "Apa itu agent loop", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
    ],
    citations: { status: "cited", total: 1, cited: [1], uncited: [], invalid: [], detail: "" },
    diagrams: [],
  },
];

const MERMAID = 'flowchart TD\n  q["Pertanyaan user"]\n  a["Jawaban + visual"]\n  q --> a';

const DIAGRAM_EVENTS = [
  { type: "start", conversation_id: "c2" },
  {
    type: "tool_call",
    id: "call_mock_2",
    name: "create_diagram",
    source: "diagram",
    arguments: { kind: "flowchart", title: "Alur Kerja Agent" },
  },
  {
    type: "tool_result",
    id: "call_mock_2",
    name: "create_diagram",
    source: "diagram",
    ok: true,
    hits: null,
    duration_ms: 3,
    summary: "create_diagram flowchart 'Alur Kerja Agent' OK (2 node, 1 edge)",
    data: {
      kind: "flowchart",
      title: "Alur Kerja Agent",
      mermaid: MERMAID,
      source: "structured",
      warnings: [],
    },
  },
  // Model menjawab TANPA menyalin fence mermaid.
  { type: "delta", text: "Diagramnya sudah saya buatkan di kartu di bawah." },
  {
    type: "agent_done",
    answer: "Diagramnya sudah saya buatkan di kartu di bawah.",
    sources: [],
    citations: { status: "no-evidence", total: 0, cited: [], uncited: [], invalid: [], detail: "" },
    diagrams: [
      { tool: "create_diagram", kind: "flowchart", title: "Alur Kerja Agent", mermaid: MERMAID, source: "structured", warnings: [] },
    ],
  },
];

describe("reduceLive — jalur browser & sitasi", () => {
  const state = reduceLiveAll(SEARCH_EVENTS);

  it("chip tool menampilkan hasil, durasi, dan provenance browser", () => {
    expect(state.tools).toHaveLength(1);
    expect(state.tools[0]).toMatchObject({
      name: "web_search",
      status: "done",
      source: "browser",
      hits: 3,
      ok: true,
    });
  });

  it("sumber bernomor sudah ada SEBELUM jawaban selesai (marker [1] bisa ditautkan)", () => {
    const afterSources = reduceLiveAll(SEARCH_EVENTS.slice(0, 5));
    expect(afterSources.sources?.map((s) => s.index)).toEqual([1, 2]);
    expect(afterSources.citations).toBeNull();       // belum ada laporan final
    expect(afterSources.answer).toBe("");            // delta belum masuk
  });

  it("laporan sitasi final menggantikan daftar sumber sementara", () => {
    // agent_done adalah snapshot terakhir → laporan diambil dari sana
    expect(state.citations).toMatchObject({ status: "cited", cited: [1], total: 1 });
    expect(state.sources?.[0].cited).toBe(true);
  });

  it("event tak dikenal diabaikan tanpa mengubah status", () => {
    expect(reduceLive(state, { type: "prompt", system: "…" })).toBe(state);
  });

  it("error di tengah stream tetap terlihat (tidak hilang saat riwayat dimuat ulang)", () => {
    const failed = reduceLiveAll([
      { type: "delta", text: "Sebagian jawaban." },
      { type: "error", message: "HTTP 500 dari gateway" },
    ]);
    // page.tsx memakai status ini saat run gagal & tidak ada pesan assistant
    // yang tersimpan — tanpa itu jawaban/kesalahan menghilang dari layar.
    expect(failed.answer).toContain("Sebagian jawaban.");
    expect(failed.answer).toContain("HTTP 500 dari gateway");
  });
});

describe("reduceLive — diagram dari tool", () => {
  it("diagram masuk dari payload tool_result, bukan dari teks jawaban", () => {
    const state = reduceLiveAll(DIAGRAM_EVENTS);
    expect(state.diagrams).toHaveLength(1);
    expect(state.diagrams?.[0]).toMatchObject({
      tool: "create_diagram",
      title: "Alur Kerja Agent",
      mermaid: MERMAID,
    });
    expect(state.answer).not.toContain("```mermaid");
  });

  it("diagram tidak dobel walau muncul di tool_result dan agent_done", () => {
    const doubled = reduceLiveAll([
      ...DIAGRAM_EVENTS,
      {
        type: "agent_done",
        diagrams: [{ tool: "create_diagram", title: "Alur Kerja Agent", mermaid: MERMAID }],
      },
    ]);
    expect(doubled.diagrams).toHaveLength(1);
  });

  it("tool_result tanpa data diagram tidak menambah kartu", () => {
    const state = reduceLiveAll([
      { type: "tool_call", id: "x", name: "web_search", source: "browser" },
      { type: "tool_result", id: "x", name: "web_search", ok: true, hits: 0,
        data: { results: [] } },
    ]);
    expect(state.diagrams).toEqual([]);
  });

  it("EMPTY_LIVE tidak dipakai bersama antar run (immutability)", () => {
    const a = reduceLive(EMPTY_LIVE, { type: "delta", text: "x" });
    expect(EMPTY_LIVE.answer).toBe("");
    expect(a.answer).toBe("x");
  });
});
