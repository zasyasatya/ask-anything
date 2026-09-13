"use client";
/* DiagramBlock — kartu diagram dengan MODE render yang bisa dipilih:

   - "graph"   : komponen HTML interaktif (GraphView). Toleran terhadap
                 Mermaid rusak: node/edge yang terbaca tetap dirender.
   - "mermaid" : renderer Mermaid asli (SVG statis).

   Preferensi disimpan di localStorage sehingga berlaku global; tiap kartu
   tetap punya toggle sendiri. Bila renderer Mermaid gagal, banner muncul
   dan satu klik memindahkan ke mode graph (fallback bebas-error).

   Kanvas dibuat selebar mungkin dan bisa fullscreen (dengan fallback focus
   mode bila browser menolak), plus badge PROVENANCE yang menyatakan apakah
   diagram ini keluaran tool create_diagram atau ditulis langsung oleh model —
   keduanya bukan bukti web, dan label itu mengatakannya terus terang. */
import { useCallback, useEffect, useMemo, useState } from "react";
import GraphView from "./GraphView";
import Mermaid from "./Mermaid";
import { parseMermaid, graphSummary } from "@/lib/graph/parseMermaid";
import { useFullscreen } from "@/lib/useFullscreen";
import type { DiagramOrigin } from "@/lib/markdown";

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

function ProvenanceBadge({ origin }: { origin: DiagramOrigin | null }) {
  const fromTool = origin?.tool === "create_diagram";
  return (
    <span
      data-testid="diagram-provenance"
      title={
        fromTool
          ? "Dihasilkan tool create_diagram: struktur node/edge dari LLM, sintaks Mermaid dibangkitkan deterministik oleh backend. Bukan sumber web."
          : "Sumber Mermaid ditulis langsung oleh model di dalam jawaban (bukan output tool). Tidak bisa disitasi sebagai bukti eksternal."
      }
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10.5px] font-medium ${
        fromTool
          ? "bg-violet-50 text-violet-700 ring-1 ring-violet-200"
          : "bg-zinc-100 text-zinc-500 ring-1 ring-zinc-200"
      }`}
    >
      <span aria-hidden="true">{fromTool ? "🔀" : "✍️"}</span>
      {fromTool ? "dari tool create_diagram" : "ditulis model di jawaban"}
    </span>
  );
}

export default function DiagramBlock({
  source,
  title,
  provenance = null,
}: {
  source: string;
  title?: string;
  /** Asal diagram: output tool create_diagram vs teks model. */
  provenance?: DiagramOrigin | null;
}) {
  const [mode, setMode] = useState<DiagramMode>("graph");
  const [hydrated, setHydrated] = useState(false);
  const [mermaidError, setMermaidError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [fitSignal, setFitSignal] = useState(0);
  const fs = useFullscreen();

  useEffect(() => {
    setMode(readDiagramMode());
    setHydrated(true);
  }, []);

  const model = useMemo(() => parseMermaid(source), [source]);
  const graphOk = model.nodes.length > 0;

  const bumpFit = useCallback(() => setFitSignal((n) => n + 1), []);

  // Setelah masuk/keluar fullscreen, refit supaya zoom memakai ruang baru.
  useEffect(() => {
    const id = requestAnimationFrame(bumpFit);
    return () => cancelAnimationFrame(id);
  }, [fs.active, mode, bumpFit]);

  const switchMode = useCallback((m: DiagramMode) => {
    setMode(m);
    saveDiagramMode(m);
  }, []);

  const toggleFullscreen = useCallback(() => {
    fs.toggle();
  }, [fs]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard tidak tersedia */
    }
  };

  const immersive = fs.active;

  return (
    <div
      ref={fs.ref}
      data-testid="diagram-card"
      data-fullscreen={immersive ? "true" : "false"}
      className={
        immersive
          ? "fixed inset-0 z-50 flex flex-col overflow-hidden bg-white"
          : "my-3 flex overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card"
      }
      style={
        immersive
          ? undefined
          : { minHeight: 380, height: "min(66vh, 620px)" }
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 bg-zinc-50/70 px-3 py-2">
        <span className="flex min-w-0 flex-wrap items-center gap-1.5">
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
          <ProvenanceBadge origin={provenance} />
          {title && (
            <span className="truncate text-[11.5px] font-medium text-zinc-600">{title}</span>
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
          <button
            type="button"
            data-testid="diagram-fullscreen"
            onClick={toggleFullscreen}
            aria-pressed={immersive}
            title={
              immersive
                ? `Keluar layar penuh (Esc)${fs.notice ? " · " + fs.notice : ""}`
                : "Layar penuh (Esc untuk keluar)"
            }
            className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] font-medium transition ${
              immersive
                ? "border-zinc-800 bg-zinc-900 text-white"
                : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            {immersive ? (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
              </svg>
            )}
            {immersive ? "Keluar" : "Layar penuh"}
          </button>
        </div>
      </div>

      {immersive && (
        <p className="border-b border-zinc-100 bg-zinc-50 px-3 py-1 font-mono text-[10.5px] text-zinc-400">
          {fs.mode === "native"
            ? "fullscreen native · Esc keluar"
            : `focus mode (fallback) · ${fs.notice || "Esc keluar"}`}
        </p>
      )}

      {!hydrated ? (
        <div className="grid flex-1 place-items-center text-sm text-zinc-400">
          memuat diagram…
        </div>
      ) : mode === "graph" && graphOk ? (
        <GraphView model={model} fill={immersive} fitSignal={fitSignal} height={immersive ? "100%" : 440} />
      ) : mode === "graph" && !graphOk ? (
        <div className="flex-1 overflow-auto p-4">
          <p className="mb-2 text-sm text-zinc-500">
            Sumber tidak mengandung node yang bisa dirender sebagai graph.
          </p>
          <pre className="overflow-x-auto rounded-xl border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs leading-5 text-zinc-700">
            {source}
          </pre>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto p-3">
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
