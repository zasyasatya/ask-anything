"""create_diagram tool — deterministic Mermaid generation (flowchart & graph).

The tool exists so that a diagram never depends on the model getting Mermaid
syntax right: the model supplies *structure* (nodes/edges), the backend turns it
into valid Mermaid deterministically, and the UI renders that source as an
interactive graph.

Because real models are sloppy about tool arguments, the input is accepted in
the shapes seen in practice and normalised here instead of failing:

  * ``nodes``/``edges`` as a JSON string, a dict ``{id: label}``, a list of bare
    strings (``["Mulai", "Selesai"]``) or a list of objects with aliases
    (``from``/``source``/``to``/``target``, ``label``/``text``/``name``);
  * edges written as strings (``"A -> B"``, ``"A --> B: oke"``);
  * endpoints that were never declared as nodes — auto-created instead of
    dropping the edge (a dropped edge renders an incomplete, "sempit" diagram);
  * a ready-made Mermaid source in ``mermaid``/``code``/``source`` (some models
    write the diagram themselves) — sanitised and used as-is.
"""
from __future__ import annotations

import re
from typing import Any

from .args import as_int, as_list, as_mapping, as_str, first_key
from .base import Tool, ToolContext, ToolResult

_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

KINDS = ("flowchart", "graph", "mindmap")

#: Alias → canonical kind. Models happily answer `alur`, `flow`, `tree`, …
_KIND_ALIASES: dict[str, str] = {
    "flowchart": "flowchart", "flow": "flowchart", "flowcharttd": "flowchart",
    "process": "flowchart", "alur": "flowchart", "diagram": "flowchart",
    "sequence": "flowchart", "step": "flowchart",
    "graph": "graph", "network": "graph", "relation": "graph",
    "relations": "graph", "digraph": "graph", "dependency": "graph",
    "dependencies": "graph", "graf": "graph",
    "mindmap": "mindmap", "mind": "mindmap", "tree": "mindmap",
    "hierarchy": "mindmap",
}

#: Optional per-node shape → Mermaid syntax. Keeps the renderer's parser happy
#: (see frontend lib/graph/parseMermaid.ts) while still looking right in Mermaid.
_SHAPE_ALIASES: dict[str, str] = {
    "rect": "rect", "box": "rect", "rectangle": "rect", "square": "rect",
    "default": "rect", "process": "rect",
    "round": "round", "rounded": "round", "pill": "round",
    "stadium": "stadium",
    "diamond": "diamond", "decision": "diamond", "rhombus": "diamond",
    "condition": "diamond", "question": "diamond",
    "circle": "circle", "ellipse": "circle", "start": "circle", "end": "circle",
    "hex": "hex", "hexagon": "hex", "prepare": "hex",
    "flag": "flag", "note": "flag",
}

_DIRECTIONS = ("TD", "TB", "LR", "RL", "BT")

#: A source that already is a Mermaid document (the model wrote it itself).
_MERMAID_HEADER_RE = re.compile(
    r"^\s*(?:%%\{.*?\}%%\s*)?(flowchart|graph|mindmap|sequenceDiagram|"
    r"classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|"
    r"gitGraph|timeline|quadrantChart|xychart-beta)\b",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"```[A-Za-z]*\s*\n?(.*?)```", re.S)


