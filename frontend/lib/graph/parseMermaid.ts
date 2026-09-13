/* Parser Mermaid → GraphModel yang TOLERAN terhadap syntax error.

   Prinsip mode "graph interaktif": sumber Mermaid dari LLM sering rusak
   (kurung tidak seimbang, directive aneh, dsb.). Alih-alih gagal total seperti
   renderer Mermaid, parser ini:
     - memproses baris per baris; baris yang tidak dipahami dicatat ke
       `problems` dan DILEWATI (bukan dilempar sebagai exception),
     - node/edge yang sudah terbaca tetap dirender,
     - tidak pernah melempar exception: semua input menghasilkan GraphModel.

   Didukung: flowchart/graph (TD|TB|LR|RL|BT), bentuk node [] () {} (()) [[]]
   {{}} ([]), edge --> --- -.-> ==> dengan label `|teks|` / `-- teks -->`,
   rantai `A --> B --> C`, chaining `&`, subgraph ... end, komentar `%%`,
   pemisah `;`, serta mindmap berbasis indentasi. */

import {
  emptyModel,
  type EdgeKind,
  type GraphModel,
  type NodeShape,
} from "./types";

/** Buang komentar `%% ...` dengan kesadaran tanda kutip. */
function stripComments(line: string): string {
  let out = "";
  let quote: string | null = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quote) {
      out += ch;
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      out += ch;
      continue;
    }
    if (ch === "%" && line[i + 1] === "%") break;
    out += ch;
  }
  return out;
}

function unquote(s: string): string {
  const t = s.trim();
  if (t.length >= 2 && (t[0] === '"' || t[0] === "'") && t[t.length - 1] === t[0]) {
    return t.slice(1, -1);
  }
  return t;
}

