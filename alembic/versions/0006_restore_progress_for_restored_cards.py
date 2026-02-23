"""Restore user_card_progress for cards that were restored from trash.

Cards restored before we fixed restore_flashcard() had their progress rows left
soft-deleted, causing UniqueViolation when loading the subcategory. This
one-time data fix sets deleted_at = NULL on those progress rows where the
flashcard is no longer deleted.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-22

"""
from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE user_card_progress ucp
        SET deleted_at = NULL
        FROM flashcards f
        WHERE ucp.flashcard_id = f.id
          AND f.deleted_at IS NULL
          AND ucp.deleted_at IS NOT NULL
    """)


def downgrade() -> None:
    # No-op: we cannot safely re-soft-delete without knowing when the card was restored
    pass
