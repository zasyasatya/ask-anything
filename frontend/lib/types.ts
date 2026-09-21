export interface Conversation {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  /** Pemilik sesi ('' bila percakapan lama / mode terbuka). */
  user_id?: string;
  owner_username?: string | null;
  owner_name?: string | null;
}

// ---------------------------------------------------------------------------
// Login & role (halaman /login; role: admin | member)
// ---------------------------------------------------------------------------

export type Role = "admin" | "member";

/** Izin efektif sebuah peran — dihitung backend, dipakai UI. */
export interface Capabilities {
  role: Role;
  is_admin: boolean;
  dashboard: string;
  modes: Record<string, boolean>;
  tools: Record<string, boolean>;
  allow_offline_models: boolean;
  allow_provider_settings: boolean;
  allow_admin_console: boolean;
  allow_rag_upload: boolean;
  allow_task_write: boolean;
  tasks_scope: "assigned" | "all";
  chat_provider: string;
}

export interface AuthUser {
  id: string;
  username: string;
  name: string;
  role: Role;
  role_label?: string;
  active: boolean;
  must_change_password?: boolean;
  created_at?: number;
  last_login?: number;
  capabilities: Capabilities;
}

export interface AuthBootstrap {
  users: number;
  seeded: boolean;
  auth_mode: string;
  demo: boolean;
  min_password: number;
  credentials?: Array<{ username: string; role: Role; password: string }>;
}

export interface AdminUser {
  id: string;
  username: string;
  name: string;
  role: Role;
  role_label?: string;
  active: boolean;
  must_change_password?: boolean;
  created_at?: number;
  last_login?: number;
  tasks_total?: number;
  tasks_done?: number;
  sessions?: number;
}

