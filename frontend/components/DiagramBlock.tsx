"use client";
/* DiagramBlock — kartu diagram dengan MODE render yang bisa dipilih:

   - "graph"   : komponen HTML interaktif (GraphView). Toleran terhadap
                 Mermaid rusak: node/edge yang terbaca tetap dirender.
   - "mermaid" : renderer Mermaid asli (SVG statis).

   Preferensi disimpan di localStorage sehingga berlaku global; tiap kartu
   tetap punya toggle sendiri. Bila renderer Mermaid gagal, banner muncul
   dan satu klik memindahkan ke mode graph (fallback bebas-error). */
import { useCallback, useEffect, useMemo, useState } from "react";
import GraphView from "./GraphView";
import Mermaid from "./Mermaid";
import { parseMermaid, graphSummary } from "@/lib/graph/parseMermaid";

export type DiagramMode = "graph" | "mermaid";

const LS_KEY = "aa:diagram-mode";

export function readDiagramMode(): DiagramMode {
  if (typeof window === "undefined") return "graph";
  try {
    const v = window.localStorage.getItem(LS_KEY);
    return v === "mermaid" ? "mermaid" : "graph";
  } catch {
    return "graph";
  }
}

function saveDiagramMode(m: DiagramMode): void {
  try {
    window.localStorage.setItem(LS_KEY, m);
  } catch {
    /* private mode dsb. */
  }
}

export default function DiagramBlock({
  source,
  title,
}: {
  source: string;
  title?: string;
}) {
  const [mode, setMode] = useState<DiagramMode>("graph");
  const [hydrated, setHydrated] = useState(false);
  const [mermaidError, setMermaidError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setMode(readDiagramMode());
    setHydrated(true);
  }, []);

  const model = useMemo(() => parseMermaid(source), [source]);
  const graphOk = model.nodes.length > 0;

  const switchMode = useCallback((m: DiagramMode) => {
    setMode(m);
    saveDiagramMode(m);
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard tidak tersedia */
    }
  };

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 bg-zinc-50/70 px-3 py-2">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="6" cy="6" r="2.6" />
            <circle cx="18" cy="6" r="2.6" />
            <circle cx="12" cy="18" r="2.6" />
            <path d="M7.8 7.8 10.5 16M16.2 7.8 13.5 16M8.6 6h6.8" />
          </svg>
          {mode === "graph" ? "graph interaktif" : "mermaid diagram"}
          {mode === "graph" && graphOk && (
            <span className="text-zinc-400">· {graphSummary(model)}</span>
          )}
        </span>

        <div className="flex items-center gap-1.5">
          {model.problems.length > 0 && mode === "graph" && (
            <span
              title={`Baris yang dilewati parser:\n${model.problems.slice(0, 6).join("\n")}`}
              className="rounded-md bg-amber-50 px-2 py-0.5 text-[10.5px] text-amber-600"
            >
              {model.problems.length} baris dilewati
            </span>
          )}
          <button
            type="button"
            onClick={copy}
            title="Salin sumber Mermaid"
            className="rounded-md px-2 py-0.5 text-[11px] text-zinc-500 hover:bg-zinc-200/70"
          >
            {copied ? "tersalin ✓" : "salin"}
          </button>
          <div
            role="radiogroup"
            aria-label="Mode render diagram"
            className="flex overflow-hidden rounded-lg border border-zinc-200 bg-white"
          >
            {(["graph", "mermaid"] as DiagramMode[]).map((m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={mode === m}
                data-testid={`mode-${m}`}
                onClick={() => switchMode(m)}
                className={`px-2.5 py-1 text-[11px] font-medium ${
                  mode === m
                    ? "bg-zinc-800 text-white"
                    : "text-zinc-500 hover:bg-zinc-100"
                }`}
              >
                {m === "graph" ? "Graph" : "Mermaid"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {!hydrated ? (
        <div className="grid h-[460px] place-items-center text-sm text-zinc-400">
          memuat diagram…
        </div>
      ) : mode === "graph" && graphOk ? (
        <GraphView model={model} />
      ) : mode === "graph" && !graphOk ? (
        <div className="p-4">
          <p className="mb-2 text-sm text-zinc-500">
            Sumber tidak mengandung node yang bisa dirender sebagai graph.
          </p>
          <pre className="overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs leading-5 text-zinc-700">
            {source}
          </pre>
        </div>
      ) : (
        <div className="p-3">
          {mermaidError && (
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
              <span className="text-[12px] text-amber-700">
                Mermaid gagal dirender: {mermaidError.slice(0, 90)}
              </span>
              <button
                type="button"
                data-testid="fallback-to-graph"
                onClick={() => switchMode("graph")}
                className="rounded-md bg-amber-600 px-2.5 py-1 text-[11.5px] font-medium text-white hover:bg-amber-700"
              >
                Pakai mode Graph
              </button>
            </div>
          )}
          <Mermaid source={source} title={title} onError={setMermaidError} bare />
        </div>
      )}
    </div>
  );
}
