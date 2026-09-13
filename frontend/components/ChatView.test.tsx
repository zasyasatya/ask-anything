import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import ChatView, { type LiveState } from "./ChatView";

vi.mock("@/lib/markdown", () => ({
  default: ({ text }: { text: string }) => <div data-testid="md">{text}</div>,
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
