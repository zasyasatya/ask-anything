import type {
  Conversation,
  DiagnosticReport,
  HFModelsResponse,
  HFSearchResponse,
  ProviderModels,
  SettingsInfo,
  TraceEvent,
} from "./types";

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function listConversations(): Promise<Conversation[]> {
  const d = await fetchJson<{ conversations: Conversation[] }>("/api/conversations");
  return d.conversations;
}

export async function loadConversation(id: string): Promise<{
  messages: Array<Record<string, unknown>>;
  trace: TraceEvent[];
}> {
  const d = await fetchJson<{
    messages: Array<Record<string, unknown>>;
    trace: TraceEvent[];
  }>(`/api/conversations/${id}`);
  return { messages: d.messages, trace: d.trace };
}

export async function getSettings(): Promise<SettingsInfo> {
  return fetchJson<SettingsInfo>("/api/settings");
}

export async function updateSettings(patch: Record<string, unknown>): Promise<SettingsInfo> {
  return fetchJson<SettingsInfo>("/api/settings", {
    method: "POST",
    body: JSON.stringify(patch),
  });
}

export async function health(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/health");
}

/** Models an OpenAI-compatible endpoint serves (dropdown in Settings). */
export async function listProviderModels(
  probe: { provider?: string; base_url?: string; api_key?: string } = {}
): Promise<ProviderModels> {
  return fetchJson<ProviderModels>("/api/models", {
    method: "POST",
    body: JSON.stringify(probe),
  });
}

/**
 * Uji endpoint sungguhan: GET /models + chat non-streaming (bentuk curl) +
 * chat streaming (yang dipakai app). Inilah jawaban "kenapa masih error?".
 */
export async function testProvider(
  probe: {
    provider?: string;
    base_url?: string;
    api_key?: string;
    model?: string;
  } = {}
): Promise<DiagnosticReport> {
  return fetchJson<DiagnosticReport>("/api/models/test", {
    method: "POST",
    body: JSON.stringify(probe),
  });
}

// ---------------------------------------------------------------------------
// Model offline: HuggingFace Hub → folder models/ → inference lokal
// ---------------------------------------------------------------------------
export async function searchHFModels(query: string): Promise<HFSearchResponse> {
  return fetchJson<HFSearchResponse>(
    `/api/hf/search?q=${encodeURIComponent(query)}`
  );
}

export async function listHFModels(): Promise<HFModelsResponse> {
  return fetchJson<HFModelsResponse>("/api/hf/models");
}

export async function listHFDownloads(): Promise<{
  downloads: HFModelsResponse["downloads"];
  models: HFModelsResponse["models"];
}> {
  return fetchJson<{
    downloads: HFModelsResponse["downloads"];
    models: HFModelsResponse["models"];
  }>("/api/hf/downloads");
}

export async function downloadHFModel(
  repoId: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/models/download", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId }),
  });
}

export async function cancelHFDownload(
  repoId: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/models/cancel", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId }),
  });
}

export async function deleteHFModel(
  repoId: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/models/delete", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId }),
  });
}

/** Pilih model offline yang aktif (dan muat ke memori secara default). */
export async function useHFModel(
  repoId: string,
  opts: { thinking?: boolean; load?: boolean } = {}
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/models/use", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, load: true, ...opts }),
  });
}

/** Muat model dari SEMANGKAH folder di disk (termasuk luar `models/`). */
export async function loadHFModelFromPath(
  path: string,
  opts: { repoId?: string; thinking?: boolean } = {}
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/models/load", {
    method: "POST",
    body: JSON.stringify({
      path,
      repo_id: opts.repoId || null,
      thinking: opts.thinking ?? null,
    }),
  });
}

export async function stopHFEngine(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/runtime/stop", {
    method: "POST",
  });
}

export async function hfEngineStatus(): Promise<HFModelsResponse["engine"]> {
  return fetchJson<HFModelsResponse["engine"]>("/api/hf/runtime");
}

/** Streams deep research on a topic; events deliver nodes incrementally. */
export async function streamDeepResearch(
  topic: string,
  onEvent: (ev: Record<string, unknown>) => void,
  opts: { maxQueries?: number; maxResultsPerQuery?: number } = {}
): Promise<void> {
  const res = await fetch("/api/deep-research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic,
      max_queries: opts.maxQueries || null,
      max_results_per_query: opts.maxResultsPerQuery || null,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`deep-research → HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore malformed */
          }
        }
      }
    }
  }
}

/** Streams one agentic turn; every interpreter event is delivered to onEvent. */
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (ev: TraceEvent) => void
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok || !res.body) throw new Error(`chat → HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore malformed */
          }
        }
      }
    }
  }
}
