from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class BenchmarkVersion(BaseModel):
    __tablename__ = "benchmark_versions"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version", name="uq_benchmark_versions_benchmark_version"),
        Index("ix_benchmark_versions_checksum", "checksum"),
    )

    benchmark_id: Mapped[int] = mapped_column(PKType, ForeignKey("benchmarks.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("files.id"))
    raw_schema: Mapped[dict | None] = mapped_column(JSONType)
    case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    imported_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="importing", nullable=False)


class TestCase(BaseModel):
    __test__ = False
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("benchmark_version_id", "external_id", name="uq_test_cases_version_external"),
        Index("ix_test_cases_content_hash", "content_hash"),
        Index("ix_test_cases_language", "language"),
    )

    benchmark_version_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("benchmark_versions.id"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    source_label: Mapped[str | None] = mapped_column(String(255))
    case_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class TestCaseRiskLabel(BaseModel):
    __test__ = False
    __tablename__ = "test_case_risk_labels"
    __table_args__ = (
        UniqueConstraint("test_case_id", "risk_category_id", name="uq_test_case_risk_labels_pair"),
        Index("ix_test_case_risk_labels_category", "risk_category_id"),
    )

    test_case_id: Mapped[int] = mapped_column(PKType, ForeignKey("test_cases.id"), nullable=False)
    risk_category_id: Mapped[int] = mapped_column(PKType, ForeignKey("risk_categories.id"), nullable=False)
    label_source: Mapped[str] = mapped_column(String(32), default="benchmark", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float | None] = mapped_column()
