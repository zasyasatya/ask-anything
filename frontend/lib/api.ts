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
  if (!res.ok) {
    // Sertakan penjelasan server bila ada: "HTTP 500" saja menyembunyikan
    // sebabnya (mis. 415 format tak didukung, 503 OCR belum aktif, 401 token
    // admin salah) dan membuat pengguna menebak.
    let detail = "";
    try {
      const body = await res.text();
      const parsed = body ? (JSON.parse(body) as { detail?: unknown }) : null;
      const value = parsed?.detail;
      detail = typeof value === "string" ? value : body.slice(0, 300);
    } catch {
      /* body bukan JSON / tidak terbaca — cukup pakai status */
    }
    throw new Error(
      `${url} → HTTP ${res.status}${detail ? `: ${detail}` : ""}`
    );
  }
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
  onEvent: (ev: TraceEvent) => void,
  mode: string = "text"
): Promise<void> {
  await streamSSE(
    "/api/chat",
    { message, conversation_id: conversationId, mode },
    onEvent
  );
}

/** POST + baca stream SSE (`data: {json}` per event) — dipakai chat & RAG. */
export async function streamSSE(
  url: string,
  body: Record<string, unknown>,
  onEvent: (ev: TraceEvent) => void
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(`${url} → HTTP ${res.status}`);

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

/** Mode RAG: pertanyaan dijawab dari dokumen yang sudah di-upload. */
export async function streamRagQuery(
  question: string,
  conversationId: string | null,
  onEvent: (ev: TraceEvent) => void,
  documentIds?: string[]
): Promise<void> {
  await streamSSE(
    "/api/rag/query",
    {
      question,
      conversation_id: conversationId,
      document_ids: documentIds && documentIds.length ? documentIds : undefined,
    },
    onEvent
  );
}

// ---------------------------------------------------------------------------
// Pipeline governance: policy publik, feedback, RAG, dan API admin
// ---------------------------------------------------------------------------

import type {
  AdminOverview,
  ArtifactItem,
  FeedbackItem,
  FullPolicy,
  InstructionDashboard,
  MemoryItem,
  OcrStatus,
  Playbook,
  PlaybookInput,
  PolicyInfo,
  QuotaDashboard,
  QuotaLimits,
  RagDocument,
} from "./types";

/** Policy publik untuk gating UI (bukan lapisan keamanan). */
export async function getPolicy(): Promise<PolicyInfo> {
  return fetchJson<PolicyInfo>("/api/policy");
}

/** 👍/👎 dari ruang chat — terecord + bisa jadi pedoman perilaku otomatis. */
export async function sendFeedback(input: {
  rating: "up" | "down";
  conversation_id?: string;
  message_id?: string;
  comment?: string;
}): Promise<{ feedback: FeedbackItem; auto_guidance: boolean }> {
  return fetchJson("/api/feedback", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// --- RAG -------------------------------------------------------------------

export async function ragUploadPdf(
  file: File
): Promise<{ document: RagDocument }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/rag/upload", { method: "POST", body: fd });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json())?.detail || detail;
    } catch {
      /* keep status */
    }
    throw new Error(detail);
  }
  return (await res.json()) as { document: RagDocument };
}

export async function ragDocuments(): Promise<{ documents: RagDocument[] }> {
  return fetchJson("/api/rag/documents");
}

export async function ragDeleteDocument(id: string): Promise<{ ok: boolean }> {
  return fetchJson(`/api/rag/documents/${id}`, { method: "DELETE" });
}

// --- Admin (dilindungi ASK_ADMIN_TOKEN bila diset di backend) --------------

export function adminHeaders(token: string): Record<string, string> {
  return token ? { "X-Admin-Token": token } : {};
}

/** Token konsol admin disimpan di localStorage browser ini saja (tidak pernah
 *  dikirim ke mana pun selain header X-Admin-Token ke backend sendiri). */
export const ADMIN_TOKEN_KEY = "ask-admin-token";

export function readAdminToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(ADMIN_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function writeAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
    else window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    /* mode privat / storage penuh — abaikan */
  }
}

async function adminFetch<T>(
  token: string,
  url: string,
  init?: RequestInit
): Promise<T> {
  return fetchJson<T>(url, {
    ...init,
    headers: { ...adminHeaders(token), ...(init?.headers || {}) },
  });
}

export async function adminOverview(
  token: string
): Promise<AdminOverview> {
  return adminFetch(token, "/api/admin/overview");
}

export async function adminGetPolicy(token: string): Promise<FullPolicy> {
  return (await adminFetch<{ policy: FullPolicy }>(
    token,
    "/api/admin/policy"
  )).policy;
}

export async function adminUpdatePolicy(
  token: string,
  patch: Record<string, Record<string, unknown>>
): Promise<FullPolicy> {
  return (await adminFetch<{ policy: FullPolicy }>(token, "/api/admin/policy", {
    method: "PUT",
    body: JSON.stringify(patch),
  })).policy;
}

export async function adminMemories(token: string): Promise<MemoryItem[]> {
  return (await adminFetch<{ memories: MemoryItem[] }>(
    token,
    "/api/admin/memories"
  )).memories;
}

