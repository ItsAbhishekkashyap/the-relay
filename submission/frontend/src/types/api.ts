/**
 * TypeScript interfaces matching the exact FastAPI backend schemas.
 * Inspected from:
 * - app/api/schemas.py
 * - app/api/routes.py
 * - app/workflow/schemas.py
 */

export interface HealthResponse {
  status: string; // e.g. "ok"
  service: string; // e.g. "relay-research-assistant"
}

export interface ReadyComponents {
  retriever?: string; // "initialized" | "uninitialized"
  traffic_manager?: string; // "initialized" | "uninitialized"
  workflow?: string; // "initialized" | "uninitialized"
  [key: string]: string | undefined;
}

export interface ReadyResponse {
  status: string; // e.g. "ready"
  provider: string; // e.g. "simulator" | "groq"
  model: string; // e.g. "openai/gpt-oss-120b"
  components: ReadyComponents;
}

export interface ReadyErrorDetail {
  status: string; // "not_ready"
  components: ReadyComponents;
}

export interface Citation {
  raw_text: string;
  paper_title?: string | null;
  paper_id?: string | null;
  page_number?: number | null;
  section?: string | null;
  is_verified: boolean;
  verification_error?: string | null;
}

export interface RetrievedDocument {
  chunk_id: string;
  paper_id: string;
  paper_title: string;
  arxiv_id: string;
  paper_version: string;
  page_number?: number | null;
  page_numbers?: number[];
  section?: string | null;
  content: string;
  score: number;
  retrieval_channels: string[];
}

export interface AskRequest {
  question: string;
  paper_filter?: string | null;
}

export interface AskResponse {
  request_id: string;
  question: string;
  answer: string;
  status: 'verified' | 'refused' | 'unverified' | string;
  citations: Citation[];
  retrieved_passages: RetrievedDocument[];
  provider: string;
  refusal_reason?: string | null;
  correction_occurred: boolean;
  workflow_metadata: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  question: string;
  paperFilter?: string | null;
  submittedAt: Date;
  status: 'loading' | 'success' | 'error';
  response?: AskResponse;
  error?: string;
  durationMs?: number;
}

export interface LatencyStats {
  available: boolean;
  sample_count: number;
  measurement_scope: string;
  window?: string;
  p50_ms?: number | null;
  p95_ms?: number | null;
  p99_ms?: number | null;
  avg_ms?: number | null;
  min_ms?: number | null;
  max_ms?: number | null;
  reason?: string;
}

export interface RequestStats {
  total_submitted: number;
  successful: number;
  failed: number;
  rate_limited: number;
  timed_out: number;
  retried: number;
  queue_rejections: number;
  client_cancellations: number;
}

export interface QueueStats {
  current_depth: number;
  capacity: number;
  utilization_pct: number;
}

export interface ConcurrencyStats {
  active_in_flight: number;
  peak_in_flight: number;
  max_concurrency: number;
}

export interface RateLimitStats {
  rpm_limit?: number | null;
  tpm_limit?: number | null;
  completed_rpm: number;
  reserved_rpm: number;
  completed_tpm: number;
  reserved_tpm: number;
}

export interface MetricsResponse {
  timestamp: string;
  provider: {
    provider_name: string;
    model_name: string;
  };
  requests: RequestStats;
  queue: QueueStats;
  concurrency: ConcurrencyStats;
  rate_limits: RateLimitStats;
  latency: LatencyStats;
}

export interface SimulatorConfigData {
  base_delay_ms: number;
  jitter_ms: number;
  ttft_ms: number;
  ttft_stddev_ms: number;
  inter_chunk_delay_ms: number;
  num_stream_chunks: number;
  latency_distribution: 'lognormal' | 'normal' | 'uniform' | string;
  load_slowdown_factor: number;
  failure_rate: number;
  deterministic_failure: 'rate_limit' | 'server_error' | 'timeout' | 'auth_error' | 'overload' | null | string;
  rpm_limit: number;
  tpm_limit: number;
  daily_budget: number;
  daily_token_budget?: number | null;
  max_concurrent_requests: number;
  retry_after_seconds?: number | null;
  target_prompt_tokens?: number | null;
  target_completion_tokens?: number | null;
  model_name: string;
}

export interface SimulatorStatusResponse {
  status: string; // "healthy"
  in_flight_requests: number;
  config?: SimulatorConfigData;
  configured_limits: Record<string, unknown>;
  current_window: {
    rpm_usage: number;
    completed_rpm: number;
    reserved_rpm: number;
    tpm_usage: number;
    completed_tpm: number;
    reserved_tpm: number;
    window_seconds: number;
  };
  daily_request_usage: {
    date: string;
    requests_used: number;
    completed_requests: number;
    in_flight_requests: number;
    budget: number;
    remaining: number;
  };
  daily_token_usage: {
    date: string;
    tokens_used: number;
    completed_tokens: number;
    reserved_tokens: number;
    budget: number | null;
    remaining: number | null;
  };
  lifetime_metrics: {
    total_handled: number;
    successes: number;
    failures: number;
    rate_limit_hits: number;
    overload_hits: number;
    client_cancellations: number;
  };
}

export interface SimulatorConfigureResponse {
  status: string; // "updated"
  config: SimulatorConfigData;
}

export interface SimulatorResetResponse {
  status: string; // "reset_successful" | "config_reset"
  current_state?: SimulatorStatusResponse;
  config?: SimulatorConfigData;
}

