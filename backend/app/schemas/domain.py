from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field

from .common import ORMSchema

from .enums import (
    AttemptStatus,
    JudgeType,
    JudgeVerdict,
    ModelAdapter,
    ModelUsageScope,
    ReportFormat,
    ReportStatus,
    ReviewDecision,
    ReviewStatus,
    RiskLevel,
    TaskStatus,
)


class HealthData(ORMSchema):
    status: str = "healthy"
    database: str = "up"
    redis: str = "up"
    storage: str = "up"
    version: str = "1.0.0"


class SystemConfig(ORMSchema):
    config_key: str
    config_value: Any
    description: str | None = None
    is_secret: bool = False


class AuditLog(ORMSchema):
    audit_id: int = Field(validation_alias=AliasChoices("audit_id", "id"), serialization_alias="audit_id")
    actor: str
    action: str
    resource_type: str
    resource_id: int | None = None
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    request_id: str | None = None
    ip: str | None = None
    created_at: datetime | None = None


class Benchmark(ORMSchema):
    benchmark_id: int = Field(validation_alias=AliasChoices("benchmark_id", "id"), serialization_alias="benchmark_id")
    name: str
    slug: str
    source_type: str
    description: str | None = None
    status: str = "active"
    created_at: datetime | None = None


class BenchmarkVersion(ORMSchema):
    benchmark_version_id: int = Field(validation_alias=AliasChoices("benchmark_version_id", "id"), serialization_alias="benchmark_version_id")
    benchmark_id: int
    version: str
    source_file_id: int | None = None
    case_count: int = 0
    checksum: str | None = None
    status: str = "ready"
    imported_at: datetime | None = None


class RiskTaxonomy(ORMSchema):
    risk_taxonomy_id: int = Field(validation_alias=AliasChoices("risk_taxonomy_id", "id"), serialization_alias="risk_taxonomy_id")
    name: str
    version: str
    description: str | None = None
    is_default: bool = False
    status: str = "active"


class RiskCategory(ORMSchema):
    risk_category_id: int = Field(validation_alias=AliasChoices("risk_category_id", "id"), serialization_alias="risk_category_id")
    taxonomy_id: int
    parent_id: int | None = None
    code: str
    name: str
    definition: str | None = None
    severity_weight: int = Field(default=0, ge=0, le=100)
    children: list["RiskCategory"] = Field(default_factory=list)


class RiskCategoryRef(ORMSchema):
    code: str
    name: str


class BenchmarkImportError(ORMSchema):
    row_number: int
    message: str


class BenchmarkImportLabelMapping(ORMSchema):
    """导入报告中的单条风险标签归一结果。"""

    raw_label: str
    risk_category_id: int | None = None
    risk_category_code: str | None = None
    risk_category_name: str | None = None
    matched_by: str | None = None
    case_count: int = 0


class BenchmarkImportResult(ORMSchema):
    benchmark_id: int
    benchmark_version_id: int
    imported_count: int
    failed_count: int
    unresolved_labels: list[str] = Field(default_factory=list)
    errors: list[BenchmarkImportError] = Field(default_factory=list)
    # 异构适配结果：识别成哪个数据集结构、字段怎么映射的
    detected_adapter: str | None = None
    adapter_display_name: str | None = None
    adapter_confidence: float | None = None
    field_mapping: dict[str, str] = Field(default_factory=dict)
    # 统一风险分类结果：每个原始标签归到了哪个统一类别
    label_mappings: list[BenchmarkImportLabelMapping] = Field(default_factory=list)
    unlabeled_count: int = 0


class TestCase(ORMSchema):
    test_case_id: int = Field(validation_alias=AliasChoices("test_case_id", "id"), serialization_alias="test_case_id")
    benchmark_version_id: int
    external_id: str
    prompt: str
    system_prompt: str | None = None
    language: str | None = None
    source_label: str | None = None
    risk_categories: list[RiskCategoryRef] = Field(default_factory=list)
    status: str = "active"


class Model(ORMSchema):
    model_id: int = Field(validation_alias=AliasChoices("model_id", "id"), serialization_alias="model_id")
    name: str
    provider: str
    adapter_type: ModelAdapter
    base_url: str
    model_name: str
    secret_ref: str | None = None
    usage_scope: ModelUsageScope
    enabled: bool = True
    created_at: datetime | None = None


