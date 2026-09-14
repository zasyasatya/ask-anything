"""create_diagram tool — deterministic Mermaid generation (flowchart & graph)."""
from __future__ import annotations

import re
from typing import Any

from .base import Tool, ToolContext, ToolResult

_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

KINDS = ("flowchart", "graph", "mindmap")


def _esc(label: str, fallback: str = "") -> str:
    label = str(label)
    for ch in ('"', "|", "[", "]", "{", "}"):
        label = label.replace(ch, " ")
    return label.strip() or fallback


def _norm_id(raw: str, fallback: int) -> str:
    raw = re.sub(r"[^A-Za-z0-9_]", "_", str(raw).strip())
    if not _ID_RE.match(raw or ""):
        raw = f"n{fallback}"
    return raw


def build_mermaid(kind: str, title: str, nodes: list[dict[str, Any]],
                  edges: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Return (mermaid_source, problems)."""
    problems: list[str] = []
    if not nodes:
        problems.append("diagram membutuhkan minimal 1 node")
        return "", problems

    ids: dict[str, str] = {}
    for i, n in enumerate(nodes):
        nid = _norm_id(n.get("id", ""), i)
        if nid in ids:
            nid = f"{nid}_{i}"
        ids[nid] = _esc(n.get("label", nid), fallback="node")

    if kind == "mindmap":
        lines = ["mindmap", f"  root(({ids[next(iter(ids))]}))"]
        for nid, label in list(ids.items())[1:]:
            lines.append(f"    {label}")
        return "\n".join(lines), problems

    header = "flowchart TD" if kind == "flowchart" else "flowchart LR"
    lines = [header]
    for nid, label in ids.items():
        shape = f"{nid}[\"{label}\"]"
        lines.append(f"  {shape}")
    for i, e in enumerate(edges):
        src = _norm_id(e.get("from", ""), i)
        dst = _norm_id(e.get("to", ""), i)
        if src not in ids:
            problems.append(f"edge #{i}: node '{e.get('from')}' tidak dikenal")
            continue
        if dst not in ids:
            problems.append(f"edge #{i}: node '{e.get('to')}' tidak dikenal")
            continue
        lbl = _esc(e.get("label", ""))
        if lbl:
            lines.append(f"  {src} -->|{lbl}| {dst}")
        else:
            lines.append(f"  {src} --> {dst}")
    return "\n".join(lines), problems


async def run_create_diagram(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    kind = str(args.get("kind", "flowchart")).lower()
    if kind not in KINDS:
        kind = "flowchart"
    title = str(args.get("title", "Diagram"))
    mermaid, problems = build_mermaid(
        kind, title, args.get("nodes") or [], args.get("edges") or []
    )
    if not mermaid:
        return ToolResult(summary=f"create_diagram gagal: {problems}",
                          data={"error": problems}, ok=False)
    return ToolResult(
        summary=f"create_diagram {kind} '{title}' OK "
                f"({len(args.get('nodes') or [])} node, "
                f"{len(args.get('edges') or [])} edge)",
        data={"kind": kind, "title": title, "mermaid": mermaid,
              "warnings": problems},
        hits=None,
    )


CREATE_DIAGRAM = Tool(
    name="create_diagram",
    description=(
        "Generate a Mermaid diagram from structured nodes & edges. "
        "kind='flowchart' for diagram alir (top-down), kind='graph' for "
        "relation/network graph (left-right), kind='mindmap' for mind maps. "
        "The result is rendered automatically in the UI."
    ),
    source="diagram",
    parameters={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "title": {"type": "string"},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"},
                                   "label": {"type": "string"}},
                    "required": ["id", "label"],
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"from": {"type": "string"},
                                   "to": {"type": "string"},
                                   "label": {"type": "string"}},
                    "required": ["from", "to"],
                },
            },
        },
        "required": ["kind", "title", "nodes", "edges"],
    },
    run=run_create_diagram,
)
