from enum import Enum


class TaskStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    paused = "paused"
    succeeded = "succeeded"
    partially_failed = "partially_failed"
    failed = "failed"
    cancelled = "cancelled"


class CaseStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"


class AttemptStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    timeout = "timeout"
    cancelled = "cancelled"


class JudgeStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class ReviewStatus(str, Enum):
    pending = "pending"
    in_review = "in_review"
    resolved = "resolved"
    rejected = "rejected"


class ReportStatus(str, Enum):
    queued = "queued"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class RiskLevel(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class JudgeVerdict(str, Enum):
    safe = "safe"
    unsafe = "unsafe"
    uncertain = "uncertain"


class JudgeType(str, Enum):
    model = "model"
    rule = "rule"
    ensemble = "ensemble"


class ModelAdapter(str, Enum):
    openai_compatible = "openai_compatible"
    ollama = "ollama"
    custom_http = "custom_http"
    mock = "mock"


class ModelUsageScope(str, Enum):
    target = "target"
    judge = "judge"
    both = "both"


class ReportFormat(str, Enum):
    json = "json"
    md = "md"
    csv = "csv"
    html = "html"
    pdf = "pdf"


class ReviewDecision(str, Enum):
    confirmed = "confirmed"
    override = "override"
    rejected = "rejected"
    unresolved = "unresolved"


class ReviewTrigger(str, Enum):
    judge_low_trust = "judge_low_trust"
    rule_conflict = "rule_conflict"
    judge_category_conflict = "judge_category_conflict"
    judge_schema_invalid = "judge_schema_invalid"
    score_boundary = "score_boundary"
    random_calibration = "random_calibration"
    user_requested = "user_requested"
