"use client";
/* Deep Research Canvas — Interactive information node explorer.
   
   When deep research mode is on, this canvas replaces the text answer.
   It displays information nodes from web research, grouped by:
   - Source domain
   - Year
   - Category
   
   Users can:
   - Filter by source, year, category
   - Click nodes to see detailed summaries
   - See connections between related nodes
   - Track research progress in real-time
   
   The mechanistic interpreter shows all browsing steps.
*/
import { useMemo, useState, useCallback } from "react";

// ─── Types ─────────────────────────────────────────────────────────────────

export interface ResearchNode {
  id: string;
  title: string;
  url: string;
  snippet: string;
  summary: string;
  domain: string;
  year: number | null;
  category: string;
  query: string;
  fetched: boolean;
  content_preview: string;
}

export interface ResearchGroup {
  by_source: Record<string, { domain: string; count: number; nodes: string[] }>;
  by_year: Record<string, { year: string; count: number; nodes: string[] }>;
  by_category: Record<string, { category: string; count: number; nodes: string[] }>;
}

export interface ResearchToolEvent {
  name: string;
  query?: string;
  url?: string;
  ok: boolean;
  hits?: number;
  error?: string;
  duration_ms: number;
}

export interface ResearchState {
  topic: string;
  nodes: ResearchNode[];
  groups: ResearchGroup | null;
  queries: string[];
  tool_events: ResearchToolEvent[];
  summary: string;
  total_nodes: number;
  total_sources: number;
  elapsed_ms: number;
}

export interface ResearchProgress {
  phase: string;
  query?: string;
  query_index?: number;
  total_queries?: number;
  queries_list?: string[];
}

// ─── Colors & Styles ───────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  "Research & Academic": "#8b5cf6",
  "News & Media": "#f59e0b",
  "Official & Government": "#10b981",
  "Technology": "#3b82f6",
  "Business & Industry": "#ef4444",
  "Tutorial & Guide": "#06b6d4",
  "Statistics & Data": "#84cc16",
  "Opinion & Analysis": "#ec4899",
  "General": "#6b7280",
};

function getCategoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] || CATEGORY_COLORS["General"];
}

// ─── Sub-Components ────────────────────────────────────────────────────────

function NodeCard({
  node,
  selected,
  onClick,
}: {
  node: ResearchNode;
  selected: boolean;
  onClick: () => void;
}) {
  const color = getCategoryColor(node.category);
  return (
    <button
      onClick={onClick}
      className={`group relative w-full text-left rounded-xl border-2 p-3 transition-all duration-200 hover:shadow-lg ${
        selected
          ? "border-accent bg-accent-soft shadow-md"
          : "border-zinc-200 bg-white hover:border-zinc-300"
      }`}
      style={{ borderLeftWidth: "4px", borderLeftColor: color }}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-semibold text-zinc-900 line-clamp-2 group-hover:text-accent">
            {node.title}
          </h4>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
            <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-zinc-600">
              {node.domain}
            </span>
            {node.year && (
              <span className="rounded bg-sky-50 px-1.5 py-0.5 font-mono text-sky-700">
                {node.year}
              </span>
            )}
            <span
              className="rounded px-1.5 py-0.5 font-mono text-white"
              style={{ backgroundColor: color }}
            >
              {node.category}
            </span>
            {node.fetched && (
              <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-emerald-700">
                ✓ dibaca
              </span>
            )}
          </div>
          <p className="mt-1.5 text-xs text-zinc-600 line-clamp-2">
            {node.snippet}
          </p>
        </div>
      </div>
    </button>
  );
}

