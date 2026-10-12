"""drop unused idempotency_keys table

Revision ID: 0004_drop_idempotency_keys
Revises: 0003_risk_label_aliases
Create Date: 2026-10-11

这张表建了模型、仓储和 UnitOfWork 入口，但没有任何服务或接口调用过它，
属于只占结构没有用途的空表。报告重复生成的问题改用
ReportRepository.claim_for_generation 的原子状态领取解决，不再需要它。
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db.models.base import JSONType, PKType

revision = "0004_drop_idempotency_keys"
down_revision = "0003_risk_label_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "idempotency_keys" in set(inspector.get_table_names()):
        op.drop_table("idempotency_keys")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "idempotency_keys" not in set(inspector.get_table_names()):
        op.create_table(
            "idempotency_keys",
            sa.Column("id", PKType, primary_key=True, autoincrement=True),
            sa.Column("key", sa.String(255), nullable=False),
            sa.Column("request_hash", sa.String(128), nullable=False),
            sa.Column("response_body", JSONType, nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("key", name="uq_idempotency_keys_key"),
        )
        op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])