export type NavigationTab = 'chat' | 'overview' | 'experiments' | 'settings';

export type ConnectionState = 'connected' | 'checking' | 'disconnected' | 'error';

// ============================================================================
// Stage 8E Experiment Analytics Schemas
// ============================================================================

export interface PercentileStats {
  count?: number;
  mean?: number;
  std?: number;
  min?: number;
  p50?: number;
  median?: number;
  p95?: number;
  p99?: number;
  max?: number;
}

export interface LoadScenarioStats {
  scenario_id: string;
  name: string;
  source: 'real' | 'simulator' | string;
  provider: string;
  description: string;
  traffic_pattern: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  status_breakdown: {
    ok: number;
    rate_limited_429: number;
    timeout_504: number;
    server_error_500: number;
  };
  success_rate_pct: number;
  rate_limited_pct: number;
  timeout_pct: number;
  error_pct: number;
  total_retries: number;
  avg_retries_per_request: number;
  total_latency_ms: PercentileStats;
  ttft_ms: PercentileStats;
  all_turnaround_ms?: PercentileStats;
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    tokens_per_answer: number;
  };
  estimated_cost_usd: number;
  cost_per_1000_answers_usd: number;
}

export interface CalibrationComparison {
  metric: string;
  real_groq_median_ms: number;
  simulator_median_ms: number;
  difference_ms: number;
  difference_pct: number;
  real_groq_ttft_median_ms: number;
  simulator_ttft_median_ms: number;
  ttft_difference_ms: number;
  ttft_difference_pct: number;
  conclusion: string;
}

export interface LoadExperimentsResponse {
  available: boolean;
  total_records?: number;
  scenarios?: LoadScenarioStats[];
  calibration_comparison?: CalibrationComparison | null;
  error?: string;
  file?: string;
}

export interface RetrievalConfigStats {
  config_id?: string;
  name?: string;
  config_name?: string;
  k?: number;
  top_k?: number;
  total_questions?: number;
  answerable_questions?: number;
  unanswerable_questions?: number;
  recall_at_1?: number;
  recall_at_3?: number;
  recall_at_5?: number;
  recall_at_8?: number;
  recall_at_10?: number;
  mrr?: number;
  correct_and_cited?: number;
  correct_and_cited_pct?: number;
  correct_and_cited_percentage?: number;
  correct_refusals?: number;
  wrong_answers?: number;
  wrong_pct?: number;
  wrong_answer_percentage?: number;
  unverified_answers?: number;
  retrieval_latency_mean_ms?: number;
  retrieval_latency_p95_ms?: number;
  avg_retrieval_latency_ms?: number;
  p95_retrieval_latency_ms?: number;
  avg_context_tokens?: number;
  cost_per_1000_answers_usd?: number;
  cost_per_1000_queries_usd?: number;
  [key: string]: unknown;
}

export interface RetrievalComparisonItem {
  configuration_name: string;
  k: number;
  stage6: {
    recall_at_5: number;
    mrr: number;
    correct_and_cited_pct: number;
    wrong_pct: number;
    latency_mean_ms: number;
    cost_per_1000_usd: number;
  };
  stage8b2: {
    recall_at_5: number;
    mrr: number;
    correct_and_cited_pct: number;
    wrong_pct: number;
    latency_mean_ms: number;
    cost_per_1000_usd: number;
  };
  delta: {
    recall_at_5_improvement: number;
    correct_and_cited_improvement_pct: number;
  };
}

export interface TopKScalingItem {
  k: number;
  recall: number;
  mrr: number;
  correct_and_cited_pct: number;
  wrong_pct: number;
  avg_context_tokens: number;
  cost_per_1000_usd: number;
}

export interface RetrievalExperimentsResponse {
  available: boolean;
  methodology_note?: string;
  denominators?: {
    total_questions: number;
    answerable_questions: number;
    unanswerable_questions: number;
    recall_and_mrr_basis: string;
    accuracy_and_refusal_basis: string;
  };
  stage6?: {
    stage_name: string;
    date: string;
    configurations: RetrievalConfigStats[];
  };
  stage8b2?: {
    stage_name: string;
    metadata?: Record<string, unknown>;
    configurations: RetrievalConfigStats[];
  };
  stage6_vs_stage8b2_comparison?: RetrievalComparisonItem[];
  top_k_scaling_stage8b2?: TopKScalingItem[];
  error?: string;
}

export interface ExperimentsOverviewResponse {
  status: string;
  description: string;
  pricing_basis: {
    prompt_tokens_per_million_usd: number;
    completion_tokens_per_million_usd: number;
  };
  datasets: {
    load_testing: {
      available: boolean;
      total_records: number;
      summary_available: boolean;
      scenarios: Array<{
        id: string;
        name: string;
        source: string;
        provider?: string;
        model?: string;
        total_requests: number;
      }>;
    };
    retrieval_benchmarks: {
      stage6: {
        stage: string;
        available: boolean;
        date: string;
        questions_count: number;
        answerable_count: number;
        unanswerable_count: number;
        configurations_count: number;
        configurations: string[];
      };
      stage8b2: {
        stage: string;
        available: boolean;
        date: string;
        questions_count: number;
        answerable_count: number;
        unanswerable_count: number;
        configurations_count: number;
        configurations: string[];
      };
    };
  };
}