/** Policy satu peran (dipakai tab Pipeline → Akses per peran). */
export interface RolePolicy {
  modes: Record<string, boolean>;
  tools: Record<string, boolean>;
  allow_offline_models: boolean;
  allow_provider_settings: boolean;
  allow_admin_console: boolean;
  allow_rag_upload: boolean;
  allow_task_write: boolean;
  chat_provider: "openai" | "auto";
  tasks_scope: "assigned" | "all";
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
  /** ditambahkan backend: peran pemanggil & boleh-tidaknya mengubah setelan */
  role?: Role;
  can_manage?: boolean;
  capabilities?: Capabilities;
  auth_mode?: string;
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
  /** batas konteks model (token) — 0 = tak diketahui */
  max_position?: number | null;
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

// ---------------------------------------------------------------------------
// Pipeline governance (halaman Admin) + mode + RAG + feedback
// ---------------------------------------------------------------------------

export type PipelineMode =
  | "text"
  | "image"
  | "diagram"
  | "ppt"
  | "rag"
  | "research";

export interface PolicyInfo {
  modes: Record<PipelineMode, boolean>;
  tools: Record<string, boolean>;
  memory: { enabled: boolean; allow_ai_write: boolean };
  rag: { top_k: number; max_upload_mb: number };
  feedback: { enabled: boolean; auto_guidance: boolean; max_guidance: number };
  interpreter: {
    always_on: boolean;
    record_logprobs: boolean;
    record_tool_payloads: boolean;
  };
  labels?: Record<string, string>;
}

export type FullPolicy = {
  modes: Record<string, boolean>;
  tools: Record<string, boolean>;
  /** Izin per peran (admin | member) — diatur di tab Pipeline. */
  roles: Record<Role, RolePolicy>;
  memory: { enabled: boolean; allow_ai_write: boolean };
  rag: {
    chunk_size: number;
    chunk_overlap: number;
    top_k: number;
    max_upload_mb: number;
    // OCR (PDF hasil scan & gambar)
    ocr_enabled: boolean;
    ocr_engine: string;
    ocr_min_chars: number;
    ocr_dpi: number;
    ocr_max_pages: number;
    ocr_deskew: boolean;
    // Kecerdasan retrieval
    retrieval_mode: "hybrid" | "vector" | "lexical";
    retrieval_candidates: number;
    mmr_lambda: number;
    min_score: number;
    context_neighbors: number;
  };
  feedback: { enabled: boolean; auto_guidance: boolean; max_guidance: number };
  interpreter: {
    always_on: boolean;
    record_logprobs: boolean;
    record_tool_payloads: boolean;
  };
  artifacts: { max_artifacts: number; retention_days: number };
  quota: {
    enabled: boolean;
    daily_tokens: number;
    weekly_tokens: number;
    daily_requests: number;
    block_on_exceed: boolean;
  };
  instructions: {
    enabled: boolean;
    max_active: number;
    max_chars: number;
  };
};

// --- Pipeline kuota token ---------------------------------------------------

export interface QuotaLimits {
  daily_tokens: number;
  weekly_tokens: number;
  daily_requests: number;
  source: "policy" | "override" | string;
  note?: string;
}

export interface QuotaUserRow {
  user_key: string;
  first_seen: number;
  last_seen: number;
  day_tokens: number;
  day_requests: number;
  week_tokens: number;
  week_requests: number;
  total_tokens: number;
  total_requests: number;
  limits: QuotaLimits;
  remaining: { day_tokens: number | null; week_tokens: number | null };
  over_limit: boolean;
}

export interface QuotaOverview {
  policy: FullPolicy["quota"];
  users: number;
  overrides: number;
  totals: {
    runs: number;
    tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
  };
  today: { runs: number; tokens: number; day_key: string };
  this_week: { runs: number; tokens: number; week_key: string };
  by_provider: { provider: string; runs: number; tokens: number }[];
  by_mode: { mode: string; runs: number; tokens: number }[];
  blocked_today: number;
}

export interface QuotaRejection {
  id: string;
  user_key: string;
  mode: string;
  reason: string;
  day_key: string;
  ts: number;
}

export interface QuotaDashboard {
  overview: QuotaOverview;
  users: QuotaUserRow[];
  rejections: QuotaRejection[];
}

// --- Pipeline instruksi advanced -------------------------------------------

export interface AnswerTheory {
  key: string;
  label: string;
  domain_hint: string;
  method: string;
}

export interface Playbook {
  id: string;
  name: string;
  domain: string;
  persona: string;
  method: string;
  theory: string;
  rules: string;
  output_format: string;
  triggers: string[];
  modes: string[];
  activation: "always" | "keywords" | "manual";
  priority: number;
  enabled: boolean;
  created_at: number;
  updated_at: number;
  /** Hanya terisi pada hasil `/preview` & seleksi run: alasan playbook menyala. */
  match_reason?: string;
}

export interface PlaybookInput {
  name: string;
  domain?: string;
  persona?: string;
  method?: string;
  theory?: string;
  rules?: string;
  output_format?: string;
  triggers?: string[];
  modes?: string[];
  activation?: "always" | "keywords" | "manual";
  priority?: number;
  enabled?: boolean;
}

export interface InstructionStats {
  total: number;
  enabled: number;
  by_activation: Record<string, number>;
  activations_total: number;
  top_used: {
    playbook_id: string;
    playbook_name: string;
    runs: number;
    last_used: number;
  }[];
  never_used: {
    id: string;
    name: string;
    activation: string;
    triggers: string[];
  }[];
}

export interface InstructionActivation {
  id: string;
  playbook_id: string;
  playbook_name: string;
  conversation_id: string;
  run_id: string;
  mode: string;
  match_reason: string;
  ts: number;
}

export interface InstructionDashboard {
  playbooks: Playbook[];
  stats: InstructionStats;
  theories: AnswerTheory[];
  activations: InstructionActivation[];
  policy: FullPolicy["instructions"];
}

// --- Kesiapan OCR ----------------------------------------------------------

export interface OcrStatus {
  deps: {
    available: boolean;
    engines: string[];
    pdf_render: boolean;
    pillow: boolean;
    install_hint: string | null;
  };
  engine_selected: string | null;
  policy: Record<string, string | number | boolean>;
  accepts: string[];
}

export interface MemoryItem {
  id: string;
  scope: string;
  key: string;
  content: string;
  source: "admin" | "ai" | "feedback" | "user";
  enabled: boolean;
  created_at: number;
  updated_at: number;
}

export interface ArtifactItem {
  id: string;
  conversation_id: string;
  run_id: string;
  kind: "image" | "pptx" | "diagram" | "document" | "data" | string;
  title: string;
  filename: string;
  mime: string;
  size_bytes: number;
  meta: Record<string, unknown>;
  created_at: number;
  url: string;
}

export interface FeedbackItem {
  id: string;
  conversation_id: string;
  message_id: string;
  rating: "up" | "down";
  comment: string;
  context: {
    model?: string;
    provider?: string;
    mode?: string;
    answer_snippet?: string;
    tools_used?: string[];
  };
  status: "new" | "reviewed" | "applied" | "dismissed";
  guidance_memory_id: string;
  created_at: number;
}

export interface RagDocument {
  id: string;
  filename: string;
  title: string;
  size_bytes: number;
  pages: number;
  chunks: number;
  chars: number;
  status:
    | "uploaded"
    | "queued"
    | "parsing"
    | "ocr"
    | "chunking"
    | "embedding"
    | "ready"
    | "error";
  error: string;
  embed_backend: string;
  timings: Record<string, number>;
  kind?: "pdf" | "image" | string;
  ocr_pages?: number;
  ocr_engine?: string;
  ocr_confidence?: number;
  ocr_detail?: Record<string, unknown>;
  created_at: number;
  updated_at: number;
}

export interface AdminOverview {
  counts: {
    conversations: number;
    messages: number;
    trace_events: number;
    memories: number;
    artifacts: number;
    artifact_bytes: number;
    feedback_total: number;
    feedback_up: number;
    feedback_down: number;
    rag_documents: number;
    rag_documents_ready: number;
  };
  feedback: {
    total: number;
    up: number;
    down: number;
    ratio_up: number | null;
    by_status: Record<string, number>;
  };
  policy: FullPolicy;
  provider: string;
  model: string;
  admin_protected: boolean;
  quota?: QuotaOverview;
  instructions?: InstructionStats;
  auth?: {
    token_required: boolean;
    token_ok: boolean;
    auth_mode: string;
    login_required: boolean;
  };
  users?: { n: number } | null;
}
