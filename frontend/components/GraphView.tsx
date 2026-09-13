"use client";
/* GraphView — renderer graph berbasis HTML/SVG yang interaktif.

   Berbeda dari renderer Mermaid (SVG statis yang gagal total bila sumber
   rusak), komponen ini menerjemahkan GraphModel menjadi elemen HTML asli:
   node = <button> (fokus keyboard, klik, drag), edge = path SVG. Interaksi:
   pan (drag latar), zoom (wheel/tombol), fit, drag node, klik node untuk
   menyorot relasi + panel inspektur, toggle arah layout TD/LR. */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as RPointerEvent,
} from "react";
import { layoutGraph, type LayoutResult } from "@/lib/graph/layout";
import type { GraphModel } from "@/lib/graph/types";

const MIN_K = 0.25;
const MAX_K = 2.5;

interface Transform {
  x: number;
  y: number;
  k: number;
}

function clamp(v: number, a: number, b: number): number {
  return Math.min(b, Math.max(a, v));
}

/** Titik potong garis pusat→pusat dengan tepi kotak node. */
function anchor(
  n: { x: number; y: number; w: number; h: number },
  tx: number,
  ty: number,
): { x: number; y: number } {
  const dx = tx - n.x;
  const dy = ty - n.y;
  if (dx === 0 && dy === 0) return { x: n.x, y: n.y };
  const sx = dx !== 0 ? n.w / 2 / Math.abs(dx) : Infinity;
  const sy = dy !== 0 ? n.h / 2 / Math.abs(dy) : Infinity;
  const t = Math.min(sx, sy);
  return { x: n.x + dx * t, y: n.y + dy * t };
}

