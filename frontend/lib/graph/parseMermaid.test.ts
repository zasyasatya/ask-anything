import { describe, expect, it } from "vitest";
import { parseMermaid, graphSummary } from "./parseMermaid";

describe("parseMermaid — flowchart dasar", () => {
  const src = [
    "flowchart TD",
    'A["Mulai"] --> B{Valid?}',
    "B -->|ya| C([Selesai])",
    "B -->|tidak| D((Ulangi))",
    "D --> A",
  ].join("\n");

  it("membaca arah, node berbentuk, dan edge ber-label", () => {
    const m = parseMermaid(src);
    expect(m.direction).toBe("TD");
    expect(m.kind).toBe("flowchart");
    expect(m.nodes.map((n) => n.id).sort()).toEqual(["A", "B", "C", "D"]);
    expect(m.nodes.find((n) => n.id === "A")?.label).toBe("Mulai");
    expect(m.nodes.find((n) => n.id === "B")?.shape).toBe("diamond");
    expect(m.nodes.find((n) => n.id === "C")?.shape).toBe("stadium");
    expect(m.nodes.find((n) => n.id === "D")?.shape).toBe("circle");
    expect(m.edges).toHaveLength(4);
    expect(m.edges.find((e) => e.from === "B" && e.to === "C")?.label).toBe("ya");
    expect(m.problems).toEqual([]);
  });

  it("graph LR → direction LR", () => {
    const m = parseMermaid("graph LR\nX --> Y");
    expect(m.direction).toBe("LR");
    expect(m.edges[0]).toMatchObject({ from: "X", to: "Y" });
  });

  it("jenis edge: dotted, thick, plain", () => {
    const m = parseMermaid(
      ["flowchart LR", "A -.-> B", "C ==> D", "E --- F"].join("\n"),
    );
    expect(m.edges.map((e) => e.kind)).toEqual(["dotted", "thick", "plain"]);
  });

  it("label bentuk teks: -- teks --> dan == teks ==>", () => {
    const m = parseMermaid(
      ["flowchart TD", "A -- butuh fakta --> B", "C == penting ==> D"].join("\n"),
    );
    expect(m.edges[0].label).toBe("butuh fakta");
    expect(m.edges[1].label).toBe("penting");
    expect(m.edges[1].kind).toBe("thick");
  });

  it("rantai A --> B --> C menjadi dua edge", () => {
    const m = parseMermaid("flowchart TD\nA --> B --> C");
    expect(m.edges.map((e) => [e.from, e.to])).toEqual([
      ["A", "B"],
      ["B", "C"],
    ]);
  });

  it("chaining & (A & B --> C)", () => {
    const m = parseMermaid("flowchart TD\nA & B --> C");
    expect(m.edges.map((e) => `${e.from}>${e.to}`).sort()).toEqual(["A>C", "B>C"]);
  });

  it("komentar %% dan pemisah ; ditangani", () => {
    const m = parseMermaid(
      ["flowchart TD", "%% catatan penting", "A --> B; B --> C"].join("\n"),
    );
    expect(m.edges).toHaveLength(2);
    expect(m.problems).toEqual([]);
  });

  it("subgraph memetakan anggota group", () => {
    const m = parseMermaid(
      [
        "flowchart TD",
        "subgraph inti [Inti Sistem]",
        "A --> B",
        "end",
        "B --> C",
      ].join("\n"),
    );
    expect(m.groups).toEqual([{ id: "inti", label: "Inti Sistem" }]);
    expect(m.nodes.find((n) => n.id === "A")?.group).toBe("inti");
    expect(m.nodes.find((n) => n.id === "B")?.group).toBe("inti");
    expect(m.nodes.find((n) => n.id === "C")?.group).toBeNull();
  });

  it("node yang hanya muncul di edge tetap dibuat", () => {
    const m = parseMermaid("flowchart TD\nbaru_node --> B");
    expect(m.nodes.map((n) => n.id).sort()).toEqual(["B", "baru_node"]);
    expect(m.nodes.find((n) => n.id === "baru_node")?.label).toBe("baru node");
  });
});

describe("parseMermaid — toleransi error", () => {
  it("tidak melempar untuk input kosong / aneh", () => {
    expect(parseMermaid("").nodes).toHaveLength(0);
    expect(parseMermaid("   \n\n").nodes).toHaveLength(0);
    expect(() => parseMermaid("???!!!")).not.toThrow();
  });

  it("baris rusak dicatat, node valid tetap dirender", () => {
    const m = parseMermaid(
      ["flowchart TD", "A[Mulai] --> B", "ini baris rusak ???", "B --> C[Tutup]"].join("\n"),
    );
    expect(m.nodes.map((n) => n.id)).toContain("A");
    expect(m.nodes.map((n) => n.id)).toContain("C");
    expect(m.edges).toHaveLength(2);
    expect(m.problems.length).toBeGreaterThan(0);
  });

  it("kurung tidak seimbang tidak menggugurkan seluruh diagram", () => {
    const m = parseMermaid("flowchart TD\nA[unclosed label\nA --> B");
    expect(m.nodes.some((n) => n.id === "B")).toBe(true);
    expect(m.edges.length).toBeGreaterThanOrEqual(1);
  });

  it("edge menggantung dicatat sebagai problem, bukan exception", () => {
    const m = parseMermaid("flowchart TD\nA -->");
    expect(m.problems.some((p) => p.includes("edge tanpa tujuan"))).toBe(true);
  });

  it("CRLF dan tab tidak merusak parsing", () => {
    const m = parseMermaid("flowchart TD\r\n\tA --> B\r\n");
    expect(m.edges).toHaveLength(1);
  });

  it("directive styling diabaikan tanpa problem", () => {
    const m = parseMermaid(
      ["flowchart TD", "A --> B", "style A fill:#f9f", "classDef x color:#000"].join("\n"),
    );
    expect(m.problems).toEqual([]);
    expect(m.edges).toHaveLength(1);
  });
});

describe("parseMermaid — mindmap", () => {
  it("indentasi menjadi hierarki edge", () => {
    const m = parseMermaid(
      ["mindmap", "  root((Rencana))", "    Riset", "      Pasar", "    Eksekusi"].join("\n"),
    );
    expect(m.kind).toBe("mindmap");
    expect(m.nodes).toHaveLength(4);
    expect(m.edges.map((e) => `${e.from}>${e.to}`)).toEqual([
      "root>Riset",
      "Riset>Pasar",
      "root>Eksekusi",
    ]);
  });
});

describe("graphSummary", () => {
  it("meringkas jumlah node/edge", () => {
    const m = parseMermaid("flowchart TD\nA --> B");
    expect(graphSummary(m)).toContain("2 node");
    expect(graphSummary(m)).toContain("1 edge");
  });
});