/** Bersihkan label untuk tampilan HTML (tanpa markup Mermaid tersisa). */
function cleanLabel(raw: string): string {
  return unquote(raw)
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/#quot;/g, '"')
    .replace(/#\d+;/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const ID_CHARS = "[^\\s\\-\\-><=|&;{}()\\[\\]\"']+";

/** Token bentuk node: `id` atau `id[bentuk]` (berbagai bentuk Mermaid). */
const NODE_RE = new RegExp(
  "^(" +
    ID_CHARS +
    ")" +
    "(?:" +
    "\\(\\(([^)]*)\\)\\)" + // ((circle))
    "|\\[\\[([^\\]]*)\\]\\]" + // [[subroutine]]
    "|\\(\\[([^\\]]*)\\]\\)" + // ([stadium])
    "|\\{\\{([^}]*)\\}\\}" + // {{hex}}
    "|\\[([^\\]]*)\\]" + // [rect]
    "|\\(([^)]*)\\)" + // (round)
    "|\\{([^}]*)\\}" + // {diamond}
    "|>([^\\]]*)\\]" + // >flag]
    ")?",
);

const SHAPES: NodeShape[] = [
  "circle",
  "rect",
  "stadium",
  "hex",
  "rect",
  "round",
  "diamond",
  "flag",
];

interface LinkToken {
  kind: EdgeKind;
  label: string;
  length: number;
}

/** Cocokkan operator link di awal string: `-->`, `---`, `-.->`, `==>`,
    varian ber-label `-- teks -->`, `== teks ==>`, `-. teks .->`. */
function matchLink(s: string): LinkToken | null {
  const forms: Array<[RegExp, EdgeKind, number]> = [
    [/^--\s*([^-|>].*?)\s*-->/, "solid", 1],
    [/^==\s*([^=|>].*?)\s*==>/, "thick", 1],
    [/^-\.\s*([^>].*?)\s*\.->/, "dotted", 1],
    [/^-\.+->/, "dotted", 0],
    [/^-=+->/, "dotted", 0],
    [/^==+>/, "thick", 0],
    [/^--+>/, "solid", 0],
    [/^--+\s*[xo]/, "solid", 0],
    [/^--+\s*o(?![^-])/, "solid", 0],
    [/^-{3,}/, "plain", 0],
    [/^-{2,}/, "plain", 0],
  ];
  for (const [re, kind, labelGroup] of forms) {
    const m = re.exec(s);
    if (m) {
      return {
        kind,
        label: labelGroup ? cleanLabel(m[1] ?? "") : "",
        length: m[0].length,
      };
    }
  }
  return null;
}

interface Ctx {
  model: GraphModel;
  nodeIndex: Map<string, number>;
  groupStack: string[];
}

function ensureNode(ctx: Ctx, id: string, label?: string, shape?: NodeShape): string {
  const existing = ctx.nodeIndex.get(id);
  if (existing !== undefined) {
    const n = ctx.model.nodes[existing];
    if (label && n.label === n.id) n.label = label;
    if (shape && n.shape === "rect") n.shape = shape;
    if (n.group === null && ctx.groupStack.length) n.group = ctx.groupStack[ctx.groupStack.length - 1];
    return id;
  }
  ctx.model.nodes.push({
    id,
    label: label || id.replace(/[_-]+/g, " "),
    shape: shape || "rect",
    group: ctx.groupStack.length ? ctx.groupStack[ctx.groupStack.length - 1] : null,
  });
  ctx.nodeIndex.set(id, ctx.model.nodes.length - 1);
  return id;
}

function addEdge(ctx: Ctx, from: string, to: string, label: string, kind: EdgeKind): void {
  ctx.model.edges.push({
    id: `e${ctx.model.edges.length}`,
    from,
    to,
    label,
    kind,
  });
}

const IGNORED_RE =
  /^\s*(style|classDef|class|linkStyle|click|fill|stroke|width|height|accTitle|accDescr|themeCSS|fontFamily)\b/i;

/** Tutup paksa kurung yang terbuka di akhir pernyataan (toleransi terhadap
    Mermaid rusak: `A[label` diperlakukan seperti `A[label]`). */
function balanceBrackets(s: string): string {
  const pairs: Record<string, string> = { "[": "]", "(": ")", "{": "}" };
  const stack: string[] = [];
  let quote: string | null = null;
  for (const ch of s) {
    if (quote) {
      if (ch === quote) quote = null;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      continue;
    }
    if (ch === "[" || ch === "(" || ch === "{") stack.push(pairs[ch]);
    else if (ch === "]" || ch === ")" || ch === "}") {
      if (stack.length && stack[stack.length - 1] === ch) stack.pop();
    }
  }
  return s + stack.reverse().join("");
}

function parseStatement(ctx: Ctx, rawStmt: string): void {
  const stmt = rawStmt.trim();
  if (!stmt) return;

  // --- header arah -----------------------------------------------------
  const header = /^\s*(flowchart|graph)\s+(TD|TB|LR|RL|BT)?\s*$/i.exec(stmt);
  if (header) {
    ctx.model.kind = "flowchart";
    const dir = (header[2] || "TD").toUpperCase();
    ctx.model.direction = dir === "LR" || dir === "RL" ? "LR" : "TD";
    return;
  }
  if (/^\s*mindmap\s*$/i.test(stmt)) {
    ctx.model.kind = "mindmap";
    return;
  }
  if (/^\s*direction\s+(TD|TB|LR|RL|BT)/i.test(stmt)) {
    const d = stmt.trim().split(/\s+/)[1].toUpperCase();
    ctx.model.direction = d === "LR" || d === "RL" ? "LR" : "TD";
    return;
  }

  // --- subgraph / end ---------------------------------------------------
  const sub = /^\s*subgraph\s+(\S+?)\s*(?:\[(.*)\]|\((.*)\))?\s*$/i.exec(stmt);
  if (sub) {
    const id = sub[1];
    const label = cleanLabel(sub[2] ?? sub[3] ?? "") || id;
    ctx.model.groups.push({ id, label });
    ctx.groupStack.push(id);
    return;
  }
  if (/^\s*end\s*$/i.test(stmt)) {
    ctx.groupStack.pop();
    return;
  }

  if (IGNORED_RE.test(stmt)) return;

  // --- pernyataan node/edge ---------------------------------------------
  const balanced = balanceBrackets(stmt);
  const nodesBefore = ctx.model.nodes.length;
  const edgesBefore = ctx.model.edges.length;
  let pos = 0;
  let current: string[] = [];
  let pendingLink: LinkToken | null = null;
  let sawAmp = false;
  let invalid = false;
  let touched = false;

  const rest = (): string => balanced.slice(pos);

  while (pos < balanced.length) {
    const ws = /^\s+/.exec(rest());
    if (ws) {
      pos += ws[0].length;
      continue;
    }
    if (balanced[pos] === ";" || balanced[pos] === ",") {
      pos++;
      current = [];
      pendingLink = null;
      sawAmp = false;
      continue;
    }
    if (balanced[pos] === "&") {
      pos++;
      sawAmp = true;
      continue;
    }
    // label pipa setelah link: -->|teks|
    if (balanced[pos] === "|" && pendingLink) {
      const close = balanced.indexOf("|", pos + 1);
      if (close > pos) {
        pendingLink.label = cleanLabel(balanced.slice(pos + 1, close));
        pos = close + 1;
        continue;
      }
    }
    const link = matchLink(rest());
    if (link && current.length) {
      touched = true;
      pendingLink = link;
      pos += link.length;
      continue;
    }
    const node = NODE_RE.exec(rest());
    if (node && node[0].length > 0) {
      const id = node[1];
      let label: string | undefined;
      let shape: NodeShape | undefined;
      for (let g = 0; g < 8; g++) {
        if (node[g + 2] !== undefined) {
          label = cleanLabel(node[g + 2]);
          shape = SHAPES[g];
          break;
        }
      }
      // `id[label]` di posisi kanan link tetap node tujuan
      touched = true;
      ensureNode(ctx, id, label, shape);
      if (pendingLink) {
        for (const src of current) addEdge(ctx, src, id, pendingLink.label, pendingLink.kind);
        current = [id];
        pendingLink = null;
        sawAmp = false;
      } else if (current.length === 0 || sawAmp) {
        current.push(id);
        sawAmp = false;
      } else {
        // dua node beruntun tanpa operator/`;` = syntax error (prosa dsb.)
        invalid = true;
        current = [id];
      }
      pos += node[0].length;
      continue;
    }
    // karakter tidak dikenal → lewati satu karakter (toleran)
    pos++;
  }

  if (invalid) {
    // pernyataan rusak: buang hasil parsialnya, catat, lanjut baris berikut
    for (let i = ctx.model.nodes.length - 1; i >= nodesBefore; i--) {
      ctx.nodeIndex.delete(ctx.model.nodes[i].id);
    }
    ctx.model.nodes.length = nodesBefore;
    ctx.model.edges.length = edgesBefore;
    ctx.model.problems.push(stmt.slice(0, 80));
    return;
  }
  if (!touched) {
    ctx.model.problems.push(stmt.slice(0, 80));
  } else if (pendingLink) {
    ctx.model.problems.push(`edge tanpa tujuan: ${stmt.slice(0, 60)}`);
  }
}

/** Mindmap berbasis indentasi: setiap baris adalah node, parent = baris
    dengan indentasi lebih kecil terdekat. */
function parseMindmapBody(ctx: Ctx, lines: string[]): void {
  const stack: Array<{ indent: number; id: string }> = [];
  let counter = 0;
  for (const raw of lines) {
    if (!raw.trim()) continue;
    const indent = raw.match(/^\s*/)![0].length;
    const body = raw.trim();
    const m = NODE_RE.exec(body);
    const id = m && m[0].length ? m[1] : `mm${counter}`;
    let label: string | undefined;
    let shape: NodeShape | undefined;
    if (m) {
      for (let g = 0; g < 8; g++) {
        if (m[g + 2] !== undefined) {
          label = cleanLabel(m[g + 2]);
          shape = SHAPES[g];
          break;
        }
      }
    }
    if (!label) label = cleanLabel(body.replace(NODE_RE, "")) || cleanLabel(body) || id;
    ensureNode(ctx, id, label, shape || "round");
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop();
    if (stack.length) {
      addEdge(ctx, stack[stack.length - 1].id, id, "", "solid");
    }
    stack.push({ indent, id });
    counter++;
  }
}

/** Terjemahkan sumber Mermaid menjadi GraphModel. Tidak pernah melempar. */
export function parseMermaid(source: string): GraphModel {
  const ctx: Ctx = {
    model: emptyModel(),
    nodeIndex: new Map(),
    groupStack: [],
  };
  if (!source || typeof source !== "string") return ctx.model;

  let lines: string[];
  try {
    lines = source.replace(/\r\n?/g, "\n").split("\n").map(stripComments);
  } catch {
    return ctx.model;
  }

  const headerIdx = lines.findIndex((l) => /^\s*(flowchart|graph|mindmap)\b/i.test(l));
  if (headerIdx >= 0 && /^\s*mindmap\b/i.test(lines[headerIdx])) {
    ctx.model.kind = "mindmap";
    parseMindmapBody(ctx, lines.slice(headerIdx + 1));
    return finish(ctx);
  }

  if (headerIdx >= 0) {
    parseStatement(ctx, lines[headerIdx]);
    const body = lines.slice(headerIdx + 1);
    for (const line of body) {
      for (const stmt of line.split(";")) parseStatement(ctx, stmt);
    }
  } else {
    // tanpa header: coba perlakukan seluruh isi sebagai body flowchart
    for (const line of lines) {
      for (const stmt of line.split(";")) parseStatement(ctx, stmt);
    }
  }
  return finish(ctx);
}

function finish(ctx: Ctx): GraphModel {
  const { model } = ctx;
  // buang group kosong tanpa anggota
  const member = new Set(model.nodes.map((n) => n.group).filter(Boolean) as string[]);
  model.groups = model.groups.filter((g) => member.has(g.id));
  // node yang hanya disebut sebagai placeholder subgraph tidak ada; rapikan edge duplikat
  const seen = new Set<string>();
  model.edges = model.edges.filter((e) => {
    const key = `${e.from}>${e.to}|${e.label}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return model;
}

/** Ringkasan singkat untuk tooltip / log. */
export function graphSummary(model: GraphModel): string {
  return `${model.nodes.length} node · ${model.edges.length} edge${
    model.problems.length ? ` · ${model.problems.length} baris dilewati` : ""
  }`;
}
