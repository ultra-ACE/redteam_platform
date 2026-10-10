from typing import Any

from pydantic import BaseModel, Field

from .enums import (
    JudgeType,
    ModelAdapter,
    ModelUsageScope,
    ReportFormat,
    ReviewDecision,
)


class SystemConfigUpdate(BaseModel):
    config_value: Any


class RiskMapping(BaseModel):
    raw_label: str
    risk_category_id: int
    mapping_type: str = "alias"
    confidence: float = Field(default=1.0, ge=0, le=1)
    mapping_note: str | None = None


class RiskMappingBatchRequest(BaseModel):
    mappings: list[RiskMapping]


class RiskMappingBatchResult(BaseModel):
    created_count: int = 0
    updated_count: int = 0
    remaining_unresolved_count: int = 0


class RiskMappingItem(BaseModel):
    raw_label: str
    count: int = 0
    mapped_category_id: int | None = None
    mapped_category_code: str | None = None
    mapped_category_name: str | None = None
    status: str = "unmapped"


class RiskMappingStatus(BaseModel):
    benchmark_version_id: int
    total_labels: int = 0
    mapped_labels: int = 0
    mapping_rate: float = 0.0
    unresolved_labels: list[str] = Field(default_factory=list)
    items: list[RiskMappingItem] = Field(default_factory=list)


class TestCaseUpdateRequest(BaseModel):
    prompt: str | None = None
    system_prompt: str | None = None
    language: str | None = None
    risk_category_ids: list[int] | None = None
    status: str | None = None


class ModelCreateRequest(BaseModel):
    name: str
    provider: str
    adapter_type: ModelAdapter
    base_url: str
    model_name: str
    secret_ref: str | None = None
    default_params: dict[str, Any] = Field(default_factory=dict)
    usage_scope: ModelUsageScope
    enabled: bool = True


class AttackMethodCreateRequest(BaseModel):
    code: str
    name: str
    category: str | None = None
    description: str | None = None
    risk_notes: str | None = None
    enabled: bool = True


class AttackMethodUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    risk_notes: str | None = None
    enabled: bool | None = None


class AttackTemplateCreateRequest(BaseModel):
    attack_method_id: int
    name: str
    template_text: str
    variables: list[str] = Field(default_factory=list)
    version: str = "v1"
    status: str = "active"


class AttackTemplateUpdateRequest(BaseModel):
    name: str | None = None
    template_text: str | None = None
    variables: list[str] | None = None
    status: str | None = None


class AttackTemplateVersionCreateRequest(BaseModel):
    version: str
    template_text: str | None = None
    variables: list[str] | None = None
    status: str = "draft"


class AttackTemplatePreviewRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class AttackTemplateValidationResult(BaseModel):
    valid: bool = False
    detected_variables: list[str] = Field(default_factory=list)
    missing_variables: list[str] = Field(default_factory=list)
    unused_variables: list[str] = Field(default_factory=list)
    undeclared_variables: list[str] = Field(default_factory=list)


class AttackTemplatePreviewResult(AttackTemplateValidationResult):
    rendered_prompt: str = ""


class RetryConfig(BaseModel):
    max_attempts: int = Field(default=2, ge=0)
    backoff_seconds: int = Field(default=3, ge=0)


class ExecutionConfig(BaseModel):
    repeat: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=120, ge=1)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    concurrency: int = Field(default=4, ge=1)


class ScoringWeights(BaseModel):
    harm_severity: float = Field(default=0.30, ge=0, le=1)
    attack_success: float = Field(default=0.25, ge=0, le=1)
    intent_compliance: float = Field(default=0.20, ge=0, le=1)
    rule_violation_severity: float = Field(default=0.15, ge=0, le=1)
    multi_run_consistency: float = Field(default=0.05, ge=0, le=1)
    cross_template_consistency: float = Field(default=0.05, ge=0, le=1)


class ScoringConfig(BaseModel):
    score_version: str = "risk-v1"
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


class ModelBinding(BaseModel):
    model_id: int
    role: str = "target"
    model_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class EvaluationTaskCreateRequest(BaseModel):
    name: str
    benchmark_version_id: int
    risk_taxonomy_id: int
    model_bindings: list[ModelBinding]
    attack_template_ids: list[int] = Field(default_factory=list)
    judge_profile_ids: list[int]
    rule_set_ids: list[int]
    execution: ExecutionConfig
    scoring: ScoringConfig
    priority: str = "normal"


class JudgeProfileCreateRequest(BaseModel):
    name: str
    judge_type: JudgeType
    judge_model_id: int | None = None
    strategy: str
    prompt_template: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class JudgeProfileUpdateRequest(BaseModel):
    name: str | None = None
    judge_type: JudgeType | None = None
    judge_model_id: int | None = None
    strategy: str | None = None
    prompt_template: str | None = None
    params: dict[str, Any] | None = None
    enabled: bool | None = None


class JudgeReEvaluateResult(BaseModel):
    judge_result_id: int
    status: str
    verdict: str | None = None
    trust_score: float | None = Field(default=None, ge=0, le=1)


class ManualReviewCreateRequest(BaseModel):
    task_attempt_id: int
    trigger_reason: str
    decision: ReviewDecision
    corrected_category_id: int | None = None
    corrected_score: float | None = Field(default=None, ge=0, le=100)
    comment: str | None = None


class ReportCreateRequest(BaseModel):
    task_id: int
    report_type: str
    format: ReportFormat
    template_version_id: int | None = None
    include: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)


class TaskActionData(BaseModel):
    task_id: int
    status: str
    cancel_requested: bool | None = None


class RetryFailedData(BaseModel):
    task_id: int
    retry_count: int
    status: str


class ReportTemplateCreateRequest(BaseModel):
    code: str
    name: str
    description: str | None = None


class ReportTemplateVersionCreateRequest(BaseModel):
    version: str
    format: ReportFormat
    content: str
    variables_schema: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"


class RiskTaxonomyCreateRequest(BaseModel):
    name: str
    version: str
    description: str | None = None
    is_default: bool = False


class RiskCategoryCreateRequest(BaseModel):
    code: str
    name: str
    parent_id: int | None = None
    definition: str | None = None
    severity_weight: int = Field(default=0, ge=0, le=100)
    examples: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class ManualReviewUpdateRequest(BaseModel):
    decision: ReviewDecision
    corrected_category_id: int | None = None
    corrected_score: float | None = Field(default=None, ge=0, le=100)
    comment: str | None = None
    status: str | None = None
