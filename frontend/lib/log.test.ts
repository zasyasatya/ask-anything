import { describe, expect, it } from "vitest";
import { buildLog, fmtDur, fmtT, logToText } from "./log";
import type { TraceEvent } from "./types";

/** Trace sintetis — bentuknya sama persis dengan yang dipancarkan run_agent(). */
const TRACE: TraceEvent[] = [
  { type: "meta", t_ms: 0, step: 0, provider: "mock", model: "mock-agent", temperature: 0.7, max_steps: 6, max_tokens: 2048, logprobs: true },
  { type: "prompt", t_ms: 1, step: 0, message_count: 2, tools: [{ function: { name: "web_search" } }] },
  { type: "llm_request", t_ms: 2, step: 1, message_count: 2, tools: ["web_search"], sampling: { temperature: 0.7, max_tokens: 2048, logprobs: true } },
  { type: "thinking", t_ms: 3, step: 1, text: "butuh " },
  { type: "thinking", t_ms: 4, step: 1, text: "data segar" },
  { type: "llm_response", t_ms: 6, step: 1, text: "", chars: 0, finish_reason: "tool_calls", duration_ms: 4, tool_calls: [{ id: "c1", name: "web_search", arguments: { query: "berita" } }] },
  { type: "tool_call", t_ms: 7, step: 1, id: "c1", name: "web_search", arguments: { query: "berita" }, source: "browser", args_preview: '{"query":"berita"}' },
  { type: "tool_result", t_ms: 9, step: 1, id: "c1", name: "web_search", source: "browser", ok: true, hits: 0, summary: "web_search: tidak ada hasil", duration_ms: 2, new_sources: 0, data: { results: [] } },
  { type: "note", t_ms: 10, step: 1, status: "no-results", message: "Browser: 0 hasil" },
  { type: "sources", t_ms: 11, step: 1, total: 0, items: [] },
  { type: "llm_request", t_ms: 12, step: 2, message_count: 4, tools: ["web_search"], sampling: { temperature: 0.7, max_tokens: 2048, logprobs: true } },
  { type: "delta", t_ms: 13, step: 2, text: "Halo " },
  { type: "delta", t_ms: 14, step: 2, text: "dunia" },
  { type: "logprobs", t_ms: 15, step: 2, items: [{ token: "Halo", logprob: -0.1, top: [] }] },
  { type: "llm_response", t_ms: 16, step: 2, text: "Halo dunia", chars: 11, finish_reason: "stop", duration_ms: 4, tool_calls: [] },
  { type: "usage", t_ms: 17, step: 2, prompt_tokens: 120, completion_tokens: 2, total_tokens: 122 },
  { type: "citations", t_ms: 18, step: 2, status: "no-evidence", total: 0, cited: [], uncited: [], invalid: [], detail: "tidak ada bukti web" },
  { type: "done", t_ms: 19, step: 2, answer: "Halo dunia", steps: 2, stopped_reason: "stop", latency_ms: 20 },
];

describe("buildLog — log eksekusi, bukan narasi", () => {
  const lines = buildLog(TRACE);
  const byAction = (a: string) => lines.filter((l) => l.action === a);

  it("satu baris per langkah penting; delta & logprobs tidak membanjiri log", () => {
    const actions = lines.map((l) => l.action);
    expect(actions).toEqual(
      expect.arrayContaining([
        "start", "prompt.assemble", "request #1", "thinking", "response #1",
        "tool.exec", "tool.result", "note:no-results", "sources",
        "request #2", "stream", "response #2", "usage", "citations", "finish",
      ])
    );
    expect(lines).toHaveLength(actions.length);
  });

  it("baris membawa timestamp relatif, step, actor, dan durasi", () => {
    const res = byAction("response #1")[0];
    expect(res.tMs).toBe(6);
    expect(res.step).toBe(1);
    expect(res.actor).toBe("llm");
    expect(res.durMs).toBe(4);
    expect(res.detail).toContain("finish=tool_calls");
    expect(res.detail).toContain("1 tool_call");
  });

  it("thinking beberapa chunk diringkas jadi satu baris berhitung", () => {
    const t = byAction("thinking");
    expect(t).toHaveLength(1);
    expect(t[0].detail).toMatch(/2 chunk/);
    expect(t[0].detail).toMatch(/16 B/);
  });

  it("delta stream dialirkan sebagai satu baris ringkas sebelum respons", () => {
    const stream = byAction("stream")[0];
    expect(stream.detail).toBe("2 delta · 10 B");
    const order = lines.map((l) => l.action);
    expect(order.indexOf("stream")).toBeLessThan(order.indexOf("response #2"));
  });

  it("tool row: provenance + status + durasi terlihat", () => {
    const exec = byAction("tool.exec")[0];
    expect(exec.level).toBe("tool");
    expect(exec.status).toBe("running");
    expect(exec.source).toBe("browser");
    expect(exec.detail).toContain("berita");

    const result = byAction("tool.result")[0];
    expect(result.status).toBe("empty"); // hits=0 → "0 hasil", bukan "ok"
    expect(result.durMs).toBe(2);
    expect(result.source).toBe("browser");
    expect(result.detail).toContain("0 hasil");
  });

  it("tool yang gagal menjadi level error", () => {
    const lines2 = buildLog([
      { type: "tool_result", t_ms: 1, step: 1, id: "x", name: "fetch_url", source: "browser", ok: false, hits: 0, summary: "fetch_url gagal", duration_ms: 5, data: { error: "boom" } },
    ]);
    expect(lines2[0].status).toBe("failed");
    expect(lines2[0].level).toBe("error");
  });

  it("sumber terdaftar dan hasil verifikasi sitasi ikut tercatat", () => {
    const src = byAction("sources")[0];
    expect(src.status).toBe("empty");
    const cit = byAction("citations")[0];
    expect(cit.level).toBe("warn");
    expect(cit.detail).toContain("no-evidence");
  });

  it("baris menyimpan payload mentah untuk dibuka di UI", () => {
    const req = byAction("request #1")[0];
    expect(req.raw.message_count).toBe(2);
    expect(req.raw.sampling).toEqual({ temperature: 0.7, max_tokens: 2048, logprobs: true });
  });

  it("run tanpa event → log kosong, tidak crash", () => {
    expect(buildLog([])).toEqual([]);
  });

  it("event tanpa step/t_ms tetap aman", () => {
    const l = buildLog([{ type: "unknown_event", foo: 1 }]);
    expect(l[0].action).toBe("unknown_event");
    expect(l[0].tMs).toBeNull();
    expect(l[0].status).toBe("n/a");
  });
});

describe("formatting & ekspor", () => {
  it("fmtT/fmtDur memakai gutter tetap", () => {
    expect(fmtT(0)).toBe("t+0.00s");
    expect(fmtT(1234.5)).toBe("t+1.23s");
    expect(fmtT(null)).toContain("—");
    expect(fmtDur(42)).toBe("42ms");
    expect(fmtDur(1234)).toBe("1.23s");
    expect(fmtDur(null)).toBe("");
  });

  it("logToText menghasilkan kolom sejajar yang bisa disalin", () => {
    const text = logToText(buildLog(TRACE));
    const rows = text.split("\n");
    expect(rows[0]).toContain("t+0.00s");
    expect(rows[0]).toContain("mock-agent");
    expect(rows.some((r) => r.includes("tool.exec") && r.includes("web_search"))).toBe(true);
    expect(rows[rows.length - 1]).toContain("finish");
  });
});
