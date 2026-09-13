/* Model graph netral-renderer: hasil terjemahan sumber Mermaid menjadi
   struktur node/edge yang bisa dirender sebagai komponen HTML interaktif.
   Dipisahkan dari parser & layout supaya mudah di-test dan dipakai ulang. */

export type NodeShape =
  | "rect"
  | "round"
  | "stadium"
  | "diamond"
  | "circle"
  | "hex"
  | "flag";

export interface GraphNode {
  id: string;
  label: string;
  shape: NodeShape;
  /** id subgraph tempat node berada (null = root). */
  group: string | null;
}

export type EdgeKind = "solid" | "dotted" | "thick" | "plain";

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  kind: EdgeKind;
}

export interface GraphGroup {
  id: string;
  label: string;
}

export interface GraphModel {
  /** Arah aliran utama hasil terjemahan header Mermaid. */
  direction: "TD" | "LR";
  kind: "flowchart" | "mindmap" | "unknown";
  nodes: GraphNode[];
  edges: GraphEdge[];
  groups: GraphGroup[];
  /** Baris yang tidak dipahami parser — dirender sebagai catatan, bukan error. */
  problems: string[];
}

export function emptyModel(): GraphModel {
  return { direction: "TD", kind: "unknown", nodes: [], edges: [], groups: [], problems: [] };
}
