import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import ChatView, { type LiveState } from "./ChatView";

vi.mock("@/lib/markdown", () => ({
  default: ({ text, sources }: { text: string; sources?: Array<{ index: number }> }) => (
    <div data-testid="md" data-sources={(sources || []).map((s) => s.index).join(",")}>
      {text}
    </div>
  ),
}));

/* DiagramBlock berat (mermaid + ResizeObserver); untuk test alur ini cukup
   dipastikan kartunya dirender dengan sumber & provenance yang benar. */
vi.mock("./DiagramBlock", () => ({
  default: ({
    source,
    title,
    provenance,
  }: {
    source: string;
    title?: string;
    provenance?: { tool: string } | null;
  }) => (
    <div data-testid="diagram-card-stub" data-provenance={provenance?.tool || ""}>
      {title}:{source}
    </div>
  ),
}));

const EMPTY: LiveState = { answer: "", thinking: "", tools: [] };

function renderChat(over: Partial<Parameters<typeof ChatView>[0]> = {}) {
  const props = {
    messages: [],
    live: EMPTY,
    streaming: false,
    input: "",
    setInput: vi.fn(),
    onSend: vi.fn(),
    accent: "indigo",
    onAccent: vi.fn(),
    ...over,
  };
  return { ...props, ...{ view: render(<ChatView {...props} />) } };
}

afterEach(cleanup);

describe("ChatView — provenance tiap hasil tool", () => {
  it("chip web_search diberi badge Browser dan jumlah hasil", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        tools: [{ name: "web_search", status: "done", source: "browser", hits: 3, ok: true, duration_ms: 412, summary: "3 hasil" }],
      },
    });
    const chip = screen.getByTestId("tool-chip-web_search");
    expect(chip.textContent).toContain("Browser");
    expect(chip.textContent).toContain("3 hasil");
    expect(chip.textContent).toContain("412ms");
  });

  it("diagram diberi badge Tool diagram, bukan Browser", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        tools: [{ name: "create_diagram", status: "done", source: "diagram", ok: true, summary: "OK" }],
      },
    });
    const chip = screen.getByTestId("tool-chip-create_diagram");
    expect(chip.textContent).toContain("Tool diagram");
    expect(chip.textContent).not.toContain("Browser");
  });

  it("browser tanpa hasil → status 0 hasil, bukan bubble kosong", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        tools: [{ name: "web_search", status: "done", source: "browser", hits: 0, ok: true, summary: "tidak ada hasil" }],
      },
    });
    const chip = screen.getByTestId("tool-chip-web_search");
    expect(chip.textContent).toContain("0 hasil");
    expect(chip.textContent).toContain("belum ada data");
    expect(chip.className).toContain("amber");
  });

  it("tool yang gagal ditandai merah", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        tools: [{ name: "fetch_url", status: "failed", source: "browser", ok: false, hits: 0, summary: "timeout" }],
      },
    });
    const chip = screen.getByTestId("tool-chip-fetch_url");
    expect(chip.className).toContain("red");
  });

  it("riwayat assistant_toolcalls juga menampilkan provenance", () => {
    renderChat({
      messages: [
        { role: "assistant_toolcalls", content: "", meta: { tool_calls: [{ name: "create_diagram", id: "c1" }] } },
      ],
    });
    expect(screen.getByText(/Tool diagram/)).toBeTruthy();
  });

  it("hasil tool yang dilipat ke riwayat ikut menampilkan status & durasi", () => {
    renderChat({
      messages: [
        {
          role: "assistant_toolcalls",
          content: "",
          meta: {
            tool_calls: [{ name: "web_search", id: "call_1" }],
            tool_results: [
              { callId: "call_1", name: "web_search", source: "browser", ok: true, hits: 0, duration_ms: 812, summary: "tidak ada hasil" },
            ],
          },
        },
      ],
    });
    const chip = screen.getByTestId("tool-chip-web_search");
    expect(chip.textContent).toContain("Browser");
    expect(chip.textContent).toContain("0 hasil");
    expect(chip.textContent).toContain("812ms");
    expect(chip.className).toContain("amber"); // bukan ✓ hijau
  });

  it("riwayat tetap render saat hasil tool tidak tersedia (tanpa ✓ palsu)", () => {
    renderChat({
      messages: [
        { role: "assistant_toolcalls", content: "", meta: { tool_calls: [{ name: "fetch_url", id: "x" }] } },
      ],
    });
    const chip = screen.getByTestId("tool-chip-fetch_url");
    expect(chip.textContent).toContain("Browser");
    expect(chip.textContent).toContain("✓");
  });
});

