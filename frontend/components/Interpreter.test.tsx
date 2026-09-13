import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Interpreter from "./Interpreter";
import type { TraceEvent } from "@/lib/types";

/** Trace yang mereplikasi apa yang dipancarkan run_agent() untuk satu run:
    browser 0 hasil + diagram tool + sitasi kosong. */
const TRACE: TraceEvent[] = [
  { type: "meta", t_ms: 0, step: 0, provider: "mock", model: "mock-agent", temperature: 0.7, max_steps: 6, max_tokens: 2048, logprobs: true, tools: ["web_search"] },
  { type: "prompt", t_ms: 1, step: 0, system: "You are **Ask Anything**…", message_count: 1, tools: [{ function: { name: "web_search" } }] },
  { type: "llm_request", t_ms: 2, step: 1, message_count: 1, tools: ["web_search"], sampling: { temperature: 0.7, max_tokens: 2048, logprobs: true } },
  { type: "thinking", t_ms: 3, step: 1, text: "perlu browsing" },
  { type: "llm_response", t_ms: 5, step: 1, text: "", chars: 0, finish_reason: "tool_calls", duration_ms: 3, tool_calls: [{ id: "c1", name: "web_search", arguments: { query: "berita" } }] },
  { type: "tool_call", t_ms: 6, step: 1, id: "c1", name: "web_search", source: "browser", arguments: { query: "berita" }, args_preview: '{"query":"berita"}' },
  { type: "tool_result", t_ms: 7, step: 1, id: "c1", name: "web_search", source: "browser", ok: true, hits: 0, new_sources: 0, summary: "web_search: tidak ada hasil", duration_ms: 1.5, data: { results: [] } },
  { type: "note", t_ms: 8, step: 1, status: "no-results", message: "Browser: 0 hasil dari web_search" },
  { type: "sources", t_ms: 9, step: 1, total: 0, items: [] },
  { type: "llm_request", t_ms: 10, step: 2, message_count: 4, tools: ["web_search"], sampling: { temperature: 0.7, max_tokens: 2048, logprobs: true } },
  { type: "delta", t_ms: 11, step: 2, text: "Jawaban " },
  { type: "delta", t_ms: 12, step: 2, text: "agent" },
  { type: "logprobs", t_ms: 12, step: 2, items: [{ token: "Jawaban", logprob: -0.02, top: [{ token: "Jawaban", logprob: -0.02 }] }] },
  { type: "llm_response", t_ms: 13, step: 2, text: "Jawaban agent", chars: 14, finish_reason: "stop", duration_ms: 3, tool_calls: [] },
  { type: "usage", t_ms: 14, step: 2, prompt_tokens: 120, completion_tokens: 2, total_tokens: 122 },
  { type: "citations", t_ms: 15, step: 2, status: "no-evidence", total: 0, cited: [], uncited: [], invalid: [], detail: "belum ada hasil browser", sources: [] },
  { type: "done", t_ms: 16, step: 2, answer: "Jawaban agent", steps: 2, stopped_reason: "stop", latency_ms: 200 },
];

const withBrowserHits = (over: TraceEvent[]): TraceEvent[] => [
  ...TRACE.slice(0, 6),
  over[0],
  ...TRACE.slice(7),
];

function renderInt(trace: TraceEvent[] = TRACE) {
  return render(<Interpreter trace={trace} streaming={false} onClose={vi.fn()} />);
}

afterEach(cleanup);

describe("Interpreter — tab Log adalah default dan berbentuk baris", () => {
  it("langsung menampilkan baris log (bukan paragraf) untuk tiap langkah", async () => {
    renderInt();
    await waitFor(() => expect(screen.getByTestId("interp-log")).toBeTruthy());
    const rows = screen.getAllByTestId(/^log-row-/);
    expect(rows.length).toBeGreaterThan(8);
    expect(screen.getByTestId("log-row-start").textContent).toContain("mock-agent");
    expect(screen.getByTestId("log-row-tool.exec").textContent).toContain("web_search");
  });

  it("baris tool menampilkan provenance Browser + durasi", () => {
    renderInt();
    const row = screen.getByTestId("log-row-tool.result");
    expect(row.textContent).toContain("Browser");
    expect(row.textContent).toContain("0 hasil");
    expect(row.textContent).toContain("2ms"); // 1.5ms dibulatkan fmtDur
  });

  it("payload mentah bisa dibuka dari baris log", () => {
    renderInt();
    fireEvent.click(screen.getByTestId("log-row-tool.exec"));
    expect(screen.getByText(/arguments/)).toBeTruthy();
  });

  it("header strip menampilkan hitungan, bukan kalimat", () => {
    renderInt();
    const panel = screen.getByTestId("interpreter");
    expect(panel.textContent).toContain("ev ");
    expect(panel.textContent).toContain("tool ");
    expect(panel.textContent).toContain("browser");
  });
});

