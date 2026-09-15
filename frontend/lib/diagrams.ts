/* Artefak diagram: dari mana kartu diagram di UI mendapat sumbernya.
   
   Tool `create_diagram` mengembalikan payload berisi sumber Mermaid. Selama ini
   kartu diagram hanya muncul bila model **menyalin ulang** sumber itu sebagai
   fence ```mermaid di jawabannya — model nyata jarang melakukannya, sehingga
   "diagram tidak ada" padahal tool-nya sukses. Modul ini menyatukan cara
   mengambil artefak diagram dari:
     - event `tool_result` (run yang sedang berlangsung),
     - `meta.diagrams` pesan assistant (riwayat),
     - fence ```mermaid di dalam teks jawaban.
   Ditambah dedupe supaya diagram yang sama tidak dirender dua kali. */

export interface DiagramArtifact {
  /** Tool asal (selalu "create_diagram" untuk keluaran tool). */
  tool: string;
  /** "structured" = node/edge dari LLM · "model" = sumber Mermaid dari model. */
  source: string;
  kind: string;
  title: string;
  mermaid: string;
  warnings: string[];
}

/** Bandingkan sumber Mermaid tanpa peduli spasi/komentar/arah default. */
export function normalizeMermaid(src: string): string {
  return String(src || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((l) => l.replace(/\s*%%[^\n]*$/, "").trim())
    .filter(Boolean)
    .join("\n")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/** Semua fence ```mermaid di dalam teks jawaban. */
export function mermaidFences(text: string): string[] {
  const out: string[] = [];
  const re = /```mermaid[ \t]*\n([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) out.push(m[1]);
  return out;
}

/** Apakah jawaban sudah memuat fence untuk diagram ini (jangan render 2×). */
export function answerHasDiagram(answer: string, mermaid: string): boolean {
  const target = normalizeMermaid(mermaid);
  if (!target) return false;
  return mermaidFences(answer).some((f) => {
    const got = normalizeMermaid(f);
    return got === target || (got.length > 40 && (got.includes(target) || target.includes(got)));
  });
}

/** Payload `tool_result` → artefak diagram (null bila bukan diagram valid). */
export function diagramFromToolResult(
  name: unknown,
  data: unknown
): DiagramArtifact | null {
  if (String(name) !== "create_diagram") return null;
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  const mermaid = typeof d.mermaid === "string" ? d.mermaid.trim() : "";
  if (!mermaid) return null;
  return {
    tool: "create_diagram",
    source: String(d.source || "structured"),
    kind: String(d.kind || "flowchart"),
    title: String(d.title || "Diagram"),
    mermaid,
    warnings: Array.isArray(d.warnings) ? d.warnings.map(String) : [],
  };
}

/** `meta.diagrams` dari backend → artefak yang bisa dirender (defensif). */
export function diagramArtifacts(raw: unknown): DiagramArtifact[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const d = item as Record<string, unknown>;
    const mermaid = typeof d.mermaid === "string" ? d.mermaid.trim() : "";
    if (!mermaid) return [];
    return [
      {
        tool: String(d.tool || "create_diagram"),
        source: String(d.source || "structured"),
        kind: String(d.kind || "flowchart"),
        title: String(d.title || "Diagram"),
        mermaid,
        warnings: Array.isArray(d.warnings) ? d.warnings.map(String) : [],
      },
    ];
  });
}

/** Tambahkan artefak tanpa duplikat (dipakai saat event streaming masuk). */
export function mergeDiagrams(
  list: DiagramArtifact[],
  next: DiagramArtifact[]
): DiagramArtifact[] {
  const seen = new Set(list.map((d) => normalizeMermaid(d.mermaid)));
  const out = [...list];
  for (const d of next) {
    const key = normalizeMermaid(d.mermaid);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(d);
  }
  return out;
}

/** Varian satu-artefak dari :func:`mergeDiagrams`. */
export function mergeDiagram(
  list: DiagramArtifact[],
  next: DiagramArtifact | null
): DiagramArtifact[] {
  return next ? mergeDiagrams(list, [next]) : list;
}
