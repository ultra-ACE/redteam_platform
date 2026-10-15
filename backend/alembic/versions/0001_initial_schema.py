"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-06

Bootstrap migration:
Uses the current SQLAlchemy metadata to create the core domain tables.
Later risk/report-template tables from 0002-0004 are transitional and are
removed again by 0005_contract_freeze.
"""
from alembic import op

from app.db.base import Base
import app.db.models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
