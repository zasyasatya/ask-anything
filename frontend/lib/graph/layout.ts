/* Layout layered (Sugiyama sederhana) yang DETERMINISTIK untuk GraphModel.

   Tahapan: (1) rank lewat longest-path dengan DFS yang memutus siklus,
   (2) pengurutan dalam rank lewat beberapa sweep barycenter,
   (3) penempatan koordinat dengan ukuran node hasil estimasi panjang label.

   Output: kotak node (posisi tengah + w/h) dalam koordinat "world" yang
   siap dirender komponen HTML interaktif (TD = atas→bawah, LR = kiri→kanan). */

import type { GraphModel } from "./types";

export interface LayoutNode {
  id: string;
  label: string;
  shape: string;
  group: string | null;
  /** posisi titik tengah dalam koordinat world */
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LayoutGroup {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LayoutResult {
  direction: "TD" | "LR";
  nodes: LayoutNode[];
  groups: LayoutGroup[];
  width: number;
  height: number;
}

const GAP_SAME = 44; // jarak antar node dalam satu rank
const GAP_RANK = 84; // jarak antar rank
const PAD = 40; // padding keliling konten

/** Perkiraan ukuran kotak node dari labelnya (multi-line didukung). */
export function nodeSize(label: string, shape: string): { w: number; h: number } {
  const lines = String(label || "").split("\n");
  const longest = lines.reduce((a, b) => (b.length > a.length ? b : a), "");
  let w = Math.max(92, Math.min(232, 34 + longest.length * 7.4));
  let h = 40 + 18 * (lines.length - 1);
  if (shape === "circle") {
    const d = Math.max(w, h + 24);
    w = Math.min(d, 170);
    h = Math.min(d, 170);
  } else if (shape === "diamond" || shape === "hex") {
    w += 34;
    h += 16;
  } else if (shape === "stadium") {
    h += 6;
  }
  return { w: Math.round(w), h: Math.round(h) };
}

function buildRanks(model: GraphModel): Map<string, number> {
  const ranks = new Map<string, number>();
  const out = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const n of model.nodes) {
    out.set(n.id, []);
    indeg.set(n.id, 0);
  }
  for (const e of model.edges) {
    if (!out.has(e.from) || !out.has(e.to) || e.from === e.to) continue;
    out.get(e.from)!.push(e.to);
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
  }

  // Kahn topological order; sisa siklus diputus sesuai urutan deklarasi
  const queue: string[] = model.nodes
    .filter((n) => (indeg.get(n.id) || 0) === 0)
    .map((n) => n.id);
  const order: string[] = [];
  const deg = new Map(indeg);
  while (queue.length) {
    const id = queue.shift()!;
    order.push(id);
    for (const dst of out.get(id) || []) {
      deg.set(dst, (deg.get(dst) || 0) - 1);
      if (deg.get(dst) === 0) queue.push(dst);
    }
  }
  for (const n of model.nodes) {
    if (!order.includes(n.id)) order.push(n.id); // anggota siklus
  }

  for (const id of order) {
    let r = ranks.get(id) ?? 0;
    for (const dst of out.get(id) || []) {
      const cur = ranks.get(dst) ?? 0;
      if (cur < r + 1) ranks.set(dst, r + 1);
    }
    if (!ranks.has(id)) ranks.set(id, r);
  }
  for (const n of model.nodes) if (!ranks.has(n.id)) ranks.set(n.id, 0);
  return ranks;
}

function orderRanks(
  model: GraphModel,
  ranks: Map<string, number>,
): string[][] {
  const maxRank = Math.max(0, ...model.nodes.map((n) => ranks.get(n.id) || 0));
  const layers: string[][] = Array.from({ length: maxRank + 1 }, () => []);
  for (const n of model.nodes) layers[ranks.get(n.id) || 0].push(n.id);

  const neigh = (id: string, toward: -1 | 1): number[] => {
    const pos = new Map<string, number>();
    const layer = layers[(ranks.get(id) || 0) + toward];
    if (!layer) return [];
    layer.forEach((lid, i) => pos.set(lid, i));
    const idx: number[] = [];
    for (const e of model.edges) {
      const other = toward === -1 ? e.from : e.to;
      const me = toward === -1 ? e.to : e.from;
      if (me === id && pos.has(other)) idx.push(pos.get(other)!);
    }
    return idx;
  };

  for (let sweep = 0; sweep < 4; sweep++) {
    const dir: -1 | 1 = sweep % 2 === 0 ? -1 : 1;
    const range =
      dir === -1
        ? Array.from({ length: maxRank }, (_, i) => i + 1)
        : Array.from({ length: maxRank }, (_, i) => maxRank - 1 - i);
    for (const r of range) {
      const bary = new Map<string, number>();
      for (const id of layers[r]) {
        const ns = neigh(id, dir);
        bary.set(id, ns.length ? ns.reduce((a, b) => a + b, 0) / ns.length : Infinity);
      }
      layers[r].sort((a, b) => {
        const da = bary.get(a)!;
        const db = bary.get(b)!;
        if (da === db) return a.localeCompare(b); // deterministik
        return da - db;
      });
    }
  }
  return layers;
}

export function layoutGraph(model: GraphModel): LayoutResult {
  const direction = model.direction === "LR" ? "LR" : "TD";
  if (!model.nodes.length) {
    return { direction, nodes: [], groups: [], width: 0, height: 0 };
  }

  const ranks = buildRanks(model);
  const layers = orderRanks(model, ranks);

  const sizes = new Map<string, { w: number; h: number }>();
  for (const n of model.nodes) sizes.set(n.id, nodeSize(n.label, n.shape));

  // koordinat: sumbu utama = rank, sumbu lintang = posisi dalam layer
  const placed = new Map<string, LayoutNode>();
  let crossCursor = 0; // posisi sepanjang sumbu lintang per layer
  const layerCross: number[] = [];

  for (let r = 0; r < layers.length; r++) {
    const ids = layers[r];
    const mainExtent = Math.max(
      ...ids.map((id) => (direction === "TD" ? sizes.get(id)!.h : sizes.get(id)!.w), 0),
    );
    let cursor = 0;
    const centers: number[] = [];
    for (const id of ids) {
      const s = sizes.get(id)!;
      const cross = direction === "TD" ? s.w : s.h;
      centers.push(cursor + cross / 2);
      cursor += cross + GAP_SAME;
    }
    const totalCross = Math.max(0, cursor - GAP_SAME);
    layerCross.push(totalCross);
    const maxCross = Math.max(...layerCross);
    const offset = (maxCross - totalCross) / 2; // semua layer center-aligned
    ids.forEach((id, i) => {
      const s = sizes.get(id)!;
      const crossCenter = offset + centers[i];
      const mainCenter = crossCursor + mainExtent / 2;
      placed.set(id, {
        id,
        label: model.nodes.find((n) => n.id === id)!.label,
        shape: model.nodes.find((n) => n.id === id)!.shape,
        group: model.nodes.find((n) => n.id === id)!.group,
        x: direction === "TD" ? crossCenter : mainCenter,
        y: direction === "TD" ? mainCenter : crossCenter,
        w: s.w,
        h: s.h,
      });
    });
    crossCursor += mainExtent + GAP_RANK;
  }

  const nodes = model.nodes.map((n) => placed.get(n.id)!);

  // bounding box grup (subgraph)
  const groups: LayoutGroup[] = [];
  for (const g of model.groups) {
    const members = nodes.filter((n) => n.group === g.id);
    if (!members.length) continue;
    const minX = Math.min(...members.map((n) => n.x - n.w / 2));
    const maxX = Math.max(...members.map((n) => n.x + n.w / 2));
    const minY = Math.min(...members.map((n) => n.y - n.h / 2));
    const maxY = Math.max(...members.map((n) => n.y + n.h / 2));
    groups.push({
      id: g.id,
      label: g.label,
      x: minX - 18,
      y: minY - 30,
      w: maxX - minX + 36,
      h: maxY - minY + 48,
    });
  }

  const minX = Math.min(...nodes.map((n) => n.x - n.w / 2), ...groups.map((g) => g.x));
  const minY = Math.min(...nodes.map((n) => n.y - n.h / 2), ...groups.map((g) => g.y));
  const maxX = Math.max(...nodes.map((n) => n.x + n.w / 2), ...groups.map((g) => g.x + g.w));
  const maxY = Math.max(...nodes.map((n) => n.y + n.h / 2), ...groups.map((g) => g.y + g.h));

  // normalisasi ke (PAD, PAD)
  for (const n of nodes) {
    n.x = Math.round(n.x - minX + PAD);
    n.y = Math.round(n.y - minY + PAD);
  }
  for (const g of groups) {
    g.x = Math.round(g.x - minX + PAD);
    g.y = Math.round(g.y - minY + PAD);
  }

  return {
    direction,
    nodes,
    groups,
    width: Math.round(maxX - minX + PAD * 2),
    height: Math.round(maxY - minY + PAD * 2),
  };
}
