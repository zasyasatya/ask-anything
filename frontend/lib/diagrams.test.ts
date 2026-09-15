import { describe, expect, it } from "vitest";
import {
  answerHasDiagram,
  diagramArtifacts,
  diagramFromToolResult,
  mermaidFences,
  mergeDiagram,
  mergeDiagrams,
  normalizeMermaid,
} from "./diagrams";

const SRC = 'flowchart TD\n  a["Mulai"]\n  b["Selesai"]\n  a --> b';

describe("normalizeMermaid", () => {
  it("mengabaikan spasi, komentar, dan besar-kecil huruf", () => {
    expect(normalizeMermaid("flowchart TD\n  A --> B   %% catatan")).toBe(
      normalizeMermaid("flowchart td\nA   -->   B"),
    );
  });
});

describe("answerHasDiagram", () => {
  it("mengenali diagram yang sama walau format penulisannya berbeda", () => {
    const answer = `Berikut diagramnya:\n\n\`\`\`mermaid\n${SRC.replace(/  /g, "")}\n\`\`\`\n`;
    expect(answerHasDiagram(answer, SRC)).toBe(true);
  });

  it("jawaban tanpa fence mermaid tidak dianggap sudah memuat diagram", () => {
    expect(answerHasDiagram("Sudah saya buatkan diagramnya.", SRC)).toBe(false);
    expect(mermaidFences("teks biasa")).toEqual([]);
  });
});

describe("diagramFromToolResult", () => {
  it("mengambil artefak dari payload create_diagram", () => {
    const d = diagramFromToolResult("create_diagram", {
      kind: "flowchart",
      title: "Alur",
      mermaid: SRC,
      warnings: ["node 'b' dibuat otomatis"],
    });
    expect(d?.title).toBe("Alur");
    expect(d?.mermaid).toBe(SRC);
    expect(d?.warnings).toEqual(["node 'b' dibuat otomatis"]);
  });

  it("mengabaikan tool lain dan payload gagal", () => {
    expect(diagramFromToolResult("web_search", { mermaid: SRC })).toBeNull();
    expect(diagramFromToolResult("create_diagram", { error: "boom" })).toBeNull();
    expect(diagramFromToolResult("create_diagram", null)).toBeNull();
  });
});

describe("diagramArtifacts (meta riwayat)", () => {
  it("defensif terhadap meta kosong/rusak", () => {
    expect(diagramArtifacts(undefined)).toEqual([]);
    expect(diagramArtifacts("nope")).toEqual([]);
    expect(diagramArtifacts([{ title: "tanpa mermaid" }])).toEqual([]);
  });

  it("membaca artefak dari backend dan memberi default yang aman", () => {
    const [d] = diagramArtifacts([{ mermaid: SRC }]);
    expect(d.tool).toBe("create_diagram");
    expect(d.kind).toBe("flowchart");
    expect(d.title).toBe("Diagram");
  });
});

describe("mergeDiagram(s)", () => {
  it("dedupe berdasarkan sumber yang dinormalisasi", () => {
    const a = diagramArtifacts([{ title: "A", mermaid: SRC }]);
    const same = diagramArtifacts([{ title: "A lagi", mermaid: SRC.replace(/ /g, "  ") }]);
    expect(mergeDiagrams(a, same)).toHaveLength(1);
    expect(mergeDiagram(a, same[0])).toHaveLength(1);
  });

  it("menambahkan diagram yang berbeda", () => {
    const a = diagramArtifacts([{ title: "A", mermaid: SRC }]);
    const b = diagramArtifacts([{ title: "B", mermaid: "flowchart LR\nx --> y" }]);
    expect(mergeDiagrams(a, b).map((d) => d.title)).toEqual(["A", "B"]);
  });
});
