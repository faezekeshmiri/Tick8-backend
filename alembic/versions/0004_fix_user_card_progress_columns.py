"""Fix user_card_progress when table exists but is missing status (and other) columns.

Run this if you see: column user_card_progress.status does not exist.
Revision ID: 0004
Revises: 0003
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure enum exists (in case 0003 was partially applied)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'progress_status_enum') THEN
                CREATE TYPE progress_status_enum AS ENUM (
                    'pending', 'phase1', 'phase2', 'graduated', 'long_term_mastered'
                );
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tick_result_kind_enum') THEN
                CREATE TYPE tick_result_kind_enum AS ENUM ('remembered', 'difficult', 'forgot');
            END IF;
        END $$
    """)

    # Add status column to user_card_progress if missing
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_card_progress' AND column_name = 'status'
            ) THEN
                ALTER TABLE user_card_progress
                ADD COLUMN status progress_status_enum NOT NULL DEFAULT 'pending';
            END IF;
        END $$
    """)

    # Add any other missing columns that the model expects
    for col_def in [
        ("current_tick", "INTEGER NOT NULL DEFAULT 0"),
        ("phase1_ticks_done", "INTEGER NOT NULL DEFAULT 0"),
        ("phase2_ticks_done", "INTEGER NOT NULL DEFAULT 0"),
        ("next_review_date", "DATE"),
        ("schedule_anchor_date", "DATE"),
        ("consecutive_missed_count", "INTEGER NOT NULL DEFAULT 0"),
        ("consecutive_forgot_count", "INTEGER NOT NULL DEFAULT 0"),
        ("phase2_regression_active", "BOOLEAN NOT NULL DEFAULT false"),
        ("phase2_regression_dismissed", "BOOLEAN NOT NULL DEFAULT false"),
        ("regression_ticks_done", "INTEGER NOT NULL DEFAULT 0"),
        ("srs_ease_factor", "DOUBLE PRECISION"),
        ("srs_interval_days", "INTEGER"),
        ("srs_repetitions", "INTEGER NOT NULL DEFAULT 0"),
        ("last_reviewed_at", "TIMESTAMPTZ"),
        ("queued_at", "TIMESTAMPTZ"),
        ("introduced_at", "TIMESTAMPTZ"),
        ("phase1_completed_at", "TIMESTAMPTZ"),
        ("graduated_at", "TIMESTAMPTZ"),
        ("deleted_at", "TIMESTAMPTZ"),
    ]:
        col_name, col_type = col_def
        op.execute(f"""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_card_progress' AND column_name = '{col_name}'
                ) THEN
                    ALTER TABLE user_card_progress ADD COLUMN {col_name} {col_type};
                END IF;
            END $$
        """)


def downgrade() -> None:
    # No-op: we don't remove columns in downgrade for this fix
    pass
