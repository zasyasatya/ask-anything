import { describe, expect, it } from "vitest";
import {
  SOURCE_META,
  citationLabel,
  citationTone,
  hasSourcesBlock,
  metaOf,
  outcomeOf,
  sourceOf,
  splitCitations,
  type CitationReport,
} from "./sources";

describe("provenance kelas tool", () => {
  it("membedakan browser vs tool diagram vs kalkulator", () => {
    expect(sourceOf("web_search")).toBe("browser");
    expect(sourceOf("fetch_url")).toBe("browser");
    expect(sourceOf("create_diagram")).toBe("diagram");
    expect(sourceOf("calculator")).toBe("compute");
  });

  it("hanya bukti browser yang wajib disitasi", () => {
    expect(SOURCE_META.browser.needsCitation).toBe(true);
    expect(SOURCE_META.diagram.needsCitation).toBe(false);
    expect(SOURCE_META.compute.needsCitation).toBe(false);
    expect(SOURCE_META.browser.label).toBe("Browser");
    expect(SOURCE_META.diagram.label).toBe("Tool diagram");
  });

  it("tool tak dikenal tidak boleh mengaku sebagai bukti web", () => {
    expect(sourceOf("mysterious_tool")).toBe("compute");
    expect(sourceOf("mysterious_tool", "browser")).toBe("browser"); // backend yang menentukan
    expect(sourceOf("mysterious_tool", "diagram")).toBe("diagram");
    // unknown string provenance → compute, bukan browser
    expect(sourceOf("mysterious_tool", "weird")).toBe("compute");
  });

  it("metaOf memakai provenance dari event bila nama tool tak dikenal", () => {
    expect(metaOf("create_diagram").icon).toBe("🔀");
    expect(metaOf("custom", "browser").label).toBe("Browser");
  });
});

describe("status hasil tool", () => {
  it("membedakan berjalan / ok / 0 hasil / gagal", () => {
    expect(outcomeOf({ status: "running" })).toBe("running");
    expect(outcomeOf({ ok: true, hits: 3 })).toBe("ok");
    expect(outcomeOf({ ok: true, hits: 0 })).toBe("empty");
    expect(outcomeOf({ ok: false })).toBe("failed");
    expect(outcomeOf({ summary: "error: timeout" })).toBe("failed");
    // diagram tidak punya hits (bukan hasil pencarian) → tetap "ok"
    expect(outcomeOf({ ok: true, hits: null })).toBe("ok");
  });
});

describe("splitCitations", () => {
  it("memecah teks pada marker [n] dan memisahkannya", () => {
    const parts = splitCitations("Harga naik [1] dan stabil [2,3].");
    expect(parts.map((p) => p.text)).toEqual(["Harga naik ", " dan stabil ", "."]);
    expect(parts[0].cites).toEqual([1]);
    expect(parts[1].cites).toEqual([2, 3]);
  });

  it("teks tanpa sitasi tetap satu bagian", () => {
    const parts = splitCitations("tidak ada sitasi");
    expect(parts).toHaveLength(1);
    expect(parts[0].cites).toEqual([]);
  });

  it("kutipan markdown [label](url) tidak dianggap nomor sitasi", () => {
    const parts = splitCitations("lihat [sumber](https://x.test) ya");
    expect(parts.every((p) => p.cites.length === 0)).toBe(true);
  });
});

describe("label & tone sitasi", () => {
  const rep = (over: Partial<CitationReport>): CitationReport => ({
    status: "cited", total: 3, cited: [1, 2], uncited: [3], invalid: [],
    detail: "", ...over,
  });

  it("cited → ok, appended → warn, no-evidence → muted", () => {
    expect(citationTone(rep({}))).toBe("ok");
    expect(citationTone(rep({ status: "appended", cited: [] }))).toBe("warn");
    expect(citationTone(rep({ status: "no-evidence", total: 0, cited: [], uncited: [] }))).toBe("muted");
    expect(citationTone(null)).toBe("muted");
  });

  it("label menjelaskan 'browser belum ada hasil' apa adanya", () => {
    expect(citationLabel(rep({}))).toBe("2/3 klaim bersitasi");
    expect(
      citationLabel(rep({ status: "no-evidence", total: 0, cited: [], uncited: [] }))
    ).toContain("belum ada hasil browser");
  });

  it("mengenali blok Sumber yang disisipkan backend", () => {
    expect(hasSourcesBlock("jawaban\n\n## Sumber\n\n1. [A](https://a)")).toBe(true);
    expect(hasSourcesBlock("jawaban tanpa sumber")).toBe(false);
  });
});
