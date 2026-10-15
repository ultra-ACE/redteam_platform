"""contract freeze: remove risk taxonomy and hard-code attack methods

Revision ID: 0005_contract_freeze
Revises: 0004_drop_idempotency_keys
Create Date: 2026-10-13

This is a destructive schema consolidation. Back up the database before
running it. Downgrade is intentionally not automatic because deleted
classification and report-template data cannot be reconstructed reliably.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_contract_freeze"
down_revision = "0004_drop_idempotency_keys"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    if column_name in _column_names(table_name):
        if op.get_bind().dialect.name == "sqlite":
            for index in inspect(op.get_bind()).get_indexes(table_name):
                if column_name in index.get("column_names", []):
                    op.drop_index(index["name"], table_name=table_name)
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_column(column_name)
        else:
            op.drop_column(table_name, column_name)


def _drop_table_if_present(table_name: str) -> None:
    if table_name in _table_names():
        op.drop_table(table_name)


def upgrade() -> None:
    tables = _table_names()

    _add_column_if_missing(
        "test_cases",
        sa.Column("dataset_type", sa.String(32), nullable=False, server_default="harmful"),
    )
    _add_column_if_missing("test_cases", sa.Column("sample_kind", sa.String(32), nullable=True))

    _add_column_if_missing(
        "evaluation_tasks",
        sa.Column("pause_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        "evaluation_tasks",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    _drop_column_if_present("evaluation_tasks", "risk_taxonomy_id")

    _add_column_if_missing("task_cases", sa.Column("celery_task_id", sa.String(255), nullable=True))
    _add_column_if_missing(
        "task_cases",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "task_attempts",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )

    if "attack_templates" in tables:
        _add_column_if_missing("attack_templates", sa.Column("method_code", sa.String(64), nullable=True))
        if "attack_methods" in tables and "attack_method_id" in _column_names("attack_templates"):
            op.execute(
                sa.text(
                    "UPDATE attack_templates "
                    "SET method_code = ("
                    "SELECT attack_methods.code FROM attack_methods "
                    "WHERE attack_methods.id = attack_templates.attack_method_id"
                    ") "
                    "WHERE method_code IS NULL"
                )
            )
        op.execute(
            sa.text(
                "UPDATE attack_templates SET method_code = 'direct_request' "
                "WHERE method_code IS NULL"
            )
        )
        inspector = inspect(op.get_bind())
        foreign_keys = [
            foreign_key
            for foreign_key in inspector.get_foreign_keys("attack_templates")
            if "attack_method_id" in foreign_key.get("constrained_columns", [])
        ]
        unique_constraints = inspector.get_unique_constraints("attack_templates")
        version_unique = next(
            (
                constraint
                for constraint in unique_constraints
                if constraint.get("name") == "uq_attack_templates_method_name_version"
            ),
            None,
        )
        has_attack_method_id = "attack_method_id" in _column_names("attack_templates")

        with op.batch_alter_table("attack_templates") as batch_op:
            batch_op.alter_column("method_code", existing_type=sa.String(64), nullable=False)
            for foreign_key in foreign_keys:
                constraint_name = foreign_key.get("name")
                if constraint_name:
                    batch_op.drop_constraint(constraint_name, type_="foreignkey")
            if version_unique and version_unique.get("column_names") != ["method_code", "name", "version"]:
                batch_op.drop_constraint(
                    "uq_attack_templates_method_name_version",
                    type_="unique",
                )
                batch_op.create_unique_constraint(
                    "uq_attack_templates_method_name_version",
                    ["method_code", "name", "version"],
                )
            if has_attack_method_id:
                batch_op.drop_column("attack_method_id")
        if "ix_attack_templates_method_code" not in {
            index["name"] for index in inspect(op.get_bind()).get_indexes("attack_templates")
        }:
            op.create_index("ix_attack_templates_method_code", "attack_templates", ["method_code"])

    _add_column_if_missing("manual_reviews", sa.Column("corrected_verdict", sa.String(32), nullable=True))
    _drop_column_if_present("manual_reviews", "risk_assessment_id")
    _drop_column_if_present("manual_reviews", "corrected_category_id")
    _drop_column_if_present("manual_reviews", "original_score")
    _drop_column_if_present("manual_reviews", "corrected_score")

    _drop_column_if_present("judge_results", "risk_category_id")
    _drop_column_if_present("rule_definitions", "category_id")
    _drop_column_if_present("reports", "template_version_id")
    _drop_column_if_present("reports", "report_version")

    # Child tables must be removed before parents that they reference.
    for table_name in (
        "risk_dimension_scores",
        "risk_assessments",
        "benchmark_risk_mappings",
        "risk_label_aliases",
        "test_case_risk_labels",
        "risk_categories",
        "risk_taxonomies",
        "task_events",
        "statistics_snapshots",
        "report_template_versions",
        "report_templates",
        "audit_logs",
        "system_configs",
        "attack_methods",
    ):
        _drop_table_if_present(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "0005_contract_freeze is a destructive schema consolidation; "
        "restore the pre-0005 database backup instead of downgrading."
    )