function NodeDetail({ node, onClose }: { node: ResearchNode; onClose: () => void }) {
  const color = getCategoryColor(node.category);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl">
        <div
          className="border-b border-zinc-200 px-6 py-4"
          style={{ borderTopWidth: "4px", borderTopColor: color }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="text-lg font-bold text-zinc-900">{node.title}</h3>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-zinc-100 px-2 py-1 font-mono text-zinc-700">
                  {node.domain}
                </span>
                {node.year && (
                  <span className="rounded bg-sky-50 px-2 py-1 font-mono text-sky-700">
                    {node.year}
                  </span>
                )}
                <span
                  className="rounded px-2 py-1 font-mono text-white"
                  style={{ backgroundColor: color }}
                >
                  {node.category}
                </span>
                {node.fetched && (
                  <span className="rounded bg-emerald-50 px-2 py-1 font-mono text-emerald-700">
                    ✓ Konten dibaca penuh
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="shrink-0 rounded-lg p-1.5 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-600"
              aria-label="Tutup"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="max-h-[calc(80vh-140px)] overflow-y-auto px-6 py-4">
          <div className="space-y-4">
            <div>
              <h4 className="mb-2 text-sm font-semibold text-zinc-700">Ringkasan</h4>
              <p className="text-sm leading-relaxed text-zinc-800">{node.summary}</p>
            </div>

            {node.content_preview && (
              <div>
                <h4 className="mb-2 text-sm font-semibold text-zinc-700">
                  Preview Konten
                </h4>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-zinc-700">
                    {node.content_preview}
                  </p>
                </div>
              </div>
            )}

            <div>
              <h4 className="mb-2 text-sm font-semibold text-zinc-700">Metadata</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-2">
                  <span className="font-mono text-zinc-500">Query:</span>
                  <p className="mt-0.5 text-zinc-800">{node.query}</p>
                </div>
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-2">
                  <span className="font-mono text-zinc-500">URL:</span>
                  <a
                    href={node.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-0.5 block truncate text-accent hover:underline"
                  >
                    {node.url}
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3">
          <a
            href={node.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-accent bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/90"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <path d="M15 3h6v6" />
              <path d="M10 14L21 3" />
            </svg>
            Buka Sumber Asli
          </a>
        </div>
      </div>
    </div>
  );
}

function FilterPanel({
  groups,
  selectedSources,
  selectedYears,
  selectedCategories,
  onToggleSource,
  onToggleYear,
  onToggleCategory,
  onClearFilters,
}: {
  groups: ResearchGroup;
  selectedSources: Set<string>;
  selectedYears: Set<string>;
  selectedCategories: Set<string>;
  onToggleSource: (s: string) => void;
  onToggleYear: (y: string) => void;
  onToggleCategory: (c: string) => void;
  onClearFilters: () => void;
}) {
  const hasFilters = selectedSources.size + selectedYears.size + selectedCategories.size > 0;

  return (
    <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-900">Filter</h3>
        {hasFilters && (
          <button
            onClick={onClearFilters}
            className="text-xs font-medium text-accent hover:underline"
          >
            Reset semua
          </button>
        )}
      </div>

      {/* Sources */}
      <div>
        <h4 className="mb-2 text-xs font-medium text-zinc-700">
          Sumber ({Object.keys(groups.by_source).length})
        </h4>
        <div className="max-h-32 space-y-1 overflow-y-auto">
          {Object.entries(groups.by_source).map(([domain, info]) => (
            <label
              key={domain}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-zinc-50"
            >
              <input
                type="checkbox"
                checked={selectedSources.has(domain)}
                onChange={() => onToggleSource(domain)}
                className="rounded"
              />
              <span className="flex-1 truncate text-zinc-700">{domain}</span>
              <span className="font-mono text-zinc-500">{info.count}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Years */}
      <div>
        <h4 className="mb-2 text-xs font-medium text-zinc-700">
          Tahun ({Object.keys(groups.by_year).length})
        </h4>
        <div className="max-h-32 space-y-1 overflow-y-auto">
          {Object.entries(groups.by_year).map(([year, info]) => (
            <label
              key={year}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-zinc-50"
            >
              <input
                type="checkbox"
                checked={selectedYears.has(year)}
                onChange={() => onToggleYear(year)}
                className="rounded"
              />
              <span className="flex-1 text-zinc-700">{year}</span>
              <span className="font-mono text-zinc-500">{info.count}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Categories */}
      <div>
        <h4 className="mb-2 text-xs font-medium text-zinc-700">
          Kategori ({Object.keys(groups.by_category).length})
        </h4>
        <div className="max-h-40 space-y-1 overflow-y-auto">
          {Object.entries(groups.by_category).map(([cat, info]) => (
            <label
              key={cat}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-zinc-50"
            >
              <input
                type="checkbox"
                checked={selectedCategories.has(cat)}
                onChange={() => onToggleCategory(cat)}
                className="rounded"
              />
              <span
                className="h-3 w-3 rounded"
                style={{ backgroundColor: getCategoryColor(cat) }}
              />
              <span className="flex-1 text-zinc-700">{cat}</span>
              <span className="font-mono text-zinc-500">{info.count}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ progress }: { progress: ResearchProgress }) {
  const percent =
    progress.total_queries && progress.query_index != null
      ? Math.round(((progress.query_index + 1) / progress.total_queries) * 100)
      : 0;

  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50 p-4">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-sky-900">
          {progress.phase === "expanding"
            ? "Mempersiapkan query pencarian..."
            : progress.phase === "searching"
            ? `Mencari: ${progress.query}`
            : "Memproses hasil..."}
        </span>
        {percent > 0 && (
          <span className="font-mono text-xs text-sky-700">{percent}%</span>
        )}
      </div>
      {percent > 0 && (
        <div className="h-2 overflow-hidden rounded-full bg-sky-100">
          <div
            className="h-full bg-sky-500 transition-all duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
      {progress.queries_list && progress.queries_list.length > 0 && (
        <div className="mt-3 space-y-1">
          {progress.queries_list.map((q, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 text-xs ${
                progress.query_index != null && i === progress.query_index
                  ? "font-medium text-sky-900"
                  : progress.query_index != null && i < progress.query_index
                  ? "text-sky-600"
                  : "text-sky-400"
              }`}
            >
              <span>
                {progress.query_index != null && i < progress.query_index
                  ? "✓"
                  : progress.query_index != null && i === progress.query_index
                  ? "▸"
                  : "○"}
              </span>
              <span className="truncate">{q}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Canvas Component ─────────────────────────────────────────────────

export default function DeepResearchCanvas({
  state,
  progress,
  streaming,
}: {
  state: ResearchState | null;
  progress: ResearchProgress | null;
  streaming: boolean;
}) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"all" | "source" | "year" | "category">("all");
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [selectedYears, setSelectedYears] = useState<Set<string>>(new Set());
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());

  const toggleSource = useCallback((s: string) => {
    setSelectedSources((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  }, []);

  const toggleYear = useCallback((y: string) => {
    setSelectedYears((prev) => {
      const next = new Set(prev);
      if (next.has(y)) next.delete(y);
      else next.add(y);
      return next;
    });
  }, []);

  const toggleCategory = useCallback((c: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setSelectedSources(new Set());
    setSelectedYears(new Set());
    setSelectedCategories(new Set());
  }, []);

  // Filter nodes
  const filteredNodes = useMemo(() => {
    if (!state) return [];
    return state.nodes.filter((node) => {
      if (selectedSources.size > 0 && !selectedSources.has(node.domain)) return false;
      if (selectedYears.size > 0) {
        const yearKey = node.year ? String(node.year) : "Unknown";
        if (!selectedYears.has(yearKey)) return false;
      }
      if (selectedCategories.size > 0 && !selectedCategories.has(node.category)) return false;
      return true;
    });
  }, [state, selectedSources, selectedYears, selectedCategories]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !state) return null;
    return state.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, state]);

  // Group filtered nodes for display
  const groupedByView = useMemo(() => {
    if (viewMode === "all") return null;
    const groups: Record<string, ResearchNode[]> = {};
    for (const node of filteredNodes) {
      let key: string;
      if (viewMode === "source") key = node.domain;
      else if (viewMode === "year") key = node.year ? String(node.year) : "Unknown";
      else key = node.category;
      groups[key] = groups[key] || [];
      groups[key].push(node);
    }
    return groups;
  }, [filteredNodes, viewMode]);

  if (!state && !progress) {
    return null;
  }

  return (
    <div className="space-y-4">
      {/* Progress */}
      {streaming && progress && <ProgressBar progress={progress} />}

      {/* Summary */}
      {state && state.summary && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 text-2xl">📊</div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-emerald-900">
                Ringkasan Penelitian
              </h3>
              <p className="mt-1 text-sm text-emerald-800">{state.summary}</p>
              <div className="mt-3 flex flex-wrap gap-3 text-xs">
                <span className="rounded bg-white px-2 py-1 font-mono text-emerald-700">
                  {state.total_nodes} node
                </span>
                <span className="rounded bg-white px-2 py-1 font-mono text-emerald-700">
                  {state.total_sources} sumber
                </span>
                <span className="rounded bg-white px-2 py-1 font-mono text-emerald-700">
                  {state.queries.length} query
                </span>
                <span className="rounded bg-white px-2 py-1 font-mono text-emerald-700">
                  {Math.round(state.elapsed_ms / 1000)}s
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toolbar */}
      {state && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-zinc-200 bg-white p-1">
            {(["all", "source", "year", "category"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  viewMode === mode
                    ? "bg-accent text-white"
                    : "text-zinc-600 hover:bg-zinc-50"
                }`}
              >
                {mode === "all"
                  ? "Semua"
                  : mode === "source"
                  ? "Sumber"
                  : mode === "year"
                  ? "Tahun"
                  : "Kategori"}
              </button>
            ))}
          </div>
          <span className="text-xs text-zinc-500">
            {filteredNodes.length} dari {state.total_nodes} node
          </span>
        </div>
      )}

      {/* Main Layout */}
      {state && (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          {/* Filter Panel */}
          {state.groups && (
            <div className="lg:sticky lg:top-4 lg:self-start">
              <FilterPanel
                groups={state.groups}
                selectedSources={selectedSources}
                selectedYears={selectedYears}
                selectedCategories={selectedCategories}
                onToggleSource={toggleSource}
                onToggleYear={toggleYear}
                onToggleCategory={toggleCategory}
                onClearFilters={clearFilters}
              />
            </div>
          )}

          {/* Nodes Grid */}
          <div>
            {viewMode === "all" ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {filteredNodes.map((node) => (
                  <NodeCard
                    key={node.id}
                    node={node}
                    selected={selectedNodeId === node.id}
                    onClick={() => setSelectedNodeId(node.id)}
                  />
                ))}
              </div>
            ) : (
              groupedByView && (
                <div className="space-y-4">
                  {Object.entries(groupedByView).map(([groupKey, nodes]) => (
                    <div
                      key={groupKey}
                      className="rounded-xl border border-zinc-200 bg-white p-4"
                    >
                      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-900">
                        {viewMode === "category" && (
                          <span
                            className="h-3 w-3 rounded"
                            style={{ backgroundColor: getCategoryColor(groupKey) }}
                          />
                        )}
                        {groupKey}
                        <span className="ml-auto text-xs font-normal text-zinc-500">
                          {nodes.length} node
                        </span>
                      </h3>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {nodes.map((node) => (
                          <NodeCard
                            key={node.id}
                            node={node}
                            selected={selectedNodeId === node.id}
                            onClick={() => setSelectedNodeId(node.id)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )
            )}

            {filteredNodes.length === 0 && state.total_nodes > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
                <p className="text-sm text-amber-900">
                  Tidak ada node yang cocok dengan filter yang dipilih.
                </p>
                <button
                  onClick={clearFilters}
                  className="mt-2 text-xs font-medium text-accent hover:underline"
                >
                  Reset filter
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Node Detail Modal */}
      {selectedNode && (
        <NodeDetail node={selectedNode} onClose={() => setSelectedNodeId(null)} />
      )}
    </div>
  );
}
