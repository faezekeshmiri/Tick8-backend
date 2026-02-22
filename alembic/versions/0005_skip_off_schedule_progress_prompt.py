"""Add skip_off_schedule_progress_prompt to user_study_settings.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-22

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_study_settings",
        sa.Column("skip_off_schedule_progress_prompt", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user_study_settings", "skip_off_schedule_progress_prompt")
