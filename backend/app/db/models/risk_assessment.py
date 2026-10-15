from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, PKType


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
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str | None] = mapped_column(String(32))
    corrected_verdict: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
