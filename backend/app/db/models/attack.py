from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel, JSONType, PKType


class AttackTemplate(BaseModel):
    __tablename__ = "attack_templates"
    __table_args__ = (
        UniqueConstraint(
            "library_name",
            "name",
            "version",
            name="uq_attack_templates_library_name_version",
        ),
        Index("ix_attack_templates_status", "status"),
    )

    library_name: Mapped[str] = mapped_column(
        String(255),
        default="默认模板库",
        server_default="默认模板库",
        nullable=False,
    )
    method_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSONType)
    version: Mapped[str] = mapped_column(String(64), default="v1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