describe("ChatView — sitasi", () => {
  const SRC = [
    { index: 1, url: "https://satu.test/a", title: "Sumber Satu", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
    { index: 2, url: "https://dua.test/b", title: "Sumber Dua", tool: "fetch_url", origin: "browser", snippet: "", read: true, cited: false },
  ];

  it("bar sitasi mendaftar tiap sumber dengan tautan + status dikutip", () => {
    renderChat({
      messages: [
        {
          role: "assistant",
          content: "jawaban",
          meta: {
            sources: SRC,
            citations: { status: "cited", total: 2, cited: [1], uncited: [2], invalid: [], detail: "" },
          },
        },
      ],
    });
    const bar = screen.getByTestId("citation-bar");
    expect(bar.textContent).toContain("1/2 klaim bersitasi");
    expect(screen.getByText("Sumber Satu").closest("a")?.getAttribute("href")).toBe("https://satu.test/a");
    expect(bar.textContent).toContain("✓ dikutip");
    expect(bar.textContent).toContain("belum dikutip");
  });

  it("tanpa bukti web: bar menjelaskan browser belum menghasilkan apa pun", () => {
    renderChat({
      messages: [
        {
          role: "assistant",
          content: "jawaban tanpa web",
          meta: {
            sources: [],
            citations: { status: "no-evidence", total: 0, cited: [], uncited: [], invalid: [], detail: "belum ada hasil" },
          },
        },
      ],
    });
    expect(screen.getByTestId("citation-bar").textContent).toContain(
      "belum ada hasil browser"
    );
  });

  it("jawaban tanpa info sitasi tidak menampilkan bar", () => {
    renderChat({ messages: [{ role: "assistant", content: "x", meta: {} }] });
    expect(screen.queryByTestId("citation-bar")).toBeNull();
  });
});

describe("ChatView — kanvas selebar mungkin", () => {
  it("kartu diagram tidak lagi dibatasi kolom teks sempit", () => {
    const { view } = renderChat({
      messages: [{ role: "assistant", content: "```mermaid\nflowchart TD\nA-->B\n```", meta: {} }],
    });
    // kontainer utama memakai max-width lebar (1180px), bukan max-w-3xl (768px)
    const wrap = view.container.querySelector("div[class*='max-w-\\[1180px\\]']");
    expect(wrap).toBeTruthy();
    expect(view.container.innerHTML).not.toContain("max-w-3xl");
  });
});

describe("ChatView — diagram dari tool create_diagram", () => {
  const DIAGRAM = 'flowchart TD\n  a["Mulai"]\n  b["Selesai"]\n  a --> b';

  it("riwayat merender kartu diagram dari meta.diagrams (tanpa fence di jawaban)", () => {
    renderChat({
      messages: [
        {
          role: "assistant",
          content: "Diagramnya sudah saya buat.",
          meta: {
            diagrams: [
              { tool: "create_diagram", kind: "flowchart", title: "Alur", mermaid: DIAGRAM },
            ],
          },
        },
      ],
    });
    const card = screen.getByTestId("diagram-card-stub");
    expect(card.textContent).toContain("Alur");
    expect(card.getAttribute("data-provenance")).toBe("create_diagram");
    expect(screen.getByText("Diagramnya sudah saya buat.")).toBeTruthy();
  });

  it("jawaban yang sudah memuat fence tidak dirender dua kali", () => {
    renderChat({
      messages: [
        {
          role: "assistant",
          content: `Ini diagramnya:\n\n\`\`\`mermaid\n${DIAGRAM}\n\`\`\`\n`,
          meta: {
            diagrams: [{ tool: "create_diagram", title: "Alur", mermaid: DIAGRAM }],
          },
        },
      ],
    });
    expect(screen.queryByTestId("diagram-card-stub")).toBeNull();
  });

  it("run berjalan: diagram dari tool_result muncul sebelum jawaban selesai", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        answer: "Menyusun…",
        tools: [{ name: "create_diagram", status: "done", source: "diagram", ok: true }],
        diagrams: [
          {
            tool: "create_diagram",
            source: "structured",
            kind: "flowchart",
            title: "Alur",
            mermaid: DIAGRAM,
            warnings: [],
          },
        ],
      },
    });
    expect(screen.getByTestId("diagram-card-stub").textContent).toContain('a["Mulai"]');
  });
});

describe("ChatView — sitasi saat streaming", () => {
  const LIVE_SRC = [
    { index: 1, url: "https://satu.test/a", title: "Sumber Satu", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
  ];

  it("marker [n] ditautkan ke sumber yang sudah terdaftar (bukan ditandai liar)", () => {
    renderChat({
      streaming: true,
      live: { ...EMPTY, answer: "Fakta terbaru [1].", sources: LIVE_SRC },
    });
    // Markdown menerima daftar sumber selama streaming — inilah yang membuat
    // chip [1] tidak tampil merah sebagai "nomor di luar daftar".
    expect(screen.getByTestId("md").getAttribute("data-sources")).toBe("1");
  });

  it("bar sitasi live muncul begitu browser mendaftarkan sumber", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        answer: "Fakta terbaru [1].",
        sources: LIVE_SRC,
        citations: { status: "cited", total: 1, cited: [1], uncited: [], invalid: [], detail: "" },
      },
    });
    const bar = screen.getByTestId("citation-bar");
    expect(bar.textContent).toContain("1/1 klaim bersitasi");
    expect(bar.textContent).toContain("Sumber Satu");
  });

  it("tanpa sumber: bar tidak muncul (belum ada yang bisa disitasi)", () => {
    renderChat({ streaming: true, live: { ...EMPTY, answer: "Halo" } });
    expect(screen.queryByTestId("citation-bar")).toBeNull();
  });
});

describe("ChatView — loading screen saat streaming", () => {
  it("menampilkan 'Model sedang berpikir' sebelum token pertama tiba", () => {
    renderChat({ streaming: true, live: EMPTY });
    const ind = screen.getByTestId("thinking-indicator");
    expect(ind.textContent).toContain("Model sedang berpikir");
  });

  it("indikator hilang begitu token (answer) mulai mengalir", () => {
    renderChat({ streaming: true, live: { ...EMPTY, answer: "Halo" } });
    expect(screen.queryByTestId("thinking-indicator")).toBeNull();
  });

  it("indikator tidak muncul saat tool sedang berjalan (chip toolnya yang tampil)", () => {
    renderChat({
      streaming: true,
      live: {
        ...EMPTY,
        tools: [{ name: "web_search", status: "running", source: "browser" }],
      },
    });
    expect(screen.queryByTestId("thinking-indicator")).toBeNull();
    expect(screen.getByTestId("tool-chip-web_search")).toBeTruthy();
  });
});
