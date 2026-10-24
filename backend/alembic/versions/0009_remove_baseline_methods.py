"""remove the four static baseline template categories

Revision ID: 0009_remove_baseline_methods
Revises: 0008_template_libraries
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op


revision = "0009_remove_baseline_methods"
down_revision = "0008_template_libraries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE attack_templates "
            "SET method_code = 'custom' "
            "WHERE lower(method_code) <> 'custom'"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "0009_remove_baseline_methods is not reversible; restore a "
        "pre-0009 database backup instead."
    )
