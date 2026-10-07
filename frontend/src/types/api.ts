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
  status: string;
  created_at?: string;
};

export type BenchmarkVersion = {
  benchmark_version_id: number;
  benchmark_id: number;
  version: string;
  source_file_id?: number | null;
  case_count: number;
  checksum?: string | null;
  status: string;
  imported_at?: string | null;
};

export type BenchmarkImportError = {
  row_number: number;
  message: string;
};

export type BenchmarkImportResult = {
  benchmark_id: number;
  benchmark_version_id: number;
  imported_count: number;
  failed_count: number;
  unresolved_labels: string[];
  errors: BenchmarkImportError[];
};


export type TestCase = {
  test_case_id: number;
  benchmark_version_id: number;
  external_id: string;
  prompt: string;
  system_prompt?: string | null;
  language?: string | null;
  source_label?: string | null;
  risk_categories?: Array<{ code: string; name: string }>;
  status: string;
};

export type RetryFailedData = {
  task_id: number;
  retry_count: number;
  status: string;
};

export type EvaluationTask = {
  task_id: number;
  name: string;
  benchmark_version_id: number;
  risk_taxonomy_id: number;
  status: string;
  progress: number;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  cancel_requested: boolean;
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
  status: string;
  model_output_excerpt?: string | null;
  normalized_risk_categories?: Array<{ code: string; name: string }>;
  judge?: { verdict: string; confidence: number; trust_score: number } | null;
  rule_validation?: { hit_count: number; highest_severity?: string | null } | null;
  risk?: { overall_score: number; risk_level: string; confidence: number; needs_review: boolean } | null;
  manual_review_status: string;
};

export type Statistics = {
  task_id: number;
  total_results: number;
  safe_count: number;
  unsafe_count: number;
  uncertain_count: number;
  high_risk_count: number;
  critical_risk_count: number;
  attack_success_rate: number;
  average_risk_score: number;
  average_judge_confidence: number;
  judge_average_trust: number;
  manual_review_rate: number;
  rule_hit_rate: number;
  risk_level_distribution: Record<string, number>;
  risk_category_distribution: Array<{ code: string; count: number; average_score: number }>;
  model_breakdown: Array<Record<string, unknown>>;
  attack_template_breakdown: Array<Record<string, unknown>>;
  top_risky_cases: Array<Record<string, unknown>>;
};

export type Report = {
  report_id: number;
  task_id: number;
  template_version_id?: number | null;
  report_type: string;
  format: string;
  status: string;
  file_id?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
};

export type ReportTemplate = {
  template_id: number;
  code: string;
  name: string;
  description?: string | null;
  status: string;
  created_at?: string | null;
};

export type ReportTemplateVersion = {
  template_version_id: number;
  template_id: number;
  version: string;
  format: string;
  content: string;
  variables_schema?: Record<string, unknown> | null;
  status: string;
  created_at?: string | null;
};

export type SystemConfig = {
  config_key: string;
  config_value: unknown;
  description?: string | null;
  is_secret: boolean;
};

export type AuditLog = {
  audit_id: number;
  actor: string;
  action: string;
  resource_type: string;
  resource_id?: number | null;
  before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null;
  request_id?: string | null;
  ip?: string | null;
  created_at?: string | null;
};

export type AttackMethod = {
  attack_method_id: number;
  code: string;
  name: string;
  category?: string | null;
  description?: string | null;
  risk_notes?: string | null;
  enabled: boolean;
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
  attack_method_id: number;
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
  corrected_category_id?: number | null;
  original_score?: number | null;
  corrected_score?: number | null;
  comment?: string | null;
  reviewer?: string | null;
  reviewed_at?: string | null;
};

export type RiskMappingItem = {
  raw_label: string;
  count: number;
  mapped_category_id?: number | null;
  mapped_category_code?: string | null;
  mapped_category_name?: string | null;
  status: string;
};

export type RiskMappingStatus = {
  benchmark_version_id: number;
  total_labels: number;
  mapped_labels: number;
  mapping_rate: number;
  unresolved_labels: string[];
  items: RiskMappingItem[];
};

export type RiskCategory = {
  risk_category_id: number;
  taxonomy_id: number;
  parent_id?: number | null;
  code: string;
  name: string;
  definition?: string | null;
  severity_weight: number;
  children: RiskCategory[];
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
  original_risk_score?: number | null;
  original_risk_level?: string | null;
};


export type RiskTaxonomy = {
  risk_taxonomy_id: number;
  name: string;
  version: string;
  description?: string | null;
  is_default: boolean;
  status: string;
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
