"""report templates

Revision ID: 0002_report_templates
Revises: 0001_initial_schema
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.db.models.base import JSONType, PKType

revision = "0002_report_templates"
down_revision = "0001_initial_schema"
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

    if "report_templates" not in tables:
        op.create_table(
            "report_templates",
            sa.Column("id", PKType, primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(128), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            *_timestamps(),
            sa.UniqueConstraint("code", name="uq_report_templates_code"),
        )
        op.create_index("ix_report_templates_status", "report_templates", ["status"])

    if "report_template_versions" not in tables:
        op.create_table(
            "report_template_versions",
            sa.Column("id", PKType, primary_key=True, autoincrement=True),
            sa.Column("template_id", PKType, sa.ForeignKey("report_templates.id"), nullable=False),
            sa.Column("version", sa.String(64), nullable=False),
            sa.Column("format", sa.String(16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("variables_schema", JSONType, nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            *_timestamps(),
            sa.UniqueConstraint("template_id", "version", name="uq_report_template_versions_template_version"),
        )
        op.create_index("ix_report_template_versions_status", "report_template_versions", ["status"])

    report_columns = {column["name"] for column in inspector.get_columns("reports")}
    if "template_version_id" not in report_columns:
        with op.batch_alter_table("reports", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("template_version_id", PKType, nullable=True))
            batch_op.create_index("ix_reports_template_version_id", ["template_version_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    report_columns = {column["name"] for column in inspector.get_columns("reports")}
    if "template_version_id" in report_columns:
        with op.batch_alter_table("reports", recreate="always") as batch_op:
            batch_op.drop_index("ix_reports_template_version_id")
            batch_op.drop_column("template_version_id")

    tables = set(inspector.get_table_names())
    if "report_template_versions" in tables:
        op.drop_table("report_template_versions")
    if "report_templates" in tables:
        op.drop_table("report_templates")