def _esc(label: Any) -> str:
    """Label aman untuk node Mermaid berkutip."""
    text = str(label if label is not None else "")
    text = text.replace("\\", " ").replace('"', "'")
    for ch in ("|", "[", "]", "{", "}"):
        text = text.replace(ch, " ")
    # newline di dalam label Mermaid cukup dipertahankan sebagai spasi
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _norm_id(raw: Any, fallback: int) -> str:
    text = re.sub(r"[^A-Za-z0-9_]", "_", str(raw if raw is not None else "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if not _ID_RE.match(text or "") or text in ("end", "graph", "subgraph"):
        text = f"n{fallback}"
    return text


def _shape_of(raw: Any) -> str:
    key = re.sub(r"[^a-z]", "", as_str(raw).lower())
    return _SHAPE_ALIASES.get(key, "rect")


def _kind_of(raw: Any) -> str | None:
    key = re.sub(r"[^a-z]", "", as_str(raw).lower())
    return _KIND_ALIASES.get(key)


def _node_label(node: dict[str, Any], nid: str) -> str:
    label = first_key(node, ("label", "text", "name", "title", "caption", "value"))
    return _esc(label) if label is not None else _esc(nid)


#: Kunci pembungkus yang sering dikarang model: `{"nodes": [...]}`,
#: `{"links": [...]}`, `{"items": {...}}`.
_WRAPPER_KEYS = ("nodes", "items", "list", "data", "result", "results",
                 "vertices", "vertexes", "steps", "edges", "links",
                 "connections", "relations", "relation", "transitions", "lines")


def _unwrap(raw: Any) -> Any:
    """`{"nodes": [...]}` / `{"links": [...]}` → isinya (bukan node/edge palsu)."""
    wrapped = as_mapping(raw)
    if len(wrapped) == 1:
        key, value = next(iter(wrapped.items()))
        # nilai list tidak pernah menjadi isi mapping `id → label`, jadi aman
        # dibuka; nilai dict hanya dibuka bila namanya memang kunci pembungkus.
        if isinstance(value, list) or (
            isinstance(value, dict) and key.lower() in _WRAPPER_KEYS
        ):
            return value
    return raw


def normalize_nodes(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Accept every node shape models emit → ``[{"id", "label", "shape"}]``."""
    problems: list[str] = []
    nodes: list[dict[str, Any]] = []

    raw = _unwrap(raw)
    mapping = as_mapping(raw)
    if mapping:
        for key, value in mapping.items():
            if isinstance(value, dict):
                item = {**value, "id": value.get("id") or key}
                nodes.append(_node_from(item, len(nodes), problems))
            else:
                nodes.append(_node_from({"id": key, "label": value},
                                        len(nodes), problems))
        return nodes, problems

    for item in as_list(raw):
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            # "A: Label" / "A = Label"
            parts = re.split(r"\s*[:=]\s*", text, maxsplit=1)
            if len(parts) == 2:
                nodes.append(_node_from({"id": parts[0], "label": parts[1]},
                                        len(nodes), problems))
            else:
                nodes.append(_node_from({"id": text, "label": text},
                                        len(nodes), problems))
        elif isinstance(item, dict):
            nodes.append(_node_from(item, len(nodes), problems))
        else:
            problems.append(f"node #{len(nodes)} diabaikan (tipe {type(item).__name__})")
    return nodes, problems


def _node_from(item: dict[str, Any], index: int, problems: list[str]) -> dict[str, Any]:
    ident = first_key(item, ("id", "node", "key", "name", "label", "text"))
    label = _node_label(item, as_str(ident) or f"n{index + 1}")
    nid = _norm_id(ident if ident is not None else "", index + 1)
    return {
        "id": nid,
        "label": label or _esc(nid),
        "shape": _shape_of(first_key(item, ("shape", "type", "kind", "style"))),
        "group": as_str(first_key(item, ("group", "subgraph", "parent", "cluster"))),
    }


#: `A -> B` / `A --> B: label` / `A -->|label| B` / `A -- label --> B`
_ARROW = r"(?:-\.->|==>|-{1,3}>|-{2,3})"
_STRING_EDGE_FORMS: list[tuple[re.Pattern[str], str]] = [
    # A -->|label| B
    (re.compile(rf"^\s*(?P<src>[^\s|]+)\s*{_ARROW}\s*\|(?P<lbl>[^|]*)\|\s*"
                r"(?P<dst>[^\s|]+)\s*$"), "pipes"),
    # A -. label .-> B
    (re.compile(r"^\s*(?P<src>[^\s.]+?)\s*-\.\s*(?P<lbl>[^.|>]+?)\s*\.->\s*"
                r"(?P<dst>[^\s]+)\s*$"), "dots"),
    # A -- label --> B  (label tanpa titik, supaya `-.->` tidak salah baca)
    (re.compile(r"^\s*(?P<src>[^\s-]+)\s*-{1,3}\s*(?P<lbl>[^-|>.]+?)\s*-{1,3}>\s*"
                r"(?P<dst>[^\s]+)\s*$"), "dashes"),
    # A -> B / A -.-> B / A ==> B, dengan ": label" opsional
    (re.compile(rf"^\s*(?P<src>[^\s:]+?)\s*{_ARROW}\s*(?P<dst>[^\s:]+)\s*"
                r"(?::\s*(?P<lbl>.+))?$"), "colon"),
]


def _string_edge(text: str) -> dict[str, Any] | None:
    for pattern, _form in _STRING_EDGE_FORMS:
        m = pattern.match(text)
        if not m:
            continue
        groups = m.groupdict()
        src = (groups.get("src") or "").strip()
        dst = (groups.get("dst") or "").strip()
        label = (groups.get("lbl") or "").strip().strip(":")
        if not src or not dst or src == dst:
            continue
        return {"from": src, "to": dst, "label": label}
    return None


def _edge_from(item: Any, index: int, problems: list[str]) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        parsed = _string_edge(text)
        if parsed is None:
            problems.append(f"edge #{index} tidak terbaca: {text[:60]}")
        return parsed
    if isinstance(item, (list, tuple)):
        # `["A", "B"]` / `["A", "B", "label"]` — pasangan tanpa nama kunci
        if len(item) < 2:
            problems.append(f"edge #{index} diabaikan (pasangan tidak lengkap)")
            return None
        return {"from": item[0], "to": item[1],
                "label": item[2] if len(item) > 2 else ""}
    if not isinstance(item, dict):
        problems.append(f"edge #{index} diabaikan (tipe {type(item).__name__})")
        return None

    src = first_key(item, ("from", "source", "src", "start", "a", "parent",
                           "first", "node_from"))
    dst = first_key(item, ("to", "target", "dst", "end", "b", "child",
                           "second", "node_to"))
    if isinstance(src, dict):
        src = first_key(src, ("id", "node", "name", "label"))
    if isinstance(dst, dict):
        dst = first_key(dst, ("id", "node", "name", "label"))
    label = first_key(item, ("label", "text", "name", "title", "relation",
                             "description", "value"))
    kind = as_str(first_key(item, ("kind", "style", "type"))).lower()
    return {"from": src, "to": dst, "label": label, "edge_kind": kind}


def normalize_edges(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    problems: list[str] = []
    edges: list[dict[str, Any]] = []
    for i, item in enumerate(as_list(_unwrap(raw))):
        parsed = _edge_from(item, i, problems)
        if parsed is None:
            continue
        edges.append(parsed)
    return edges, problems


def _directive(edge_kind: str) -> str:
    """Edge style alias (``dotted``/``thick``) → Mermaid operator."""
    return {"dotted": "-.->", "dashed": "-.->", "thick": "==>", "bold": "==>",
            "plain": "---"}.get(edge_kind, "-->")


def sanitize_mermaid(raw: Any) -> str:
    """Extract a Mermaid document from model text (fences/prose stripped)."""
    text = as_str(raw)
    if not text:
        return ""
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if _MERMAID_HEADER_RE.match(line)), -1)
    if start < 0:
        return ""
    body = lines[start:]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(line.rstrip() for line in body)


def build_mermaid(kind: str, title: str, nodes: list[dict[str, Any]],
                  edges: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Return (mermaid_source, problems)."""
    problems: list[str] = []
    if not nodes:
        problems.append("diagram membutuhkan minimal 1 node")
        return "", problems

    ids: dict[str, str] = {}
    shapes: dict[str, str] = {}
    groups: dict[str, str] = {}
    for i, n in enumerate(nodes):
        base = n.get("id") or f"n{i + 1}"
        nid = str(base)
        if nid in ids:
            suffix = 2
            while f"{nid}_{suffix}" in ids:
                suffix += 1
            problems.append(f"node id '{nid}' ganda → dipakai '{nid}_{suffix}'")
            nid = f"{nid}_{suffix}"
        ids[nid] = _esc(n.get("label", nid)) or _esc(nid)
        shapes[nid] = _shape_of(n.get("shape"))
        group = as_str(n.get("group"))
        if group:
            groups.setdefault(group, _esc(group))

    kind = _kind_of(kind) or "flowchart"
    if kind == "mindmap":
        root = next(iter(ids))
        lines = ["mindmap", f"  root(({ids[root]}))"]
        for nid, label in list(ids.items())[1:]:
            lines.append(f"    {label}")
        return "\n".join(lines), problems

    header = "flowchart TD" if kind == "flowchart" else "flowchart LR"
    lines = [header]
    # Node dengan `group` dikelompokkan jadi subgraph (label = nama grup);
    # urutan deklarasi dipertahankan supaya hasilnya deterministik.
    open_group: str | None = None
    for n, nid in zip(nodes, ids.keys()):
        group = as_str(n.get("group")) or None
        if group != open_group:
            if open_group:
                lines.append("  end")
            if group:
                lines.append(f"  subgraph {groups.get(group, group)}")
        open_group = group
        lines.append(("    " if open_group else "  ")
                     + _node_line(nid, ids[nid], shapes[nid]))
    if open_group:
        lines.append("  end")

    known = set(ids)
    # `Node 1` vs `node1`: id yang hanya beda huruf besar/kecil dianggap sama.
    fold = {nid.casefold(): nid for nid in ids}
    for i, e in enumerate(edges):
        src = _norm_id(e.get("from", ""), i + 1)
        dst = _norm_id(e.get("to", ""), i + 1)
        if not as_str(e.get("from")) or not as_str(e.get("to")):
            problems.append(f"edge #{i}: endpoint kosong → dilewati")
            continue
        src = fold.get(src.casefold(), src)
        dst = fold.get(dst.casefold(), dst)
        for endpoint, original in ((src, e.get("from")), (dst, e.get("to"))):
            if endpoint not in known:
                # Endpoint yang belum dideklarasikan tetap dipakai: menyisakan
                # node/edge adalah diagram yang lebih baik daripada diagram
                # bolong-bolong karena satu node lupa ditulis.
                known.add(endpoint)
                ids[endpoint] = _esc(original) or _esc(endpoint)
                shapes[endpoint] = "rect"
                lines.append("  " + _node_line(endpoint, ids[endpoint], "rect"))
                problems.append(
                    f"node '{original}' tidak dideklarasikan → dibuat otomatis")
        lbl = _esc(e.get("label"))
        arrow = _directive(as_str(e.get("edge_kind")).lower())
        lines.append(f"  {src} {arrow}|{lbl}| {dst}" if lbl
                     else f"  {src} {arrow} {dst}")
    if title:
        # judul sebagai komentar Mermaid: tidak mengubah struktur, tetap terlihat
        lines.append(f"  %% judul: {_esc(title)}")
    return "\n".join(lines), problems


def _node_line(nid: str, label: str, shape: str) -> str:
    if shape == "round":
        return f'{nid}("{label}")'
    if shape == "stadium":
        return f'{nid}(["{label}"])'
    if shape == "circle":
        return f'{nid}(("{label}"))'
    if shape == "diamond":
        return f'{nid}{{"{label}"}}'
    if shape == "hex":
        return f'{nid}{{{{"{label}"}}}}'
    if shape == "flag":
        return f'{nid}>"{label}"]'
    return f'{nid}["{label}"]'


async def run_create_diagram(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    raw_args = dict(args or {})
    title = as_str(first_key(raw_args, ("title", "name", "caption")), "Diagram")

    # 1) Sumber Mermaid siap pakai (model menulis sintaksnya sendiri).
    inline = sanitize_mermaid(first_key(raw_args, ("mermaid", "code", "source",
                                                   "diagram", "definition")))
    nodes, problems = normalize_nodes(first_key(raw_args, ("nodes", "vertexes",
                                                           "vertices", "items",
                                                           "steps")))
    edges, edge_problems = normalize_edges(first_key(raw_args, ("edges", "links",
                                                                "relations",
                                                                "connections",
                                                                "transitions")))
    problems += edge_problems

    kind_raw = first_key(raw_args, ("kind", "type", "diagram_type", "graph_type"),
                        "flowchart")
    kind = _kind_of(kind_raw) or ""
    direction = as_str(first_key(raw_args, ("direction", "orient", "orientation"))).upper()
    if direction not in _DIRECTIONS:
        direction = ""
    if inline:
        if not kind:
            m = _MERMAID_HEADER_RE.match(inline)
            kind = _kind_of(m.group(1)) if m else "flowchart"
        if direction and re.match(r"^\s*flowchart\b", inline, re.IGNORECASE):
            head, _, rest = inline.partition("\n")
            if not re.search(r"\b(TD|TB|LR|RL|BT)\b", head, re.IGNORECASE):
                inline = f"flowchart {direction}\n{rest}" if rest else f"flowchart {direction}"
        return ToolResult(
            summary=f"create_diagram {kind or 'diagram'} '{title}' OK "
                    f"(sumber Mermaid dari model, {len(inline.splitlines())} baris)",
            data={"kind": kind or "flowchart", "title": title, "mermaid": inline,
                  "source": "model", "warnings": problems,
                  "node_count": None, "edge_count": None},
            hits=None,
        )

    if not nodes:
        return ToolResult(
            summary=("create_diagram gagal: tidak ada node yang terbaca "
                     "(nodes kosong atau argumen tidak terbaca)"),
            data={"error": problems or ["nodes kosong"],
                  "hint": ("Kirim `nodes` sebagai array objek "
                           "[{\"id\":\"a\",\"label\":\"Mulai\"}] atau tulis "
                           "`mermaid` berisi sumber Mermaid langsung.")},
            ok=False,
        )

    if not kind:
        kind = _kind_of(as_str(first_key(raw_args, ("kind", "type")))) or "flowchart"
    mermaid, build_problems = build_mermaid(kind, title, nodes, edges)
    problems += build_problems
    if direction and kind != "mindmap" and mermaid:
        # Arah eksplisit dari model (TD/LR/…) menang atas default kind.
        _, _, rest = mermaid.partition("\n")
        mermaid = (f"flowchart {direction}\n{rest}" if rest
                   else f"flowchart {direction}")
    if not mermaid:
        return ToolResult(summary=f"create_diagram gagal: {problems}",
                          data={"error": problems}, ok=False)

    declared = sum(1 for e in edges if as_str(e.get("from")) and as_str(e.get("to")))
    return ToolResult(
        summary=f"create_diagram {kind} '{title}' OK "
                f"({len(nodes)} node, {declared} edge)"
                + (f" · {len(problems)} catatan" if problems else ""),
        data={"kind": kind, "title": title, "mermaid": mermaid,
              "source": "structured",
              "node_count": len(nodes), "edge_count": declared,
              "warnings": problems},
        hits=None,
    )


CREATE_DIAGRAM = Tool(
    name="create_diagram",
    description=(
        "Generate a Mermaid diagram from structured nodes & edges. "
        "kind='flowchart' for diagram alir (top-down), kind='graph' for "
        "relation/network graph (left-right), kind='mindmap' for mind maps. "
        "The result is rendered automatically as a diagram card in the UI — "
        "there is no need to paste the Mermaid source into the answer. "
        "Nodes: [{id, label, shape?, group?}]. Edges: [{from, to, label?}]. "
        "Endpoints missing from `nodes` are created automatically, so declare "
        "at least the nodes you want labelled."
    ),
    source="diagram",
    parameters={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "title": {"type": "string"},
            "direction": {"type": "string", "enum": list(_DIRECTIONS)},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"},
                                   "label": {"type": "string"},
                                   "shape": {"type": "string",
                                             "enum": list(set(_SHAPE_ALIASES.values()))},
                                   "group": {"type": "string"}},
                    "required": ["id"],
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"from": {"type": "string"},
                                   "to": {"type": "string"},
                                   "label": {"type": "string"},
                                   "kind": {"type": "string",
                                            "enum": ["solid", "dotted", "thick",
                                                     "plain"]}},
                    "required": ["from", "to"],
                },
            },
            "mermaid": {
                "type": "string",
                "description": ("Opsional: sumber Mermaid jadi (bila Anda sudah "
                                "menulisnya sendiri) — dipakai apa adanya."),
            },
        },
        "required": ["kind"],
    },
    run=run_create_diagram,
)
