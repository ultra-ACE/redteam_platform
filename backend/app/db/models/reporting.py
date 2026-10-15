from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class Report(BaseModel):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_task_created", "task_id", "created_at"),
        Index("ix_reports_status", "status"),
    )

    task_id: Mapped[int] = mapped_column(PKType, ForeignKey("evaluation_tasks.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), default="html", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    file_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("files.id"))
    filter_snapshot: Mapped[dict | None] = mapped_column(JSONType)
    error_message: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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




