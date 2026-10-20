"""task seed selection: benchmark_version_id becomes optional

Revision ID: 0006_task_seed_selection
Revises: 0005_contract_freeze
Create Date: 2026-10-20

新任务直接按 seed_test_case_ids 选种子，不再强制绑定 Benchmark 版本。
旧任务保留原版本字段，保证历史数据可读。
"""
import sqlalchemy as sa
from alembic import op


revision = "0006_task_seed_selection"
down_revision = "0005_contract_freeze"
branch_labels = None
depends_on = None


def _alter_nullable(nullable: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("evaluation_tasks") as batch_op:
            batch_op.alter_column(
                "benchmark_version_id",
                existing_type=sa.BigInteger(),
                nullable=nullable,
            )
    else:
        op.alter_column(
            "evaluation_tasks",
            "benchmark_version_id",
            existing_type=sa.BigInteger(),
            nullable=nullable,
        )


def upgrade() -> None:
    _alter_nullable(True)


def downgrade() -> None:
    # 降级前把空版本回填为一个已存在的版本，避免 NOT NULL 失败
    op.get_bind().execute(
        sa.text(
            "UPDATE evaluation_tasks SET benchmark_version_id = "
            "(SELECT MIN(id) FROM benchmark_versions) "
            "WHERE benchmark_version_id IS NULL"
        )
    )
    _alter_nullable(False)
