// ── Overview ────────────────────────────────────────────────────────

export interface OverviewStats {
  total_mcps: number;
  total_agents: number;
  total_users: number;
  total_tool_calls_today: number;
  total_agent_interactions_today: number;
}

export interface TopItem {
  id: string;
  name: string;
  value: number;
}

export interface TrendPoint {
  date: string;
  submissions: number;
  users: number;
}

// ── OTel ────────────────────────────────────────────────────────────

export interface OtelStats {
  total_sessions: number;
  total_prompts: number;
  total_api_requests: number;
  total_tool_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_traces: number;
  total_spans: number;
}

export interface OtelTrace {
  trace_id: string;
  span_name: string;
  service_name?: string;
  duration_ns: number;
  status: string;
  session_id?: string;
  timestamp?: string;
}

export interface OtelSessionData {
  session_id: string;
  events: RawOtelEvent[];
  traces: unknown[];
  service_name: string;
}

export interface RawOtelEvent {
  timestamp: string;
  event_name: string;
  body?: string;
  attributes?: Record<string, string>;
  service_name?: string;
}

// ── Latency ─────────────────────────────────────────────────────────

export interface LatencyCell {
  name: string;
  hour: number;
  p50: number;
  p90: number;
  p99: number;
}

// ── Tokens ──────────────────────────────────────────────────────────

export interface TokenStats {
  total_input: number;
  total_output: number;
  total_tokens: number;
  avg_per_trace: number;
  by_agent: TokenUsageRow[];
  by_mcp: TokenUsageRow[];
  over_time: { date: string; input: number; output: number }[];
}

export interface TokenUsageRow {
  name: string;
  input: number;
  output: number;
  total: number;
  traces: number;
}

// ── Registry ────────────────────────────────────────────────────────

export interface RegistryItem {
  id: string;
  name: string;
  description?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

// ── Review ──────────────────────────────────────────────────────────

export interface ReviewItem {
  id: string;
  name?: string;
  type?: string;
  listing_type?: string;
  submitted_by?: string;
  submitted_at?: string;
  created_at?: string;
  status?: string;
}

// ── Scores ──────────────────────────────────────────────────────────

export interface Score {
  score_id: string;
  trace_id: string;
  span_id?: string;
  name: string;
  source: string;
  data_type: string;
  value?: number;
  string_value?: string;
  comment?: string;
  timestamp: string;
}

// ── Alerts ──────────────────────────────────────────────────────────

export interface AlertRule {
  id: string;
  name: string;
  metric: "error_rate" | "latency_p99" | "token_usage";
  threshold: number;
  condition: "above" | "below";
  target_type: "mcp" | "agent" | "all";
  target_id: string;
  webhook_url: string;
  status: "active" | "paused";
  last_triggered: string | null;
  created_at: string;
}

export interface AlertRuleCreate {
  name: string;
  metric: string;
  threshold: number;
  condition: string;
  target_type: string;
  target_id?: string;
  webhook_url?: string;
}

// ── Feedback ────────────────────────────────────────────────────────

export interface FeedbackItem {
  id: string;
  listing_id?: string;
  listing_name?: string;
  listing_type?: string;
  stars: number;
  comment?: string;
  user?: string;
  username?: string;
  created_at?: string;
}

// ── Eval ────────────────────────────────────────────────────────────

export interface Scorecard {
  id: string;
  agent_id?: string;
  agent_name?: string;
  version?: string;
  status?: string;
  overall_score?: number;
  created_at?: string;
  dimensions?: { name: string; score: number; comment?: string }[];
  metadata?: Record<string, unknown>;
}

// ── IDE Usage ───────────────────────────────────────────────────────

export interface IdeRow {
  ide: string;
  traces: number;
  avg_latency_ms: number;
  error_count: number;
  error_rate: number;
}

export interface IdeUsageData {
  ides: IdeRow[];
}

// ── Sandbox ─────────────────────────────────────────────────────────

export interface SandboxRun {
  span_id: string;
  name: string;
  exit_code: number | null;
  duration_ms: number | null;
  memory_mb: number | null;
  cpu_ms: number | null;
  oom: boolean;
  timestamp: string;
}

export interface SandboxData {
  total_runs: number;
  oom_count: number;
  oom_rate: number;
  timeout_count: number;
  timeout_rate: number;
  avg_exit_code: number | null;
  recent_runs: SandboxRun[];
  cpu_over_time: { date: string; avg_cpu: number }[];
  memory_over_time: { date: string; avg_memory: number }[];
}

// ── GraphRAG ────────────────────────────────────────────────────────

export interface GraphRagData {
  total_queries: number;
  avg_entities: number | null;
  avg_relationships: number | null;
  avg_relevance_score: number | null;
  avg_embedding_latency_ms: number | null;
  relevance_distribution: { bucket: string; count: number }[];
  recent_queries: { span_id: string; name: string; query_interface: string; entities: number | null; relationships: number | null; relevance_score: number | null; latency_ms: number | null; timestamp: string }[];
}

export interface RagasDimensionScore {
  avg: number | null;
  count: number;
}

export interface RagasScoresData {
  faithfulness: RagasDimensionScore;
  answer_relevancy: RagasDimensionScore;
  context_precision: RagasDimensionScore;
  context_recall: RagasDimensionScore;
}

// ── Admin ───────────────────────────────────────────────────────────

export interface AdminUser {
  id: string;
  username?: string;
  name?: string;
  email?: string;
  role: string;
  created_at?: string;
}

export interface AdminSetting {
  key: string;
  value: string;
}

// ── OTel Sessions ───────────────────────────────────────────────────

export interface OtelSession {
  session_id: string;
  first_event_time: string;
  last_event_time: string;
  prompt_count: number;
  api_request_count: number;
  tool_result_count: number;
  total_input_tokens: number;
  total_output_tokens: number;
  model: string;
  service_name: string;
}

// ── Telemetry ───────────────────────────────────────────────────────

export interface TelemetryStatus {
  clickhouse: boolean;
  traces_count: number;
  spans_count: number;
  scores_count: number;
}
