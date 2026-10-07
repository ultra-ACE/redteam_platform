from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class AttackMethod(BaseModel):
    __tablename__ = "attack_methods"
    __table_args__ = (
        UniqueConstraint("code", name="uq_attack_methods_code"),
        Index("ix_attack_methods_enabled", "enabled"),
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AttackTemplate(BaseModel):
    __tablename__ = "attack_templates"
    __table_args__ = (
        UniqueConstraint("attack_method_id", "name", "version", name="uq_attack_templates_method_name_version"),
        Index("ix_attack_templates_status", "status"),
    )

    attack_method_id: Mapped[int] = mapped_column(
        PKType, ForeignKey("attack_methods.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSONType)
    version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
