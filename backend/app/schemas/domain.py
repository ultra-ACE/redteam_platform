from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator

from .common import ORMSchema
from .enums import (
    AttackMethodCode,
    AttemptStatus,
    DatasetType,
    JudgeType,
    JudgeVerdict,
    ModelAdapter,
    ModelUsageScope,
    ReportFormat,
    ReportStatus,
    ReviewDecision,
    ReviewStatus,
    SampleKind,
    TaskStatus,
)


class HealthData(ORMSchema):
    status: str = "healthy"
    database: str = "up"
    redis: str = "up"
    storage: str = "up"
    version: str = "1.0.0"


class Benchmark(ORMSchema):
    benchmark_id: int = Field(validation_alias=AliasChoices("benchmark_id", "id"), serialization_alias="benchmark_id")
    name: str
    slug: str
    source_type: str
    description: str | None = None
    status: str = "active"
    created_at: datetime | None = None


class BenchmarkVersion(ORMSchema):
    benchmark_version_id: int = Field(
        validation_alias=AliasChoices("benchmark_version_id", "id"),
        serialization_alias="benchmark_version_id",
    )
    benchmark_id: int
    version: str
    source_file_id: int | None = None
    case_count: int = 0
    checksum: str | None = None
    status: str = "ready"
    imported_at: datetime | None = None


class BenchmarkImportError(ORMSchema):
    row_number: int
    message: str


class BenchmarkImportResult(ORMSchema):
    benchmark_id: int
    benchmark_version_id: int
    imported_count: int
    failed_count: int
    errors: list[BenchmarkImportError] = Field(default_factory=list)
    detected_adapter: str | None = None
    adapter_display_name: str | None = None
    adapter_confidence: float | None = None
    field_mapping: dict[str, str] = Field(default_factory=dict)
    dataset_type_counts: dict[str, int] = Field(default_factory=dict)


class TestCase(ORMSchema):
    test_case_id: int = Field(validation_alias=AliasChoices("test_case_id", "id"), serialization_alias="test_case_id")
    benchmark_version_id: int
    external_id: str
    prompt: str
    system_prompt: str | None = None
    language: str | None = None
    source_label: str | None = None
    dataset_type: DatasetType = DatasetType.harmful
    sample_kind: SampleKind | None = None
    status: str = "active"


ATTACK_METHOD_ALIASES = {
    "role_play_api": "role_play",
    "roleplay": "role_play",
    "role-play": "role_play",
    "direct": "direct_request",
    "direct_api": "direct_request",
    "prefix": "prefix_injection",
    "prefix-injection": "prefix_injection",
    "refusal": "refusal_suppression",
    "refusal-suppression": "refusal_suppression",
}


