import { describe, expect, it } from "vitest";
import { EMPTY_LIVE, reduceLive, reduceLiveAll } from "./live";
import { buildLog } from "./log";

describe("live reducer — artifact & event pipeline baru", () => {
  it("event `artifact` (gambar/PPT) masuk daftar artifact live", () => {
    let s = reduceLive(EMPTY_LIVE, {
      type: "artifact",
      id: "a1",
      kind: "image",
      title: "kucing astronot",
      url: "/api/artifacts/a1/download",
      tool: "generate_image",
    });
    expect(s.artifacts).toHaveLength(1);
    expect(s.artifacts?.[0]).toMatchObject({
      id: "a1",
      kind: "image",
      url: "/api/artifacts/a1/download",
    });

    // artifact kedua + id duplikat tidak menumpuk
    s = reduceLive(s, {
      type: "artifact",
      id: "a2",
      kind: "pptx",
      title: "deck",
      url: "/api/artifacts/a2/download",
    });
    s = reduceLive(s, {
      type: "artifact",
      id: "a2",
      kind: "pptx",
      title: "deck v2",
      url: "/api/artifacts/a2/download",
    });
    expect(s.artifacts).toHaveLength(2);
  });

  it("rentetan event RAG (rag_stage → rag_retrieve → delta → agent_done) direduksi tanpa error", () => {
    const s = reduceLiveAll([
      { type: "meta", pipeline: "rag", provider: "mock", model: "m", mode: "rag", temperature: 0.7, max_steps: 1, memory: [] },
      { type: "rag_stage", stage: "embed", status: "ok", backend: "hashing-v1", dim: 384, message: "Query di-embed", duration_ms: 1 },
      {
        type: "rag_retrieve",
        stage: "retrieve",
        status: "ok",
        top_k: 4,
        hits: [{ doc_id: "d1", doc_title: "produk.pdf", seq: 0, page: 1, score: 0.42, preview: "Produk A…" }],
        message: "Retrieval: 1 potongan",
        duration_ms: 2,
      },
      { type: "delta", text: "Berdasarkan dokumen [1]…" },
      { type: "done", answer: "Berdasarkan dokumen [1]…", stopped_reason: "stop" },
    ]);
    expect(s.answer).toContain("Berdasarkan dokumen");
  });

  it("buildLog menampilkan baris RAG & policy & artifact di timeline interpreter", () => {
    const lines = buildLog([
      { type: "meta", pipeline: "rag", provider: "mock", model: "m", mode: "rag", temperature: 0.7, max_steps: 1, memory: [] },
      { type: "rag_stage", t_ms: 1, step: 1, stage: "embed", status: "ok", backend: "hashing-v1", dim: 384, message: "Query di-embed", duration_ms: 1 },
      { type: "rag_retrieve", t_ms: 2, step: 2, stage: "retrieve", status: "ok", top_k: 4, hits: [{ doc_id: "d1", doc_title: "produk.pdf", seq: 0, page: 1, score: 0.42, preview: "Produk A…" }], duration_ms: 2 },
      { type: "artifact", t_ms: 3, step: 2, id: "a1", kind: "pptx", title: "deck", url: "/api/artifacts/a1/download", tool: "generate_ppt" },
      { type: "policy", t_ms: 4, step: 2, action: "tool_blocked", tool: "web_search", message: "tool web_search diblokir oleh kebijakan admin", status: "blocked" },
    ]);
    const actions = lines.map((l) => l.action);
    expect(actions).toContain("start (RAG)");
    expect(actions).toContain("rag.embed");
    expect(actions).toContain("rag.retrieve");
    expect(actions).toContain("artifact.pptx");
    expect(actions).toContain("tool_blocked");
    const pol = lines.find((l) => l.action === "tool_blocked");
    expect(pol?.detail).toContain("diblokir");
    const ret = lines.find((l) => l.action === "rag.retrieve");
    expect(ret?.detail).toContain("produk.pdf");
  });
});
