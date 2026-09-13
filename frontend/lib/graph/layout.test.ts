import { describe, expect, it } from "vitest";
import { layoutGraph, nodeSize } from "./layout";
import { parseMermaid } from "./parseMermaid";
import type { GraphModel } from "./types";

function rectsOverlap(
  a: { x: number; y: number; w: number; h: number },
  b: { x: number; y: number; w: number; h: number },
): boolean {
  return (
    Math.abs(a.x - b.x) < (a.w + b.w) / 2 - 1 &&
    Math.abs(a.y - b.y) < (a.h + b.h) / 2 - 1
  );
}

const CHAIN = "flowchart TD\nA[Mulai] --> B[Proses]\nB --> C{Cek}\nC -->|ya| D[Selesai]";

describe("layoutGraph", () => {
  it("rantai TD: rank bawah selalu lebih rendah", () => {
    const lay = layoutGraph(parseMermaid(CHAIN));
    const y = (id: string) => lay.nodes.find((n) => n.id === id)!.y;
    expect(y("B")).toBeGreaterThan(y("A"));
    expect(y("C")).toBeGreaterThan(y("B"));
    expect(y("D")).toBeGreaterThan(y("C"));
  });

  it("rantai LR: sumbu utama berpindah ke x", () => {
    const lay = layoutGraph(parseMermaid(CHAIN.replace("TD", "LR")));
    expect(lay.direction).toBe("LR");
    const x = (id: string) => lay.nodes.find((n) => n.id === id)!.x;
    expect(x("B")).toBeGreaterThan(x("A"));
    expect(x("D")).toBeGreaterThan(x("C"));
  });

  it("tidak ada node yang bertumpuk", () => {
    const src = [
      "flowchart TD",
      "A --> B", "A --> C", "A --> D",
      "B --> E", "C --> E", "D --> E",
      "E --> F[Final dengan label yang agak panjang sekali]",
    ].join("\n");
    const lay = layoutGraph(parseMermaid(src));
    for (let i = 0; i < lay.nodes.length; i++) {
      for (let j = i + 1; j < lay.nodes.length; j++) {
        expect(rectsOverlap(lay.nodes[i], lay.nodes[j]),
          `${lay.nodes[i].id} vs ${lay.nodes[j].id}`).toBe(false);
      }
    }
  });

  it("siklus tidak membuat hang dan tetap ter-layout", () => {
    const lay = layoutGraph(parseMermaid("flowchart TD\nA --> B\nB --> A\nB --> C"));
    expect(lay.nodes).toHaveLength(3);
    expect(lay.width).toBeGreaterThan(0);
  });

  it("deterministik: input sama → output sama", () => {
    const m = parseMermaid(CHAIN);
    expect(layoutGraph(m)).toEqual(layoutGraph(m));
  });

  it("model kosong aman", () => {
    const lay = layoutGraph({ direction: "TD", kind: "unknown", nodes: [], edges: [], groups: [], problems: [] } as GraphModel);
    expect(lay.nodes).toHaveLength(0);
    expect(lay.width).toBe(0);
  });

  it("bounding box subgraph memuat anggotanya", () => {
    const lay = layoutGraph(parseMermaid(
      ["flowchart TD", "subgraph g1 [Grup]", "A --> B", "end", "B --> C"].join("\n"),
    ));
    const g = lay.groups.find((x) => x.id === "g1")!;
    for (const id of ["A", "B"]) {
      const n = lay.nodes.find((x) => x.id === id)!;
      expect(n.x).toBeGreaterThan(g.x);
      expect(n.x).toBeLessThan(g.x + g.w);
      expect(n.y).toBeGreaterThan(g.y);
      expect(n.y).toBeLessThan(g.y + g.h);
    }
  });
});

describe("nodeSize", () => {
  it("label panjang dibatasi maks lebar", () => {
    expect(nodeSize("x".repeat(500), "rect").w).toBeLessThanOrEqual(232);
  });
  it("multi-line menambah tinggi", () => {
    expect(nodeSize("a\nb\nc", "rect").h).toBeGreaterThan(nodeSize("a", "rect").h);
  });
});
