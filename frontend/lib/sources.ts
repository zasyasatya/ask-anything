/* Provenance of agent output + citation helpers.
   The UI must always answer "where did this come from?" — a Mermaid diagram
   from `create_diagram` is *generated*, a search hit from `web_search` is
   *external evidence* that has to be citable, and "browser returned nothing"
   is a distinct, visible state (not an empty bubble). */

export type ToolSource = "browser" | "diagram" | "compute";

/** One citable URL registered by a browser tool (mirrors `app/sources.py`). */
export interface SourceRef {
  index: number;
  url: string;
  title: string;
  tool: string;
  origin: string;
  snippet: string;
  read: boolean;
  cited: boolean;
}

export interface CitationReport {
  status: "cited" | "appended" | "no-evidence" | "na";
  total: number;
  cited: number[];
  uncited: number[];
  invalid: number[];
  detail: string;
}

export interface SourceMeta {
  /** Badge label. */
  label: string;
  icon: string;
  /** Is this external evidence that must be cited? */
  needsCitation: boolean;
  /** Short explanation for the `title` tooltip. */
  hint: string;
  /** Tailwind classes for the chip. */
  chip: string;
  dot: string;
}

export const SOURCE_META: Record<ToolSource, SourceMeta> = {
  browser: {
    label: "Browser",
    icon: "🌐",
    needsCitation: true,
    hint: "Bukti eksternal: diambil langsung dari web oleh web_search / fetch_url. Setiap klaim dari sini wajib disitasi.",
    chip: "border-sky-200 bg-sky-50 text-sky-700",
    dot: "bg-sky-500",
  },
  diagram: {
    label: "Tool diagram",
    icon: "🔀",
    needsCitation: false,
    hint: "Konten dihasilkan tool create_diagram (struktur dari LLM, rendering deterministik di UI). Bukan sumber web — tidak bisa disitasi sebagai bukti.",
    chip: "border-violet-200 bg-violet-50 text-violet-700",
    dot: "bg-violet-500",
  },
  compute: {
    label: "Kalkulator",
    icon: "🧮",
    needsCitation: false,
    hint: "Hasil komputasi lokal yang deterministik (AST-safe arithmetic). Dapat diverifikasi ulang, tidak butuh sitasi.",
    chip: "border-zinc-200 bg-zinc-100 text-zinc-600",
    dot: "bg-zinc-400",
  },
};

/** Tool name → provenance. Mirrors `tool_source()` on the backend. */
export const TOOL_SOURCE: Record<string, ToolSource> = {
  web_search: "browser",
  fetch_url: "browser",
  create_diagram: "diagram",
  calculator: "compute",
};

export function sourceOf(toolName: string, fromEvent?: unknown): ToolSource {
  const known = TOOL_SOURCE[toolName];
  if (known) return known;
  // Prefer what the backend reported (custom tools), but never let an unknown
  // tool claim to be web evidence.
  const v = typeof fromEvent === "string" ? fromEvent : "";
  return v === "browser" || v === "diagram" ? (v as ToolSource) : "compute";
}

export function metaOf(toolName: string, fromEvent?: unknown): SourceMeta {
  return SOURCE_META[sourceOf(toolName, fromEvent)];
}

/** Result state of one tool execution — drives the chip colour + wording. */
export type ToolOutcome = "running" | "ok" | "empty" | "failed";

export function outcomeOf(ev: {
  ok?: unknown;
  hits?: unknown;
  status?: string;
  summary?: unknown;
}): ToolOutcome {
  if (ev.status === "running") return "running";
  if (ev.ok === false) return "failed";
  if (typeof ev.summary === "string" && /^error/i.test(ev.summary)) return "failed";
  if (ev.hits === 0) return "empty";
  return "ok";
}

export const OUTCOME_LABEL: Record<ToolOutcome, string> = {
  running: "berjalan…",
  ok: "selesai",
  empty: "0 hasil — belum ada data",
  failed: "gagal",
};

/** Dark-theme badge classes for the interpreter (same provenance colours). */
export const SOURCE_BADGE: Record<string, string> = {
  Browser: "bg-sky-500/15 text-sky-300",
  "Tool diagram": "bg-violet-500/15 text-violet-300",
  Kalkulator: "bg-zinc-500/15 text-zinc-300",
};

/** `[1]` / `[2,3]` markers understood as citations (mirrors backend regex). */
const CITE_RE = /\[(\d{1,3}(?:\s*[,;-]\s*\d{1,3})*)\]/g;

export interface TextPart {
  text: string;
  /** Citation indices found immediately after this text, if any. */
  cites: number[];
}

/** Split text into segments with their trailing inline citations. */
export function splitCitations(text: string): TextPart[] {
  const out: TextPart[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  CITE_RE.lastIndex = 0;
  while ((m = CITE_RE.exec(text))) {
    out.push({ text: text.slice(last, m.index), cites: [] });
    last = m.index + m[0].length;
    const nums = m[1]
      .split(/[,;-]/)
      .map((n) => parseInt(n.trim(), 10))
      .filter((n) => Number.isFinite(n));
    if (out.length && nums.length) out[out.length - 1].cites = nums;
    else out.push({ text: m[0], cites: nums });
  }
  if (last < text.length) out.push({ text: text.slice(last), cites: [] });
  return out.filter((p, i) => p.text !== "" || p.cites.length || i === 0);
}

/** Does this answer contain a `## Sumber` section produced by the backend? */
export function hasSourcesBlock(text: string): boolean {
  return /^\s*##\s+Sumber\s*$/im.test(text);
}

export type CitationTone = "ok" | "warn" | "muted";

export function citationTone(rep?: CitationReport | null): CitationTone {
  if (!rep) return "muted";
  if (rep.status === "cited") return "ok";
  if (rep.status === "no-evidence" || rep.status === "na") return "muted";
  return "warn";
}

export function citationLabel(rep?: CitationReport | null): string {
  if (!rep) return "tanpa info sitasi";
  switch (rep.status) {
    case "cited":
      return `${rep.cited.length}/${rep.total} klaim bersitasi`;
    case "appended":
      return "sitasi disisipkan otomatis (model tidak menulis [n])";
    case "no-evidence":
      return "belum ada hasil browser — tidak ada yang bisa disitasi";
    default:
      return "tidak memakai sumber web";
  }
}
