from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class EvaluationTask(BaseModel):
    __tablename__ = "evaluation_tasks"
    __table_args__ = (
        Index("ix_evaluation_tasks_status", "status"),
        Index("ix_evaluation_tasks_created_at", "created_at"),
        Index("ix_evaluation_tasks_status_priority", "status", "priority"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    benchmark_version_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("benchmark_versions.id"), nullable=False
    )
    risk_taxonomy_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("risk_taxonomies.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONType)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class TaskModelBinding(BaseModel):
    __tablename__ = "task_model_bindings"
    __table_args__ = (
        UniqueConstraint("task_id", "model_id", "role", name="uq_task_model_bindings_task_model_role"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(PKType, ForeignKey("models.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="target", nullable=False)
    model_params: Mapped[dict | None] = mapped_column(JSONType)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TaskCase(BaseModel):
    __tablename__ = "task_cases"
    __table_args__ = (
        UniqueConstraint("task_id", "case_key", name="uq_task_cases_task_case_key"),
        Index("ix_task_cases_task_status", "task_id", "status"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(PKType, ForeignKey("test_cases.id"), nullable=False)
    attack_template_id: Mapped[int | None] = mapped_column(
        PKType, ForeignKey("attack_templates.id")
    )
    case_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    case_config: Mapped[dict | None] = mapped_column(JSONType)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TaskAttempt(BaseModel):
    __tablename__ = "task_attempts"
    __table_args__ = (
        UniqueConstraint(
            "task_case_id",
            "model_id",
            "attempt_no",
            name="uq_task_attempts_case_model_attempt",
        ),
        Index("ix_task_attempts_status", "status"),
        Index("ix_task_attempts_model_created", "model_id", "created_at"),
    )

    task_case_id: Mapped[int] = mapped_column(PKType, ForeignKey("task_cases.id"), nullable=False)
    model_id: Mapped[int] = mapped_column(PKType, ForeignKey("models.id"), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONType)
    request_payload_hash: Mapped[str | None] = mapped_column(String(128))
    output_text: Mapped[str | None] = mapped_column(Text)
    output_file_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("files.id"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEvent(BaseModel):
    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_task_id", "task_id", "id"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONType)
