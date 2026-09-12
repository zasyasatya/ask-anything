export interface Conversation {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export interface ChatMessage {
  id?: string;
  role: "user" | "assistant" | "tool" | "assistant_toolcalls";
  content: string;
  meta?: Record<string, unknown>;
  ts?: number;
}

export interface TraceEvent {
  type: string;
  run_id?: string;
  seq?: number;
  ts?: number;
  [key: string]: unknown;
}

export interface SettingsInfo {
  provider: string;
  model: string;
  hf_base_url: string;
  hf_model: string;
  openai_base_url: string;
  openai_model: string;
  temperature: number;
  max_steps: number;
  logprobs: boolean;
  search_backend: string;
  has_openai_key: boolean;
  llm_reachable?: boolean;
}
