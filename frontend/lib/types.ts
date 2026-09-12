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
  hf_api_key_masked?: string;
  openai_api_key_masked?: string;
  thinking?: boolean;
  models_dir?: string;
  hf_port?: number;
  hf_ctx_size?: number;
  openai_base_url: string;
  openai_model: string;
  temperature: number;
  max_steps: number;
  logprobs: boolean;
  search_backend: string;
  has_openai_key: boolean;
  has_hf_key?: boolean;
  llm_reachable?: boolean;
}

export interface DownloadState {
  model_id: string;
  status: "idle" | "downloading" | "ready" | "error";
  downloaded: number;
  total: number;
  percent: number;
  speed_bps: number;
  error: string | null;
}

export interface LocalFileInfo {
  exists: boolean;
  path: string;
  size_bytes: number;
  downloaded_at: number | null;
}

export interface HFModel {
  id: string;
  name: string;
  repo_id: string;
  filename: string;
  quant: string;
  params: string;
  size_bytes: number;
  ram: string;
  thinking: boolean;
  tools: boolean;
  note: string;
  recommended: boolean;
  custom?: boolean;
  local: LocalFileInfo;
  download: DownloadState | null;
}

export interface LLMRuntimeInfo {
  binary: string | null;
  available: boolean;
  running: boolean;
  pid: number | null;
  model_path: string | null;
  port: number | null;
  base_url: string;
  started_at: number | null;
  error: string | null;
  install_hint: string | null;
}

export interface HFModelsResponse {
  models_dir: string;
  endpoint: string;
  models: HFModel[];
  runtime: LLMRuntimeInfo;
  active: {
    provider: string;
    hf_model: string;
    hf_base_url: string;
    thinking: boolean;
  };
}