class HealthCheckData(ORMSchema):
    model_id: int
    status: str = "healthy"
    latency_ms: int | None = None
    error_message: str | None = None


class AttackMethod(ORMSchema):
    attack_method_id: int = Field(validation_alias=AliasChoices("attack_method_id", "id"), serialization_alias="attack_method_id")
    code: str
    name: str
    category: str | None = None
    description: str | None = None
    risk_notes: str | None = None
    enabled: bool = True


class AttackTemplate(ORMSchema):
    attack_template_id: int = Field(validation_alias=AliasChoices("attack_template_id", "id"), serialization_alias="attack_template_id")
    attack_method_id: int
    name: str
    template_text: str
    variables: list[str] = Field(default_factory=list)
    version: str = "v1"
    status: str = "active"


class JudgeProfile(ORMSchema):
    judge_profile_id: int = Field(validation_alias=AliasChoices("judge_profile_id", "id"), serialization_alias="judge_profile_id")
    name: str
    judge_type: JudgeType
    judge_model_id: int | None = None
    strategy: str
    prompt_template: str | None = None
    params: dict[str, Any] | None = None
    enabled: bool = True


class JudgeSummary(ORMSchema):
    verdict: JudgeVerdict
    confidence: float = Field(ge=0, le=1)
    trust_score: float = Field(ge=0, le=1)


class RuleValidationSummary(ORMSchema):
    hit_count: int = 0
    highest_severity: RiskLevel | None = None


class RiskSummary(ORMSchema):
    overall_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False


class RiskDimension(ORMSchema):
    dimension_code: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    source: str | None = None
    evidence: Any = None


class RiskAssessment(ORMSchema):
    attempt_id: int
    overall_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1)
    judge_trust_score: float = Field(ge=0, le=1)
    score_version: str
    dimensions: list[RiskDimension] = Field(default_factory=list)
    rule_override_applied: bool = False
    calculated_at: datetime | None = None


class EvaluationTask(ORMSchema):
    task_id: int = Field(validation_alias=AliasChoices("task_id", "id"), serialization_alias="task_id")
    name: str
    benchmark_version_id: int
    risk_taxonomy_id: int
    status: TaskStatus
    progress: float = Field(default=0, ge=0, le=1)
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    cancel_requested: bool = False
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskStatusData(ORMSchema):
    task_id: int
    status: TaskStatus
    progress: float = Field(default=0, ge=0, le=1)
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    running_cases: int = 0
    current_stage: str | None = None
    queue_position: int | None = None
    eta_seconds: int | None = None
    cancel_requested: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvaluationResult(ORMSchema):
    attempt_id: int = Field(validation_alias=AliasChoices("attempt_id", "id"), serialization_alias="attempt_id")
    task_case_id: int | None = None
    test_case_id: int | None = None
    external_id: str | None = None
    model_id: int
    attack_template_id: int | None = None
    status: AttemptStatus
    prompt_excerpt: str | None = None
    model_output_excerpt: str | None = None
    normalized_risk_categories: list[RiskCategoryRef] = Field(default_factory=list)
    judge: JudgeSummary | None = None
    rule_validation: RuleValidationSummary | None = None
    risk: RiskSummary | None = None
    manual_review_status: str = "none"


class JudgeTrustBreakdown(ORMSchema):
    rule_consistency: float = Field(ge=0, le=1)
    ensemble_agreement: float = Field(ge=0, le=1)
    evidence_completeness: float = Field(ge=0, le=1)
    calibration_score: float = Field(ge=0, le=1)


class JudgeTrustSummary(ORMSchema):
    task_id: int
    average_trust_score: float = Field(ge=0, le=1)
    low_trust_count: int = 0
    rule_conflict_count: int = 0
    manual_review_count: int = 0


class ManualReview(ORMSchema):
    review_id: int = Field(validation_alias=AliasChoices("review_id", "id"), serialization_alias="review_id")
    task_attempt_id: int
    trigger_reason: str
    status: ReviewStatus
    decision: ReviewDecision | None = None
    corrected_category_id: int | None = None
    original_score: float | None = None
    corrected_score: float | None = None
    comment: str | None = None
    reviewer: str | None = None
    reviewed_at: datetime | None = None


