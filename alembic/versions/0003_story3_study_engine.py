"""Story 3 – Tick 8 Study Engine (user_card_progress, tick_results, user_study_settings)

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-22

"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Enums for progress status and tick result
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE progress_status_enum AS ENUM ("
        "'pending', 'phase1', 'phase2', 'graduated', 'long_term_mastered')"
    )
    op.execute(
        "CREATE TYPE tick_result_kind_enum AS ENUM ('remembered', 'difficult', 'forgot')"
    )

    # ------------------------------------------------------------------
    # 2. user_study_settings — 1:1 per user
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE user_study_settings (
            user_id                 INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            daily_new_card_limit    INTEGER NOT NULL DEFAULT 20,
            session_cap             INTEGER NOT NULL DEFAULT 50,
            phase_regression_enabled BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("CREATE INDEX ix_user_study_settings_user_id ON user_study_settings (user_id)")

    # ------------------------------------------------------------------
    # 3. user_card_progress — one per (user, flashcard)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE user_card_progress (
            id                      SERIAL PRIMARY KEY,
            user_id                 INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            flashcard_id            INTEGER NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
            status                  progress_status_enum NOT NULL DEFAULT 'pending',
            current_tick           INTEGER NOT NULL DEFAULT 0,
            phase1_ticks_done       INTEGER NOT NULL DEFAULT 0,
            phase2_ticks_done       INTEGER NOT NULL DEFAULT 0,
            next_review_date        DATE,
            schedule_anchor_date    DATE,
            consecutive_missed_count INTEGER NOT NULL DEFAULT 0,
            consecutive_forgot_count INTEGER NOT NULL DEFAULT 0,
            phase2_regression_active BOOLEAN NOT NULL DEFAULT false,
            phase2_regression_dismissed BOOLEAN NOT NULL DEFAULT false,
            regression_ticks_done  INTEGER NOT NULL DEFAULT 0,
            srs_ease_factor        DOUBLE PRECISION,
            srs_interval_days       INTEGER,
            srs_repetitions         INTEGER NOT NULL DEFAULT 0,
            last_reviewed_at        TIMESTAMPTZ,
            queued_at              TIMESTAMPTZ,
            introduced_at          TIMESTAMPTZ,
            phase1_completed_at     TIMESTAMPTZ,
            graduated_at           TIMESTAMPTZ,
            deleted_at             TIMESTAMPTZ,
            CONSTRAINT uq_user_card_progress_user_flashcard UNIQUE (user_id, flashcard_id)
        )
    """)
    op.execute("CREATE INDEX ix_user_card_progress_id ON user_card_progress (id)")
    op.execute("CREATE INDEX ix_user_card_progress_user_id ON user_card_progress (user_id)")
    op.execute("CREATE INDEX ix_user_card_progress_flashcard_id ON user_card_progress (flashcard_id)")
    op.execute("CREATE INDEX ix_user_card_progress_next_review_date ON user_card_progress (next_review_date)")
    op.execute("CREATE INDEX ix_user_card_progress_status ON user_card_progress (status)")
    op.execute("CREATE INDEX ix_user_card_progress_deleted_at ON user_card_progress (deleted_at)")

    # ------------------------------------------------------------------
    # 4. tick_results — append-only tick log
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE tick_results (
            id                      SERIAL PRIMARY KEY,
            user_card_progress_id   INTEGER NOT NULL REFERENCES user_card_progress(id) ON DELETE CASCADE,
            tick_number             INTEGER NOT NULL,
            phase                   INTEGER NOT NULL,
            reviewed_on_date        DATE NOT NULL,
            result                  tick_result_kind_enum NOT NULL,
            response_time_ms        INTEGER,
            is_regression_tick      BOOLEAN NOT NULL DEFAULT false,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_tick_results_id ON tick_results (id)")
    op.execute("CREATE INDEX ix_tick_results_user_card_progress_id ON tick_results (user_card_progress_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tick_results CASCADE")
    op.execute("DROP TABLE IF EXISTS user_card_progress CASCADE")
    op.execute("DROP TABLE IF EXISTS user_study_settings CASCADE")
    op.execute("DROP TYPE IF EXISTS tick_result_kind_enum")
    op.execute("DROP TYPE IF EXISTS progress_status_enum")
