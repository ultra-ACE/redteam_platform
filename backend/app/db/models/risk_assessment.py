from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class RiskAssessment(BaseModel):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint("task_attempt_id", "score_version", name="uq_risk_assessments_attempt_version"),
        Index("ix_risk_assessments_risk_level", "risk_level"),
        Index("ix_risk_assessments_overall_score", "overall_score"),
    )

    task_attempt_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("task_attempts.id"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    judge_trust_score: Mapped[float | None] = mapped_column(Float)
    dimension_summary: Mapped[dict | None] = mapped_column(JSONType)
    score_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_override_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RiskDimensionScore(BaseModel):
    __tablename__ = "risk_dimension_scores"
    __table_args__ = (
        UniqueConstraint("risk_assessment_id", "dimension_code", name="uq_risk_dimension_scores_assessment_dimension"),
    )

    risk_assessment_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("risk_assessments.id"), nullable=False
    )
    dimension_code: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONType)
    source: Mapped[str | None] = mapped_column(String(64))


class ManualReview(BaseModel):
    __tablename__ = "manual_reviews"
    __table_args__ = (
        Index("ix_manual_reviews_status_created", "status", "created_at"),
        Index("ix_manual_reviews_task_attempt_id", "task_attempt_id"),
    )

    task_attempt_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("task_attempts.id"), nullable=False
    )
    judge_result_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("judge_results.id"))
    risk_assessment_id: Mapped[int | None] = mapped_column(
        PKType, ForeignKey("risk_assessments.id")
    )
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(32))
    corrected_category_id: Mapped[int | None] = mapped_column(
        PKType, ForeignKey("risk_categories.id")
    )
    original_score: Mapped[float | None] = mapped_column(Float)
    corrected_score: Mapped[float | None] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
