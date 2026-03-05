"""Add preferred_language to users.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-05

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_language")
