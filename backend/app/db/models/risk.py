from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class RiskTaxonomy(BaseModel):
    __tablename__ = "risk_taxonomies"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_risk_taxonomies_name_version"),
        Index("ix_risk_taxonomies_is_default", "is_default"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class RiskCategory(BaseModel):
    __tablename__ = "risk_categories"
    __table_args__ = (
        UniqueConstraint("taxonomy_id", "code", name="uq_risk_categories_taxonomy_code"),
        Index("ix_risk_categories_parent_id", "parent_id"),
    )

    taxonomy_id: Mapped[int] = mapped_column(PKType, ForeignKey("risk_taxonomies.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(PKType, ForeignKey("risk_categories.id"))
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    severity_weight: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    examples: Mapped[dict | None] = mapped_column(JSONType)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class BenchmarkRiskMapping(BaseModel):
    __tablename__ = "benchmark_risk_mappings"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_version_id",
            "raw_label",
            "risk_category_id",
            name="uq_benchmark_risk_mappings_raw_category",
        ),
        Index("ix_benchmark_risk_mappings_raw_label", "raw_label"),
    )

    benchmark_version_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("benchmark_versions.id"), nullable=False
    )
    raw_label: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_category_id: Mapped[int] = mapped_column(PKType, ForeignKey("risk_categories.id"), nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(32), default="alias", nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    mapping_note: Mapped[str | None] = mapped_column(Text)
