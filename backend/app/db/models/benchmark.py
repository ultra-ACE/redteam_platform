from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class Benchmark(BaseModel):
    __tablename__ = "benchmarks"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_benchmarks_slug"),
        Index("ix_benchmarks_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_file_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("files.id"))
    raw_schema: Mapped[dict | None] = mapped_column(JSONType)
    case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    imported_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class TestCase(BaseModel):
    __test__ = False
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "external_id", name="uq_test_cases_benchmark_external"),
        Index("ix_test_cases_content_hash", "content_hash"),
        Index("ix_test_cases_language", "language"),
    )

    benchmark_id: Mapped[int] = mapped_column(PKType, ForeignKey("benchmarks.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    source_label: Mapped[str | None] = mapped_column(String(255))
    dataset_type: Mapped[str] = mapped_column(String(32), default="harmful", nullable=False)
    sample_kind: Mapped[str | None] = mapped_column(String(32))
    case_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
