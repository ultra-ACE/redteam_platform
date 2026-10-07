from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType


class ModelRegistry(BaseModel):
    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("name", "model_name", name="uq_models_name_model_name"),
        Index("ix_models_enabled", "enabled"),
        Index("ix_models_usage_scope", "usage_scope"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    default_params: Mapped[dict | None] = mapped_column(JSONType)
    capabilities: Mapped[dict | None] = mapped_column(JSONType)
    usage_scope: Mapped[str] = mapped_column(String(32), default="target", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
