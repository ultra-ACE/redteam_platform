from typing import Any

from pydantic import BaseModel, Field, model_validator

from .enums import (
    AttackMethodCode,
    JudgeType,
    ModelAdapter,
    ModelUsageScope,
    ReportFormat,
    ReviewDecision,
)


class TestCaseUpdateRequest(BaseModel):
    prompt: str | None = None
    system_prompt: str | None = None
    language: str | None = None
    dataset_type: str | None = None
    sample_kind: str | None = None
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


class ModelUpdateRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    adapter_type: ModelAdapter | None = None
    base_url: str | None = None
    model_name: str | None = None
    secret_ref: str | None = None
    default_params: dict[str, Any] | None = None
    usage_scope: ModelUsageScope | None = None
    enabled: bool | None = None


class AttackTemplateCreateRequest(BaseModel):
    method_code: AttackMethodCode = AttackMethodCode.custom
    library_name: str = "默认模板库"
    name: str
    template_text: str
    variables: list[str] = Field(default_factory=list)
    version: str = "v1"
    status: str = "active"


class AttackTemplateUpdateRequest(BaseModel):
    library_name: str | None = None
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
    timeout_seconds: int = Field(default=600, ge=1)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    concurrency: int = Field(default=4, ge=1)


class ModelBinding(BaseModel):
    model_id: int
    role: str = "target"
    model_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class EvaluationTaskCreateRequest(BaseModel):
    name: str
    benchmark_id: int | None = None
    seed_test_case_ids: list[int] = Field(default_factory=list)
    model_bindings: list[ModelBinding]
    attack_template_ids: list[int] = Field(default_factory=list)
    judge_profile_ids: list[int]
    rule_set_ids: list[int]
    execution: ExecutionConfig
    priority: str = "normal"

    @model_validator(mode="after")
    def _require_seed_source(self) -> "EvaluationTaskCreateRequest":
        if not self.seed_test_case_ids and self.benchmark_id is None:
            raise ValueError("seed_test_case_ids 与 benchmark_id 至少提供一个")
        return self


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
    corrected_verdict: str | None = None
    comment: str | None = None


class ManualReviewUpdateRequest(BaseModel):
    decision: ReviewDecision
    corrected_verdict: str | None = None
    comment: str | None = None
    status: str | None = None


class ReportCreateRequest(BaseModel):
    task_id: int
    report_type: str = "full"
    format: ReportFormat = ReportFormat.html
    include: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)


class TaskActionData(BaseModel):
    task_id: int
    status: str
    cancel_requested: bool | None = None
    pause_requested: bool | None = None


class RetryFailedData(BaseModel):
    task_id: int
    retry_count: int
    status: str