export async function adminCreateMemory(
  token: string,
  item: { scope: string; key: string; content: string; enabled: boolean }
): Promise<MemoryItem> {
  return adminFetch(token, "/api/admin/memories", {
    method: "POST",
    body: JSON.stringify(item),
  });
}

export async function adminUpdateMemory(
  token: string,
  id: string,
  patch: Partial<Pick<MemoryItem, "content" | "key" | "enabled" | "scope">>
): Promise<MemoryItem> {
  return adminFetch(token, `/api/admin/memories/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function adminDeleteMemory(
  token: string,
  id: string
): Promise<void> {
  await adminFetch(token, `/api/admin/memories/${id}`, { method: "DELETE" });
}

export async function adminArtifacts(
  token: string,
  kind?: string
): Promise<ArtifactItem[]> {
  const q = kind && kind !== "all" ? `&kind=${encodeURIComponent(kind)}` : "";
  return (await adminFetch<{ artifacts: ArtifactItem[] }>(
    token,
    `/api/admin/artifacts?limit=300${q}`
  )).artifacts;
}

export async function adminDeleteArtifact(
  token: string,
  id: string
): Promise<void> {
  await adminFetch(token, `/api/admin/artifacts/${id}`, { method: "DELETE" });
}

export async function adminFeedback(
  token: string
): Promise<{ feedback: FeedbackItem[]; stats: Record<string, unknown> }> {
  return adminFetch(token, "/api/admin/feedback?limit=300");
}

export async function adminSetFeedbackStatus(
  token: string,
  id: string,
  status: FeedbackItem["status"]
): Promise<FeedbackItem> {
  return adminFetch(token, `/api/admin/feedback/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function adminApplyFeedback(
  token: string,
  id: string
): Promise<{ feedback: FeedbackItem; memory: MemoryItem }> {
  return adminFetch(token, `/api/admin/feedback/${id}/apply`, {
    method: "POST",
  });
}

export async function adminDeleteFeedback(
  token: string,
  id: string
): Promise<void> {
  await adminFetch(token, `/api/admin/feedback/${id}`, { method: "DELETE" });
}

// --- Pipeline kuota token (monitoring + manage per end user) ----------------

export async function adminQuota(token: string): Promise<QuotaDashboard> {
  return adminFetch(token, "/api/admin/quota?limit=300");
}

export async function adminSetQuotaLimit(
  token: string,
  userKey: string,
  limits: {
    daily_tokens?: number | null;
    weekly_tokens?: number | null;
    daily_requests?: number | null;
    note?: string;
  }
): Promise<{ ok: boolean; limits: QuotaLimits }> {
  return adminFetch(token, `/api/admin/quota/users/${encodeURIComponent(userKey)}`, {
    method: "PUT",
    body: JSON.stringify(limits),
  });
}

export async function adminClearQuotaLimit(
  token: string,
  userKey: string
): Promise<{ ok: boolean }> {
  return adminFetch(token, `/api/admin/quota/users/${encodeURIComponent(userKey)}`, {
    method: "DELETE",
  });
}

export async function adminResetQuota(
  token: string,
  userKey: string,
  scope: "day" | "week" | "all" = "day"
): Promise<{ ok: boolean; removed_rows: number }> {
  return adminFetch(
    token,
    `/api/admin/quota/users/${encodeURIComponent(userKey)}/reset?scope=${scope}`,
    { method: "POST" }
  );
}

/** Sisa kuota pemanggil (dipakai indikator kuota di UI chat). */
export async function myQuota(): Promise<{
  user_key: string;
  enabled: boolean;
  limits: QuotaLimits;
  used: {
    day_tokens: number;
    day_requests: number;
    week_tokens: number;
    week_requests: number;
  };
  remaining: {
    day_tokens: number | null;
    week_tokens: number | null;
    day_requests: number | null;
  };
  period: {
    day_key: string;
    week_key: string;
    day_reset_at: number;
    week_reset_at: number;
  };
}> {
  return fetchJson("/api/quota/me");
}

// --- Pipeline instruksi advanced -------------------------------------------

export async function adminInstructions(
  token: string
): Promise<InstructionDashboard> {
  return adminFetch(token, "/api/admin/instructions");
}

export async function adminCreatePlaybook(
  token: string,
  item: PlaybookInput
): Promise<Playbook> {
  return adminFetch(token, "/api/admin/instructions", {
    method: "POST",
    body: JSON.stringify(item),
  });
}

export async function adminUpdatePlaybook(
  token: string,
  id: string,
  patch: Partial<PlaybookInput>
): Promise<Playbook> {
  return adminFetch(token, `/api/admin/instructions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function adminDeletePlaybook(
  token: string,
  id: string
): Promise<void> {
  await adminFetch(token, `/api/admin/instructions/${id}`, { method: "DELETE" });
}

/** Uji pemicu playbook TANPA memanggil model (kunci agar pipeline dikelola). */
export async function adminPreviewPlaybooks(
  token: string,
  body: { message: string; mode?: string; playbook_ids?: string[] }
): Promise<{ block: string; selected: Playbook[]; count: number }> {
  return adminFetch(token, "/api/admin/instructions/preview", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- Kesiapan OCR ----------------------------------------------------------

export async function ocrStatus(): Promise<OcrStatus> {
  return fetchJson("/api/rag/ocr");
}
