"""Add color column to sub_categories.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-25

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_categories",
        sa.Column("color", sa.String(7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sub_categories", "color")
