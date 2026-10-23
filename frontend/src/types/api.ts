export type ApiEnvelope<T> = {
  code: string;
  message: string;
  data: T;
  request_id: string;
  details?: Record<string, unknown>;
};

export type PaginatedData<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
};

export type HealthData = {
  status: string;
  database: string;
  redis: string;
  storage: string;
  version: string;
};

export type ModelRecord = {
  model_id: number;
  name: string;
  provider: string;
  adapter_type: string;
  base_url: string;
  model_name: string;
  secret_ref?: string | null;
  secret_configured?: boolean;
  usage_scope: string;
  enabled: boolean;
  created_at?: string;
};

export type Benchmark = {
  benchmark_id: number;
  name: string;
  slug: string;
  source_type: string;
  description?: string | null;
  source_file_id?: number | null;
  case_count: number;
  checksum?: string | null;
  imported_at?: string | null;
  status: string;
  created_at?: string;
};

export type BenchmarkImportError = {
  row_number: number;
  message: string;
};

export type BenchmarkImportResult = {
  benchmark_id: number;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  errors: BenchmarkImportError[];
  detected_adapter?: string | null;
  adapter_display_name?: string | null;
  adapter_confidence?: number | null;
  field_mapping?: Record<string, string>;
  dataset_type_counts?: Record<string, number>;
};

export type BenchmarkAdapter = {
  name: string;
  display_name: string;
  description: string;
};

export type DatasetType = 'benign' | 'harmful' | 'jailbreak';
export type SampleKind = 'seed' | 'template';

export type TestCase = {
  test_case_id: number;
  benchmark_id: number;
  external_id: string;
  prompt: string;
  system_prompt?: string | null;
  language?: string | null;
  source_label?: string | null;
  dataset_type: DatasetType;
  sample_kind?: SampleKind | null;
  status: string;
};

export type RetryFailedData = {
  task_id: number;
  retry_count: number;
  status: string;
};

export type EvaluationTaskModelBinding = {
  model_id: number;
  role?: 'target' | 'attacker';
  model_params?: Record<string, unknown>;
  enabled?: boolean;
};

export type EvaluationTaskRetryConfig = {
  max_attempts: number;
  backoff_seconds: number;
};

export type EvaluationTaskExecutionConfig = {
  repeat: number;
  timeout_seconds: number;
  retry: EvaluationTaskRetryConfig;
  concurrency: number;
};

export type AttackStrategyType = 'static' | 'transform' | 'iterative';
export type AttackStrategyCode = 'static' | 'puzzler' | 'pair';

export type EvaluationTaskAttackStrategy = {
  type: AttackStrategyType;
  code: AttackStrategyCode;
  config?: Record<string, unknown>;
  enabled?: boolean;
};

export type EvaluationTaskCreatePayload = {
  name: string;
  benchmark_id?: number | null;
  seed_test_case_ids?: number[];
  sample_size?: number;
  model_bindings: EvaluationTaskModelBinding[];
  attack_template_ids?: number[];
  judge_profile_ids: number[];
  rule_set_ids: number[];
  execution: EvaluationTaskExecutionConfig;
  priority?: string;
  attacker_model_id?: number;
  max_rounds?: number;
  attack_strategy?: EvaluationTaskAttackStrategy;
};

