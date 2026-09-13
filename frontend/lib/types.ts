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
  /** local = inference di proses backend · server = URL OpenAI-compatible */
  hf_mode: "local" | "server";
  hf_base_url: string;
  hf_model: string;
  hf_endpoint?: string;
  hf_device?: string;
  hf_dtype?: string;
  hf_api_key_masked?: string;
  hf_token_masked?: string;
  openai_api_key_masked?: string;
  thinking?: boolean;
  models_dir?: string;
  openai_base_url: string;
  openai_model: string;
  temperature: number;
  max_steps: number;
  logprobs: boolean;
  search_backend: string;
  has_openai_key: boolean;
  has_hf_key?: boolean;
  has_hf_token?: boolean;
  llm_reachable?: boolean;
}

export interface ProviderModel {
  id: string;
  label: string;
}

/** Answer of `POST /api/models` — model list of the probed endpoint. */
export interface ProviderModels {
  ok: boolean;
  provider?: string;
  base_url?: string | null;
  url?: string | null;
  status?: number | null;
  active_model?: string | null;
  models: ProviderModel[];
  count: number;
  error?: string | null;
  detail?: string;
}

/** Answer of `POST /api/models/test` — hasil diagnostik endpoint. */
export interface DiagnosticCheck {
  name: string;
  ok: boolean;
  status: number | null;
  latency_ms?: number;
  detail?: string;
  error?: string;
  hint?: string;
  models?: string[];
}

export interface DiagnosticReport {
  ok: boolean;
  provider?: string;
  base_url?: string | null;
  models_url?: string | null;
  chat_url?: string | null;
  checks: DiagnosticCheck[];
  hint?: string | null;
}

/** Progres unduhan satu repo HuggingFace (di-poll UI). */
export interface DownloadState {
  repo_id: string;
  status: "idle" | "downloading" | "ready" | "error";
  stage?: string;
  downloaded: number;
  total: number;
  percent: number;
  speed_bps: number;
  file?: string;
  file_index?: number;
  file_count?: number;
  error: string | null;
}

/** Satu hasil pencarian di HuggingFace Hub. */
export interface HFSearchHit {
  repo_id: string;
  label: string;
  params: number;
  size_bytes: number;
  downloads: number;
  likes: number;
  pipeline_tag: string;
  tags: string[];
  local: LocalModelInfo;
}

export interface LocalModelInfo {
  exists: boolean;
  ready: boolean;
  partial: boolean;
  path: string;
  size_bytes: number;
  downloaded_at: number | null;
  files: number;
}

/** Model yang sudah tersimpan di folder `models/` project. */
export interface HFModel {
  repo_id: string;
  label: string;
  params: number;
  size_bytes: number;
  files: number;
  downloaded_at: number | null;
  path: string;
  ready: boolean;
  partial: boolean;
  download: DownloadState | null;
}

export interface EngineDeps {
  available: boolean;
  torch: string | null;
  transformers: string | null;
  device: string | null;
  install_hint: string | null;
}

/** Status inference lokal (transformers) di proses backend. */
export interface EngineStatus {
  state: "idle" | "loading" | "ready" | "error";
  running: boolean;
  available: boolean;
  deps?: EngineDeps;
  model_path: string | null;
  repo_id: string | null;
  model_label: string | null;
  device: string | null;
  dtype: string | null;
  params: number | null;
  loaded_at: number | null;
  generating: boolean;
  error: string | null;
  hint: string | null;
  install_hint: string | null;
}

export interface HFModelsResponse {
  models_dir: string;
  endpoint: string;
  models: HFModel[];
  downloads: DownloadState[];
  engine: EngineStatus;
  deps: EngineDeps;
  active: {
    provider: string;
    hf_mode: string;
    hf_model: string;
    thinking: boolean;
  };
}

export interface HFSearchResponse {
  ok: boolean;
  query: string;
  models: HFSearchHit[];
  error: string | null;
}