export default function GraphView({
  model,
  height = 460,
  fill = false,
  fitSignal = 0,
  onNodeCount,
}: {
  model: GraphModel;
  /** tinggi kanvas: angka = px, string = CSS (mis. "100%"). */
  height?: number | string;
  /** isi tinggi container (dipakai saat fullscreen/focus mode). */
  fill?: boolean;
  /** naikkan angka ini untuk memaksa refit (mis. setelah masuk/keluar fullscreen). */
  fitSignal?: number;
  onNodeCount?: (n: number) => void;
}) {
  const [dirOverride, setDirOverride] = useState<"TD" | "LR" | null>(null);
  const [offsets, setOffsets] = useState<Record<string, { dx: number; dy: number }>>({});
  const [tf, setTf] = useState<Transform>({ x: 24, y: 16, k: 1 });
  const [selected, setSelected] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<
    | { mode: "pan"; startX: number; startY: number; ox: number; oy: number; moved: boolean }
    | { mode: "node"; id: string; startX: number; startY: number; ox: number; oy: number; moved: boolean }
    | null
  >(null);

  /** Angka fallback untuk perhitungan yang butuh px (prop `height` boleh CSS string). */
  const heightPx = typeof height === "number" ? height : 460;

  const directed = useMemo<GraphModel>(
    () => ({ ...model, direction: dirOverride ?? model.direction }),
    [model, dirOverride],
  );
  const layout: LayoutResult = useMemo(() => layoutGraph(directed), [directed]);

  useEffect(() => {
    onNodeCount?.(layout.nodes.length);
  }, [layout.nodes.length, onNodeCount]);

  // reset zoom & seleksi saat model/arah berubah
  useEffect(() => {
    setSelected(null);
    setOffsets({});
  }, [directed]);

  const posOf = useCallback(
    (id: string) => {
      const n = layout.nodes.find((x) => x.id === id);
      if (!n) return null;
      const o = offsets[id];
      return { ...n, x: n.x + (o?.dx || 0), y: n.y + (o?.dy || 0) };
    },
    [layout, offsets],
  );

  const fit = useCallback(() => {
    const el = containerRef.current;
    const cw = el?.clientWidth || 800;
    const ch = el?.clientHeight || heightPx;
    if (!layout.width || !layout.height) return;
    const k = clamp(Math.min(cw / layout.width, ch / layout.height) * 0.96, MIN_K, 1.4);
    setTf({
      k,
      x: (cw - layout.width * k) / 2,
      y: (ch - layout.height * k) / 2,
    });
  }, [layout, heightPx]);

  const didInit = useRef(false);
  useEffect(() => {
    fit();
    didInit.current = true;
  }, [fit]);

  // Refit saat ukuran container berubah (panel di-resize, navbar di-collapse,
  // masuk/keluar fullscreen) — tanpa ini kanvas tetap sekecil ukuran awal.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => fit());
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [fit]);

  useEffect(() => {
    if (fitSignal > 0) fit();
  }, [fitSignal, fit]);

  // zoom wheel (non-passive agar bisa preventDefault scroll halaman)
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      setTf((t) => {
        const k = clamp(t.k * Math.exp(-e.deltaY * 0.0016), MIN_K, MAX_K);
        const wx = (cx - t.x) / t.k;
        const wy = (cy - t.y) / t.k;
        return { k, x: cx - wx * k, y: cy - wy * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const zoomBy = (factor: number) => {
    const el = containerRef.current;
    const cw = el?.clientWidth || 800;
    const ch = el?.clientHeight || heightPx;
    setTf((t) => {
      const k = clamp(t.k * factor, MIN_K, MAX_K);
      const wx = (cw / 2 - t.x) / t.k;
      const wy = (ch / 2 - t.y) / t.k;
      return { k, x: cw / 2 - wx * k, y: ch / 2 - wy * k };
    });
  };

  // ------------------------------------------------------------- pointer
  const onCanvasPointerDown = (e: RPointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      /* lingkungan tanpa pointer aktif (mis. jsdom) */
    }
    dragRef.current = {
      mode: "pan",
      startX: e.clientX,
      startY: e.clientY,
      ox: tf.x,
      oy: tf.y,
      moved: false,
    };
  };

  const onNodePointerDown = (id: string) => (e: RPointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    e.stopPropagation();
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      /* lingkungan tanpa pointer aktif (mis. jsdom) */
    }
    const o = offsets[id] || { dx: 0, dy: 0 };
    dragRef.current = {
      mode: "node",
      id,
      startX: e.clientX,
      startY: e.clientY,
      ox: o.dx,
      oy: o.dy,
      moved: false,
    };
  };

  const onPointerMove = (e: RPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.startX;
    const dy = e.clientY - d.startY;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (d.mode === "pan") {
      setTf((t) => ({ ...t, x: d.ox + dx, y: d.oy + dy }));
    } else {
      setOffsets((o) => ({
        ...o,
        [d.id]: { dx: d.ox + dx / tf.k, dy: d.oy + dy / tf.k },
      }));
    }
  };

  const onPointerUp = (e: RPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d) return;
    if (d.mode === "pan" && !d.moved) setSelected(null); // klik latar = deselect
    if (d.mode === "node" && !d.moved) {
      setSelected((s) => (s === d.id ? null : d.id));
    }
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* sudah lepas */
    }
  };

  // ------------------------------------------------------------- derived
  const neighbors = useMemo(() => {
    const set = new Set<string>();
    if (!selected) return set;
    set.add(selected);
    for (const e of model.edges) {
      if (e.from === selected) set.add(e.to);
      if (e.to === selected) set.add(e.from);
    }
    return set;
  }, [selected, model.edges]);

  const selectedNode = selected ? layout.nodes.find((n) => n.id === selected) : null;
  const incoming = selected
    ? model.edges.filter((e) => e.to === selected)
    : [];
  const outgoing = selected
    ? model.edges.filter((e) => e.from === selected)
    : [];

  const nodeById = (id: string) => layout.nodes.find((n) => n.id === id);
  const labelOf = (id: string) => nodeById(id)?.label || id;

  return (
    <div
      ref={containerRef}
      data-testid="graph-canvas"
      role="group"
      aria-label="Graph interaktif: drag untuk geser, scroll untuk zoom, klik node untuk detail"
      className={`relative w-full touch-none select-none overflow-hidden bg-[radial-gradient(circle,#e4e4e7_1px,transparent_1px)] [background-size:18px_18px] ${fill ? "h-full min-h-0 flex-1" : "rounded-b-xl"}`}
      style={fill ? { cursor: "grab" } : { height, cursor: "grab" }}
      onPointerDown={onCanvasPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onDoubleClick={(e) => {
        if (e.target === e.currentTarget) fit();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") setSelected(null);
      }}
    >
      <div
        data-testid="graph-world"
        className="absolute left-0 top-0 origin-top-left"
        style={{ transform: `translate(${tf.x}px, ${tf.y}px) scale(${tf.k})` }}
      >
        {/* edge + group sebagai SVG di lapisan bawah */}
        <svg
          width={layout.width || 1}
          height={layout.height || 1}
          className="pointer-events-none absolute left-0 top-0 overflow-visible"
          aria-hidden="true"
        >
          <defs>
            <marker id="gv-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
              markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="#71717a" />
            </marker>
            <marker id="gv-arrow-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"
              markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--accent, #6366f1)" />
            </marker>
          </defs>
          {layout.groups.map((g) => (
            <g key={g.id}>
              <rect x={g.x} y={g.y} width={g.w} height={g.h} rx={14}
                fill="rgba(99,102,241,0.05)" stroke="rgba(99,102,241,0.35)"
                strokeDasharray="5 4" strokeWidth={1.2} />
              <text x={g.x + 10} y={g.y + 16} fontSize={11} fill="#6366f1"
                fontFamily="ui-monospace, monospace">
                {g.label}
              </text>
            </g>
          ))}
          {model.edges.map((e) => {
            const a = posOf(e.from);
            const b = posOf(e.to);
            if (!a || !b) return null;
            const p1 = anchor(a, b.x, b.y);
            const p2 = anchor(b, a.x, a.y);
            const hi = selected !== null && (e.from === selected || e.to === selected);
            const dim = selected !== null && !hi;
            const mx = (p1.x + p2.x) / 2;
            const my = (p1.y + p2.y) / 2;
            const vertical = layout.direction === "TD";
            const c1 = vertical ? { x: p1.x, y: p1.y + (p2.y - p1.y) / 2 } : { x: p1.x + (p2.x - p1.x) / 2, y: p1.y };
            const c2 = vertical ? { x: p2.x, y: p1.y + (p2.y - p1.y) / 2 } : { x: p1.x + (p2.x - p1.x) / 2, y: p2.y };
            return (
              <g key={e.id} opacity={dim ? 0.25 : 1}>
                <path
                  d={`M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}`}
                  fill="none"
                  stroke={hi ? "var(--accent, #6366f1)" : "#71717a"}
                  strokeWidth={e.kind === "thick" ? 2.6 : hi ? 2.2 : 1.5}
                  strokeDasharray={e.kind === "dotted" ? "5 4" : undefined}
                  markerEnd={e.kind === "plain" ? undefined : hi ? "url(#gv-arrow-hi)" : "url(#gv-arrow)"}
                />
                {e.label && (
                  <text x={mx} y={my - 5} fontSize={11.5} textAnchor="middle"
                    fill={hi ? "var(--accent, #6366f1)" : "#52525b"}
                    stroke="#ffffff" strokeWidth={4} paintOrder="stroke"
                    fontFamily="ui-sans-serif, system-ui">
                    {e.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* node sebagai elemen HTML asli: fokus, klik, drag */}
        {layout.nodes.map((n, i) => {
          const p = posOf(n.id)!;
          const isSel = selected === n.id;
          const dim = selected !== null && !neighbors.has(n.id);
          const shapeCls =
            n.shape === "circle" || n.shape === "stadium"
              ? "rounded-full"
              : n.shape === "round"
                ? "rounded-2xl"
                : "rounded-lg";
          return (
            <button
              key={n.id}
              type="button"
              data-testid={`graph-node-${n.id}`}
              data-node-id={n.id}
              aria-label={`Node ${i + 1} dari ${layout.nodes.length}: ${n.label}`}
              aria-pressed={isSel}
              onPointerDown={onNodePointerDown(n.id)}
              onClick={(e) => {
                // klik via keyboard (detail=0): Enter/Space memilih node
                if (e.detail === 0) setSelected((s) => (s === n.id ? null : n.id));
              }}
              className={`absolute flex items-center justify-center border px-3 text-center text-[12.5px] leading-4 shadow-sm outline-none transition-[opacity,box-shadow] focus-visible:ring-2 focus-visible:ring-accent ${shapeCls} ${
                isSel
                  ? "border-accent bg-accent-soft text-zinc-900 ring-2 ring-accent"
                  : neighbors.has(n.id) && selected
                    ? "border-accent bg-white text-zinc-800"
                    : "border-zinc-300 bg-white text-zinc-800 hover:border-zinc-400"
              } ${dim ? "opacity-35" : "opacity-100"}`}
              style={{
                left: p.x - n.w / 2,
                top: p.y - n.h / 2,
                width: n.w,
                height: n.h,
                cursor: "pointer",
                clipPath:
                  n.shape === "diamond"
                    ? "polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"
                    : n.shape === "hex"
                      ? "polygon(12% 0, 88% 0, 100% 50%, 88% 100%, 12% 100%, 0 50%)"
                      : undefined,
              }}
            >
              <span className="pointer-events-none line-clamp-3 break-words font-medium">
                {n.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* toolbar zoom */}
      <div className="absolute bottom-2 right-2 flex items-center gap-1 rounded-lg border border-zinc-200 bg-white/95 p-1 shadow-sm">
        <button type="button" aria-label="Perkecil" title="Perkecil"
          onClick={() => zoomBy(1 / 1.25)}
          className="grid h-7 w-7 place-items-center rounded-md text-zinc-600 hover:bg-zinc-100">
          −
        </button>
        <span className="w-11 text-center font-mono text-[11px] text-zinc-500">
          {Math.round(tf.k * 100)}%
        </span>
        <button type="button" aria-label="Perbesar" title="Perbesar"
          onClick={() => zoomBy(1.25)}
          className="grid h-7 w-7 place-items-center rounded-md text-zinc-600 hover:bg-zinc-100">
          +
        </button>
        <button type="button" aria-label="Pas ke layar" title="Pas ke layar (fit)"
          onClick={fit}
          className="grid h-7 w-7 place-items-center rounded-md text-zinc-600 hover:bg-zinc-100">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
          </svg>
        </button>
      </div>

      {/* toggle arah layout */}
      <div className="absolute right-2 top-2 flex overflow-hidden rounded-lg border border-zinc-200 bg-white/95 shadow-sm">
        {(["TD", "LR"] as const).map((d) => (
          <button
            key={d}
            type="button"
            title={d === "TD" ? "Atas → bawah" : "Kiri → kanan"}
            onClick={() => setDirOverride(d)}
            className={`px-2.5 py-1 font-mono text-[11px] ${
              (dirOverride ?? model.direction) === d
                ? "bg-zinc-800 text-white"
                : "text-zinc-500 hover:bg-zinc-100"
            }`}
          >
            {d === "TD" ? "↓ TD" : "→ LR"}
          </button>
        ))}
      </div>

      {/* panel inspektur node terpilih */}
      {selectedNode && (
        <div
          data-testid="graph-inspector"
          className="absolute left-2 top-2 w-60 rounded-xl border border-zinc-200 bg-white/95 p-3 shadow-card backdrop-blur"
        >
          <div className="mb-1 flex items-start justify-between gap-2">
            <span className="text-[13px] font-semibold leading-5 text-zinc-900">
              {selectedNode.label}
            </span>
            <button type="button" aria-label="Tutup detail"
              onClick={() => setSelected(null)}
              className="-m-1 rounded p-1 text-zinc-400 hover:bg-zinc-100">
              ✕
            </button>
          </div>
          <p className="mb-2 font-mono text-[10.5px] text-zinc-400">
            id: {selectedNode.id} · bentuk: {selectedNode.shape}
          </p>
          {incoming.length > 0 && (
            <p className="mb-1 text-[11px] text-zinc-500">
              Masuk dari:{" "}
              {incoming.map((e, i) => (
                <button key={i} type="button"
                  onClick={() => setSelected(e.from)}
                  className="mr-1 mb-0.5 rounded bg-zinc-100 px-1.5 py-0.5 text-[10.5px] text-zinc-700 hover:bg-zinc-200">
                  {labelOf(e.from)}
                  {e.label ? ` (${e.label})` : ""}
                </button>
              ))}
            </p>
          )}
          {outgoing.length > 0 && (
            <p className="text-[11px] text-zinc-500">
              Keluar ke:{" "}
              {outgoing.map((e, i) => (
                <button key={i} type="button"
                  onClick={() => setSelected(e.to)}
                  className="mr-1 mb-0.5 rounded bg-zinc-100 px-1.5 py-0.5 text-[10.5px] text-zinc-700 hover:bg-zinc-200">
                  {labelOf(e.to)}
                  {e.label ? ` (${e.label})` : ""}
                </button>
              ))}
            </p>
          )}
          {!incoming.length && !outgoing.length && (
            <p className="text-[11px] italic text-zinc-400">Node terpisah (tanpa edge).</p>
          )}
        </div>
      )}

      {!layout.nodes.length && (
        <div className="absolute inset-0 grid place-items-center text-sm text-zinc-400">
          Tidak ada node yang bisa dirender dari sumber ini.
        </div>
      )}
    </div>
  );
}
