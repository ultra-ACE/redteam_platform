from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class JudgeProfile(BaseModel):
    __tablename__ = "judge_profiles"
    __table_args__ = (
        Index("ix_judge_profiles_enabled", "enabled"),
        Index("ix_judge_profiles_judge_type", "judge_type"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    judge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    judge_model_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("models.id"))
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict | None] = mapped_column(JSONType)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class JudgeResult(BaseModel):
    __tablename__ = "judge_results"
    __table_args__ = (
        UniqueConstraint(
            "task_attempt_id",
            "judge_profile_id",
            "run_no",
            name="uq_judge_results_attempt_profile_run",
        ),
        Index("ix_judge_results_status", "status"),
        Index("ix_judge_results_risk_category", "risk_category_id"),
    )

    task_attempt_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("task_attempts.id"), nullable=False
    )
    judge_profile_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("judge_profiles.id"), nullable=False
    )
    run_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(32))
    risk_category_id: Mapped[int | None] = mapped_column(
        PKType, ForeignKey("risk_categories.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    reasoning: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list | None] = mapped_column(JSONType)
    raw_output: Mapped[str | None] = mapped_column(Text)
    trust_score: Mapped[float | None] = mapped_column(Float)
    trust_breakdown: Mapped[dict | None] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)


class RuleSet(BaseModel):
    __tablename__ = "rule_sets"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_rule_sets_name_version"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RuleDefinition(BaseModel):
    __tablename__ = "rule_definitions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "code", name="uq_rule_definitions_set_code"),
        Index("ix_rule_definitions_enabled", "enabled"),
    )

    rule_set_id: Mapped[int] = mapped_column(PKType, ForeignKey("rule_sets.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[dict | None] = mapped_column(JSONType)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("risk_categories.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RuleValidationResult(BaseModel):
    __tablename__ = "rule_validation_results"
    __table_args__ = (
        UniqueConstraint(
            "task_attempt_id",
            "rule_definition_id",
            name="uq_rule_validation_results_attempt_rule",
        ),
        Index("ix_rule_validation_results_severity", "severity"),
    )

    task_attempt_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("task_attempts.id"), nullable=False
    )
    rule_definition_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("rule_definitions.id"), nullable=False
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(32))
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_evidence: Mapped[dict | None] = mapped_column(JSONType)
