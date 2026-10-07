from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class StatisticsSnapshot(BaseModel):
    __tablename__ = "statistics_snapshots"
    __table_args__ = (
        Index("ix_statistics_snapshots_task_scope_time", "task_id", "scope", "generated_at"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSONType)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(BaseModel):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_task_created", "task_id", "created_at"),
        Index("ix_reports_status", "status"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    file_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("files.id"))
    template_version_id: Mapped[int | None] = mapped_column(
        PKType, ForeignKey("report_template_versions.id")
    )
    filter_snapshot: Mapped[dict | None] = mapped_column(JSONType)
    report_version: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ReportTemplate(BaseModel):
    __tablename__ = "report_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_report_templates_code"),
        Index("ix_report_templates_status", "status"),
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class ReportTemplateVersion(BaseModel):
    __tablename__ = "report_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_report_template_versions_template_version"),
        Index("ix_report_template_versions_status", "status"),
    )

    template_id: Mapped[int] = mapped_column(PKType, ForeignKey("report_templates.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict | None] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)


class StoredFile(BaseModel):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_sha256", "sha256"),
        Index("ix_files_owner", "owner_type", "owner_id"),
    )

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_type: Mapped[str | None] = mapped_column(String(64))
    owner_id: Mapped[int | None] = mapped_column(PKType)


class SystemConfig(BaseModel):
    __tablename__ = "system_configs"
    __table_args__ = (
        UniqueConstraint("config_key", name="uq_system_configs_config_key"),
    )

    config_key: Mapped[str] = mapped_column(String(128), nullable=False)
    config_value: Mapped[dict | None] = mapped_column(JSONType)
    description: Mapped[str | None] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_audit_logs_request_id", "request_id"),
    )

    actor: Mapped[str] = mapped_column(String(128), default="local", nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(PKType)
    before_data: Mapped[dict | None] = mapped_column(JSONType)
    after_data: Mapped[dict | None] = mapped_column(JSONType)
    request_id: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))


class IdempotencyKey(BaseModel):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("key", name="uq_idempotency_keys_key"),
        Index("ix_idempotency_keys_expires_at", "expires_at"),
    )

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_body: Mapped[dict | None] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