export type EvaluationTask = {
  task_id: number;
  name: string;
  benchmark_id?: number | null;
  status: string;
  progress: number;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  cancel_requested: boolean;
  pause_requested: boolean;
  last_heartbeat_at?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type TaskStatusData = {
  task_id: number;
  status: string;
  progress: number;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  running_cases: number;
  current_stage?: string | null;
  queue_position?: number | null;
  eta_seconds?: number | null;
  cancel_requested: boolean;
  pause_requested: boolean;
  last_heartbeat_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type EvaluationResult = {
  attempt_id: number;
  task_case_id?: number | null;
  test_case_id?: number | null;
  external_id?: string | null;
  model_id: number;
  attack_template_id?: number | null;
  dataset_type?: DatasetType | null;
  sample_kind?: SampleKind | null;
  attempt_no: number;
  round_no?: number | null;
  attack_strategy?: string | null;
  status: string;
  prompt_excerpt?: string | null;
  model_output_excerpt?: string | null;
  judge?: { verdict: string; confidence: number; trust_score: number } | null;
  rule_validation?: { hit_count: number; highest_severity?: string | null } | null;
  manual_review_status: string;
};

export type Statistics = {
  task_id: number;
  total_results: number;
  safe_count: number;
  unsafe_count: number;
  uncertain_count: number;
  attack_success_rate: number;
  average_judge_confidence: number;
  judge_average_trust: number;
  manual_review_rate: number;
  rule_hit_rate: number;
  judge_verdict_distribution: Record<string, number>;
  dataset_type_distribution: Record<string, number>;
  model_breakdown: Array<Record<string, unknown>>;
  attack_template_breakdown: Array<Record<string, unknown>>;
  top_unsafe_cases: Array<Record<string, unknown>>;
};

export type Report = {
  report_id: number;
  task_id: number;
  report_type: string;
  format: string;
  status: string;
  file_id?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
};

export type AttackMethod = {
  code: string;
  name: string;
  description?: string | null;
};

export type AttackTemplateValidationResult = {
  valid: boolean;
  detected_variables: string[];
  missing_variables: string[];
  unused_variables: string[];
  undeclared_variables: string[];
};

export type AttackTemplatePreviewResult = AttackTemplateValidationResult & {
  rendered_prompt: string;
};

export type AttackTemplate = {
  attack_template_id: number;
  library_name: string;
  method_code: string;
  name: string;
  template_text: string;
  variables: string[];
  version: string;
  status: string;
};

export type JudgeProfile = {
  judge_profile_id: number;
  name: string;
  judge_type: string;
  judge_model_id?: number | null;
  strategy: string;
  prompt_template?: string | null;
  params?: Record<string, unknown> | null;
  enabled: boolean;
};

export type JudgeTrustSummary = {
  task_id: number;
  average_trust_score: number;
  low_trust_count: number;
  rule_conflict_count: number;
  manual_review_count: number;
};

export type JudgeReEvaluateResult = {
  judge_result_id: number;
  status: string;
  verdict?: string | null;
  trust_score?: number | null;
};

export type ManualReview = {
  review_id: number;
  task_attempt_id: number;
  trigger_reason: string;
  status: string;
  decision?: string | null;
  corrected_verdict?: string | null;
  comment?: string | null;
  reviewer?: string | null;
  reviewed_at?: string | null;
};

export type ManualReviewDetail = ManualReview & {
  task_id?: number | null;
  test_case_id?: number | null;
  external_id?: string | null;
  prompt?: string | null;
  model_output?: string | null;
  judge_verdict?: string | null;
  judge_confidence?: number | null;
  judge_trust_score?: number | null;
  rule_hits: number;
  rule_highest_severity?: string | null;
};

export type StoredFile = {
  file_id: number;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  owner_type?: string | null;
  owner_id?: number | null;
  created_at?: string | null;
};

export type RuleValidationDetail = {
  rule_definition_id: number;
  rule_code?: string | null;
  passed: boolean;
  severity?: string | null;
  hit_count: number;
  matched_evidence?: unknown;
};

export type JudgeDetail = {
  judge_result_id: number;
  judge_profile_id: number;
  judge_profile_name?: string | null;
  judge_type?: string | null;
  strategy?: string | null;
  verdict?: string | null;
  confidence?: number | null;
  trust_score?: number | null;
  trust_breakdown?: Record<string, number> | null;
  reasoning?: string | null;
  evidence?: unknown;
  raw_output?: string | null;
};

export type AttemptDetail = {
  attempt_id: number;
  task_id?: number | null;
  task_case_id: number;
  test_case_id?: number | null;
  external_id?: string | null;
  model_id: number;
  model_name?: string | null;
  attack_template_id?: number | null;
  attack_template_name?: string | null;
  dataset_type?: DatasetType | null;
  sample_kind?: SampleKind | null;
  attempt_no: number;
  round_no?: number | null;
  attack_strategy?: string | null;
  attack_prompt?: string | null;
  status: string;
  prompt?: string | null;
  system_prompt?: string | null;
  rendered_prompt?: string | null;
  input_snapshot?: Record<string, unknown> | null;
  model_output?: string | null;
  latency_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  judge?: JudgeDetail | null;
  rule_validations: RuleValidationDetail[];
  manual_review?: ManualReview | null;
};