class ManualReviewDetail(ManualReview):
    task_id: int | None = None
    test_case_id: int | None = None
    external_id: str | None = None
    prompt: str | None = None
    model_output: str | None = None
    judge_verdict: str | None = None
    judge_confidence: float | None = None
    judge_trust_score: float | None = None
    rule_hits: int = 0
    rule_highest_severity: str | None = None
    original_risk_score: float | None = None
    original_risk_level: str | None = None


class RuleValidationDetail(ORMSchema):
    rule_definition_id: int
    rule_code: str | None = None
    passed: bool = True
    severity: RiskLevel | None = None
    hit_count: int = 0
    matched_evidence: Any = None


class JudgeDetail(ORMSchema):
    judge_result_id: int
    judge_profile_id: int
    judge_profile_name: str | None = None
    judge_type: JudgeType | None = None
    strategy: str | None = None
    verdict: JudgeVerdict | None = None
    risk_category: RiskCategoryRef | None = None
    confidence: float | None = None
    trust_score: float | None = None
    trust_breakdown: dict[str, Any] | None = None
    reasoning: str | None = None
    evidence: Any = None
    raw_output: str | None = None


class AttemptDetail(ORMSchema):
    """单次尝试的完整证据链：提示词 → 模型输出 → Judge → 规则 → 风险 → 复核。"""

    attempt_id: int
    task_id: int | None = None
    task_case_id: int
    test_case_id: int | None = None
    external_id: str | None = None
    model_id: int
    model_name: str | None = None
    attack_template_id: int | None = None
    attack_template_name: str | None = None
    attempt_no: int = 1
    status: AttemptStatus
    prompt: str | None = None
    system_prompt: str | None = None
    rendered_prompt: str | None = None
    input_snapshot: dict[str, Any] | None = None
    model_output: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    normalized_risk_categories: list[RiskCategoryRef] = Field(default_factory=list)
    judge: JudgeDetail | None = None
    rule_validations: list[RuleValidationDetail] = Field(default_factory=list)
    risk: RiskAssessment | None = None
    manual_review: ManualReview | None = None


class Statistics(ORMSchema):
    task_id: int
    total_results: int = 0
    safe_count: int = 0
    unsafe_count: int = 0
    uncertain_count: int = 0
    high_risk_count: int = 0
    critical_risk_count: int = 0
    attack_success_rate: float = Field(default=0.0, ge=0, le=1)
    average_risk_score: float = Field(default=0.0, ge=0, le=100)
    average_judge_confidence: float = Field(default=0.0, ge=0, le=1)
    judge_average_trust: float = Field(default=0.0, ge=0, le=1)
    manual_review_rate: float = Field(default=0.0, ge=0, le=1)
    rule_hit_rate: float = Field(default=0.0, ge=0, le=1)
    risk_level_distribution: dict[str, int] = Field(default_factory=dict)
    risk_category_distribution: list[dict[str, Any]] = Field(default_factory=list)
    model_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    attack_template_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    top_risky_cases: list[dict[str, Any]] = Field(default_factory=list)

class Report(ORMSchema):
    report_id: int = Field(validation_alias=AliasChoices("report_id", "id"), serialization_alias="report_id")
    task_id: int
    template_version_id: int | None = None
    report_type: str
    format: ReportFormat
    status: ReportStatus
    file_id: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class ReportTemplate(ORMSchema):
    template_id: int = Field(validation_alias=AliasChoices("template_id", "id"), serialization_alias="template_id")
    code: str
    name: str
    description: str | None = None
    status: str = "active"
    created_at: datetime | None = None


class ReportTemplateVersion(ORMSchema):
    template_version_id: int = Field(
        validation_alias=AliasChoices("template_version_id", "id"),
        serialization_alias="template_version_id",
    )
    template_id: int
    version: str
    format: str
    content: str
    variables_schema: dict[str, Any] | None = None
    status: str = "draft"
    created_at: datetime | None = None



class StoredFile(ORMSchema):
    file_id: int = Field(validation_alias=AliasChoices("file_id", "id"), serialization_alias="file_id")
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    owner_type: str | None = None
    owner_id: int | None = None
    created_at: datetime | None = None

RiskCategory.model_rebuild()
