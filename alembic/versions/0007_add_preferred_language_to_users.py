"""Add preferred_language column to users table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-06

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_language",
            sa.String(10),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_language")
