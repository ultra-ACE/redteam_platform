"""template libraries: group attack templates by library name

Revision ID: 0008_template_libraries
Revises: 0007_remove_benchmark_versions
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0008_template_libraries"
down_revision = "0007_remove_benchmark_versions"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("attack_templates")
    }


def _unique_names() -> set[str]:
    return {
        item["name"]
        for item in inspect(op.get_bind()).get_unique_constraints("attack_templates")
        if item.get("name")
    }


def upgrade() -> None:
    if "library_name" not in _columns():
        op.add_column(
            "attack_templates",
            sa.Column(
                "library_name",
                sa.String(255),
                nullable=False,
                server_default="默认模板库",
            ),
        )

    unique_names = _unique_names()
    old_constraint = "uq_attack_templates_method_name_version"
    new_constraint = "uq_attack_templates_library_name_version"

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("attack_templates") as batch_op:
            if old_constraint in unique_names:
                batch_op.drop_constraint(old_constraint, type_="unique")
            if new_constraint not in unique_names:
                batch_op.create_unique_constraint(
                    new_constraint,
                    ["library_name", "name", "version"],
                )
    else:
        if old_constraint in unique_names:
            op.drop_constraint(old_constraint, "attack_templates", type_="unique")
        if new_constraint not in unique_names:
            op.create_unique_constraint(
                new_constraint,
                "attack_templates",
                ["library_name", "name", "version"],
            )


def downgrade() -> None:
    raise RuntimeError(
        "0008_template_libraries is not automatically reversible; restore a "
        "pre-0008 database backup instead."
    )