describe("Interpreter — tab LLM membuka blackbox", () => {
  it("menampilkan request & respons mentah per step", async () => {
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /^LLM/ }));
    await waitFor(() => expect(screen.getByTestId("interp-llm")).toBeTruthy());
    const text = screen.getByTestId("interp-llm").textContent || "";
    expect(text).toContain("request messages");
    expect(text).toContain("raw completion");
    expect(text).toContain("chain-of-thought");
    expect(text).toContain("tool_calls yang diminta model");
    expect(text).toContain("system prompt");
  });

  it("token logprobs dirender sebagai chips bila provider mengirimnya", () => {
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /^LLM/ }));
    expect(screen.getByTestId("interp-llm").textContent).toContain("token logprobs");
  });
});

describe("Interpreter — tab Tools & Sumber", () => {
  it("tab Tools memperlihatkan argumen, hasil mentah, status, durasi", async () => {
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /^Tools/ }));
    await waitFor(() => expect(screen.getByTestId("interp-tools")).toBeTruthy());
    const txt = screen.getByTestId("interp-tools").textContent || "";
    expect(txt).toContain("web_search");
    expect(txt).toContain("arguments (dari model)");
    expect(txt).toContain("result payload (mentah)");
    expect(txt).toContain("0 hasil");
    expect(txt).toContain("belum ada hasil dari browser");
    expect(txt).toContain("Browser: 0 hasil dari web_search");
  });

  it("tab Sumber menjelaskan 0 sumber tanpa mengarang", async () => {
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /Sumber/ }));
    await waitFor(() => expect(screen.getByTestId("interp-sources")).toBeTruthy());
    expect(screen.getByTestId("interp-sources").textContent).toContain(
      "0 sumber — browser sudah dipanggil tapi tidak menghasilkan hasil"
    );
  });

  it("sumber browser yang ada ditampilkan sebagai baris tabel + status dikutip", async () => {
    const withHits = withBrowserHits([
      {
        type: "tool_result", t_ms: 7, step: 1, id: "c1", name: "web_search",
        source: "browser", ok: true, hits: 2, new_sources: 2,
        summary: "web_search 'berita': 2 hasil", duration_ms: 12,
        data: { results: [{ title: "A", url: "https://a.test" }] },
      },
    ]);
    const trace = withHits.map((e) =>
      e.type === "citations"
        ? { ...e, status: "cited", total: 2, cited: [1, 2], detail: "2/2 dikutip",
            sources: [
              { index: 1, url: "https://a.test", title: "A", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
              { index: 2, url: "https://b.test", title: "B", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true },
            ] }
        : e.type === "sources"
          ? { ...e, total: 2, items: [{ index: 1, url: "https://a.test", title: "A", tool: "web_search", origin: "browser", snippet: "", read: false, cited: true }] }
          : e
    );
    renderInt(trace as TraceEvent[]);
    fireEvent.click(screen.getByRole("button", { name: /Sumber/ }));
    await waitFor(() => expect(screen.getByTestId("interp-sources")).toBeTruthy());
    const txt = screen.getByTestId("interp-sources").textContent || "";
    expect(txt).toContain("https://a.test");
    expect(txt).toContain("✓ dikutip");
    expect(txt).toContain("status verifikasi");
    expect(txt).toContain("cited");
  });
});

describe("Interpreter — Metrik & kontrol panel", () => {
  it("tab Metrik berisi angka mentah run", async () => {
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /Metrik/ }));
    await waitFor(() => expect(screen.getByTestId("interp-metrics")).toBeTruthy());
    const txt = screen.getByTestId("interp-metrics").textContent || "";
    expect(txt).toContain("mock-agent");
    expect(txt).toContain("122");
    expect(txt).toContain("200 ms");
    expect(txt).toContain("stopped_reason");
  });

  it("tombol copy log menyalin teks log apa adanya", async () => {
    const write = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: write }, configurable: true });
    renderInt();
    fireEvent.click(screen.getByRole("button", { name: /copy log/ }));
    await waitFor(() => expect(write).toHaveBeenCalled());
    expect(String((write.mock.calls as unknown as string[][])[0][0])).toContain("tool.exec");
  });

  it("panel punya grip untuk dilebarkan dan punya lebar awal", () => {
    const { container } = renderInt();
    const aside = container.querySelector("aside") as HTMLElement;
    expect(parseInt(aside.style.width, 10)).toBeGreaterThan(300);
    expect(screen.getByTestId("interp-resizer")).toBeTruthy();
  });

  it("run kosong tidak crash dan memberi instruksi singkat", () => {
    renderInt([]);
    expect(screen.getByTestId("interp-log").textContent).toContain("Belum ada event");
  });
});
