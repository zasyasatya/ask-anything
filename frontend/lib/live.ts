/* Status "sedang berjalan" satu run agent, sebagai reducer murni.

   Dipisah dari page.tsx supaya alur streaming bisa diuji tanpa DOM: setiap
   event SSE dari `/api/chat` diumpankan ke :func:`reduceLive`, dan hasilnya
   adalah apa yang dilihat pengguna selama run berlangsung.

   Dua hal yang dulu hilang di jalur live dan sekarang dijaga di sini:
   - **sumber bernomor** — muncul dari event `sources`/`citations` sehingga
     marker `[n]` yang sedang mengalir sudah bisa ditautkan (tanpa menunggu
     riwayat dimuat ulang);
   - **diagram dari tool** — diambil dari payload `tool_result`
     (`create_diagram`) dan dari snapshot `agent_done`, bukan dari teks
     jawaban, jadi diagram tetap tampil walau model tidak menyalin fence
     ```mermaid.
*/
import {
  diagramArtifacts,
  diagramFromToolResult,
  mergeDiagram,
  mergeDiagrams,
  type DiagramArtifact,
} from "./diagrams";
import type { CitationReport, SourceRef } from "./sources";

export interface LiveTool {
  name: string;
  status: string;
  summary?: string;
  source?: string;
  ok?: boolean;
  hits?: number | null;
  duration_ms?: number;
  new_sources?: number;
  /** id panggilan tool — dipakai untuk mencocokkan hasil dengan pemanggilnya. */
  callId?: string;
}

export interface LiveState {
  answer: string;
  thinking: string;
  tools: LiveTool[];
  /** Sumber bernomor yang sudah terdaftar browser tool (mengalir via trace). */
  sources?: SourceRef[];
  /** Laporan sitasi final — hanya ada setelah run selesai. */
  citations?: CitationReport | null;
  /** Artefak diagram dari tool create_diagram (bukan fence di teks jawaban). */
  diagrams?: DiagramArtifact[];
}

export const EMPTY_LIVE: LiveState = {
  answer: "",
  thinking: "",
  tools: [],
  sources: [],
  citations: null,
  diagrams: [],
};

/** Event `citations` (trace akhir run) → CitationReport untuk bar sitasi. */
export function citationReport(ev: Record<string, unknown>): CitationReport {
  const nums = (v: unknown): number[] =>
    Array.isArray(v) ? v.map(Number).filter((n) => Number.isFinite(n)) : [];
  return {
    status: (ev.status as CitationReport["status"]) || "na",
    total: Number(ev.total) || 0,
    cited: nums(ev.cited),
    uncited: nums(ev.uncited),
    invalid: nums(ev.invalid),
    detail: String(ev.detail || ""),
  };
}

/** Satu event SSE → status live berikutnya (immutable, tanpa efek samping). */
export function reduceLive(
  state: LiveState,
  ev: Record<string, unknown>
): LiveState {
  const type = String(ev.type || "");
  switch (type) {
    case "thinking":
      return { ...state, thinking: state.thinking + String(ev.text ?? "") };
    case "delta":
      return { ...state, answer: state.answer + String(ev.text ?? "") };
    case "tool_call":
      return {
        ...state,
        tools: [
          ...state.tools,
          {
            name: String(ev.name ?? "?"),
            status: "running",
            callId: ev.id as string | undefined,
            source: ev.source as string | undefined,
          },
        ],
      };
    case "sources":
      return {
        ...state,
        sources: (ev.items as SourceRef[]) || state.sources || [],
      };
    case "citations":
      return {
        ...state,
        sources: (ev.sources as SourceRef[]) || state.sources || [],
        citations: citationReport(ev),
      };
    case "tool_result": {
      const diagram = diagramFromToolResult(ev.name, ev.data);
      const tools = state.tools.map((t, i) => {
        // cocokkan by id bila ada; fallback: pemanggilan terakhir yang belum
        // selesai (beberapa tool bisa jalan berurutan dalam 1 step)
        const match =
          (ev.id != null && t.callId === ev.id && t.status === "running") ||
          (i === state.tools.length - 1 && t.status === "running");
        return match
          ? {
              ...t,
              status: ev.ok === false ? "failed" : "done",
              summary: ev.summary as string,
              source: ev.source as string | undefined,
              ok: ev.ok as boolean | undefined,
              hits: ev.hits as number | null | undefined,
              duration_ms: ev.duration_ms as number | undefined,
              new_sources: ev.new_sources as number | undefined,
            }
          : t;
      });
      return {
        ...state,
        tools,
        diagrams: mergeDiagram(state.diagrams || [], diagram),
      };
    }
    case "agent_done":
      // Snapshot akhir run: kartu diagram + daftar sumber tetap ada walau
      // pengambilan ulang riwayat gagal.
      return {
        ...state,
        sources: (ev.sources as SourceRef[]) || state.sources || [],
        citations: ev.citations
          ? citationReport(ev.citations as Record<string, unknown>)
          : state.citations,
        diagrams: mergeDiagrams(state.diagrams || [], diagramArtifacts(ev.diagrams)),
      };
    case "error":
      return { ...state, answer: `${state.answer}\n\n> ⚠️ ${String(ev.message ?? "")}` };
    default:
      return state;
  }
}

/** Umpankan banyak event (mis. seluruh isi trace) ke reducer. */
export function reduceLiveAll(
  events: Array<Record<string, unknown>>,
  initial: LiveState = EMPTY_LIVE
): LiveState {
  return events.reduce(reduceLive, initial);
}
