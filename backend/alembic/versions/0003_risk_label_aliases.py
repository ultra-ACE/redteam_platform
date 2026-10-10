"""risk label aliases

Revision ID: 0003_risk_label_aliases
Revises: 0002_report_templates
Create Date: 2026-10-10

新增 risk_label_aliases 表：存放"异构 Benchmark 原始风险标签 -> 统一风险分类"
的别名词典，是创新点一（统一风险分类）的落点之一。
表本身只建结构；具体别名由导入时按统一 code 自动播种（见 risk_aliases.py）。
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db.models.base import PKType

revision = "0003_risk_label_aliases"
down_revision = "0002_report_templates"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "risk_label_aliases" not in tables:
        op.create_table(
            "risk_label_aliases",
            sa.Column("id", PKType, primary_key=True, autoincrement=True),
            sa.Column("taxonomy_id", PKType, sa.ForeignKey("risk_taxonomies.id"), nullable=False),
            sa.Column("alias", sa.String(255), nullable=False),
            sa.Column("risk_category_id", PKType, sa.ForeignKey("risk_categories.id"), nullable=False),
            sa.Column("source", sa.String(32), nullable=False, server_default="builtin"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("note", sa.Text(), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("taxonomy_id", "alias", name="uq_risk_label_aliases_taxonomy_alias"),
        )
        op.create_index("ix_risk_label_aliases_category", "risk_label_aliases", ["risk_category_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "risk_label_aliases" in set(inspector.get_table_names()):
        op.drop_table("risk_label_aliases")
