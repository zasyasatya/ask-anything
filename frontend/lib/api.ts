import type {
  Conversation,
  HFModelsResponse,
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

/** Offline HuggingFace models: catalog + local files + llama.cpp runtime. */
export async function listHFModels(): Promise<HFModelsResponse> {
  return fetchJson<HFModelsResponse>("/api/hf/models");
}

export async function downloadHFModel(
  id: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/api/hf/models/${id}/download`, {
    method: "POST",
  });
}

export async function deleteHFModel(
  id: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/api/hf/models/${id}/delete`, {
    method: "POST",
  });
}

/** Select a downloaded GGUF as the active model (and optionally run it). */
export async function useHFModel(
  id: string,
  opts: { thinking?: boolean; run?: boolean; port?: number; ctx?: number } = {}
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/api/hf/models/${id}/use`, {
    method: "POST",
    body: JSON.stringify(opts),
  });
}

export async function stopHFRuntime(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/api/hf/runtime/stop", {
    method: "POST",
  });
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