def mask_secret_ref(value: object) -> str | None:
    """模型密钥只返回可辨识的掩码，绝不把明文回传给前端。

    - ``env:XXX`` 只暴露环境变量名，本身不是密钥；
    - ``literal:真实Key`` 只保留后四位；
    - 无前缀的旧数据同样按明文处理。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("env:"):
        return text
    prefix = ""
    body = text
    if text.startswith("literal:"):
        prefix = "literal:"
        body = text[len("literal:"):]
    if len(body) <= 4:
        return f"{prefix}****"
    return f"{prefix}****{body[-4:]}"


class Model(ORMSchema):
    model_id: int = Field(validation_alias=AliasChoices("model_id", "id"), serialization_alias="model_id")
    name: str
    provider: str
    adapter_type: ModelAdapter
    base_url: str
    model_name: str
    secret_ref: str | None = None
    secret_configured: bool = False
    usage_scope: ModelUsageScope
    enabled: bool = True
    created_at: datetime | None = None

    @field_validator("secret_ref", mode="before")
    @classmethod
    def _mask_secret_ref(cls, value: object) -> str | None:
        return mask_secret_ref(value)

    @model_validator(mode="after")
    def _fill_secret_configured(self) -> "Model":
        self.secret_configured = self.secret_ref is not None
        return self


class HealthCheckData(ORMSchema):
    model_id: int
    status: str = "healthy"
    latency_ms: int | None = None
    error_message: str | None = None


class AttackMethod(ORMSchema):
    code: AttackMethodCode
    name: str
    description: str | None = None


class AttackTemplate(ORMSchema):
    attack_template_id: int = Field(
        validation_alias=AliasChoices("attack_template_id", "id"),
        serialization_alias="attack_template_id",
    )
    method_code: AttackMethodCode
    name: str
    template_text: str
    variables: list[str] = Field(default_factory=list)
    version: str = "v1"
    status: str = "active"

    @field_validator("method_code", mode="before")
    @classmethod
    def _normalize_method_code(cls, value: object) -> object:
        """兼容历史数据里的写法，避免一条旧记录让整个列表接口 500。"""
        if value is None:
            return value
        text = str(getattr(value, "value", value)).strip().lower()
        return ATTACK_METHOD_ALIASES.get(text, text)


class JudgeProfile(ORMSchema):
    judge_profile_id: int = Field(
        validation_alias=AliasChoices("judge_profile_id", "id"),
        serialization_alias="judge_profile_id",
    )
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
    highest_severity: str | None = None


class EvaluationTask(ORMSchema):
    task_id: int = Field(validation_alias=AliasChoices("task_id", "id"), serialization_alias="task_id")
    name: str
    benchmark_version_id: int | None = None
    status: TaskStatus
    progress: float = Field(default=0, ge=0, le=1)
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    cancel_requested: bool = False
    pause_requested: bool = False
    last_heartbeat_at: datetime | None = None
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
    pause_requested: bool = False
    last_heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvaluationResult(ORMSchema):
    attempt_id: int = Field(validation_alias=AliasChoices("attempt_id", "id"), serialization_alias="attempt_id")
    task_case_id: int | None = None
    test_case_id: int | None = None
    external_id: str | None = None
    model_id: int
    attack_template_id: int | None = None
    dataset_type: DatasetType | None = None
    sample_kind: SampleKind | None = None
    status: AttemptStatus
    prompt_excerpt: str | None = None
    model_output_excerpt: str | None = None
    judge: JudgeSummary | None = None
    rule_validation: RuleValidationSummary | None = None
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
    corrected_verdict: str | None = None
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


class RuleValidationDetail(ORMSchema):
    rule_definition_id: int
    rule_code: str | None = None
    passed: bool = True
    severity: str | None = None
    hit_count: int = 0
    matched_evidence: Any = None


class JudgeDetail(ORMSchema):
    judge_result_id: int
    judge_profile_id: int
    judge_profile_name: str | None = None
    judge_type: JudgeType | None = None
    strategy: str | None = None
    verdict: JudgeVerdict | None = None
    confidence: float | None = None
    trust_score: float | None = None
    trust_breakdown: dict[str, Any] | None = None
    reasoning: str | None = None
    evidence: Any = None
    raw_output: str | None = None


class AttemptDetail(ORMSchema):
    """单次尝试的完整证据链：提示词 → 模型输出 → Judge → 规则 → 复核。"""

    attempt_id: int
    task_id: int | None = None
    task_case_id: int
    test_case_id: int | None = None
    external_id: str | None = None
    model_id: int
    model_name: str | None = None
    attack_template_id: int | None = None
    attack_template_name: str | None = None
    dataset_type: DatasetType | None = None
    sample_kind: SampleKind | None = None
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
    judge: JudgeDetail | None = None
    rule_validations: list[RuleValidationDetail] = Field(default_factory=list)
    manual_review: ManualReview | None = None


class Statistics(ORMSchema):
    task_id: int
    total_results: int = 0
    safe_count: int = 0
    unsafe_count: int = 0
    uncertain_count: int = 0
    attack_success_rate: float = Field(default=0.0, ge=0, le=1)
    average_judge_confidence: float = Field(default=0.0, ge=0, le=1)
    judge_average_trust: float = Field(default=0.0, ge=0, le=1)
    manual_review_rate: float = Field(default=0.0, ge=0, le=1)
    rule_hit_rate: float = Field(default=0.0, ge=0, le=1)
    judge_verdict_distribution: dict[str, int] = Field(default_factory=dict)
    dataset_type_distribution: dict[str, int] = Field(default_factory=dict)
    model_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    attack_template_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    top_unsafe_cases: list[dict[str, Any]] = Field(default_factory=list)


class Report(ORMSchema):
    report_id: int = Field(validation_alias=AliasChoices("report_id", "id"), serialization_alias="report_id")
    task_id: int
    report_type: str
    format: ReportFormat
    status: ReportStatus
    file_id: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class StoredFile(ORMSchema):
    file_id: int = Field(validation_alias=AliasChoices("file_id", "id"), serialization_alias="file_id")
    original_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    owner_type: str | None = None
    owner_id: int | None = None
    created_at: datetime | None = None
