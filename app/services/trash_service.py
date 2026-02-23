"""Service layer for the user-facing Trash feature (soft-deleted content)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.flashcard import Flashcard
from app.models.sub_category import SubCategory
from app.models.user_card_progress import UserCardProgress
from app.schemas.trash import (
    TrashCategoryItem,
    TrashFlashcardItem,
    TrashResponse,
    TrashSubCategoryItem,
)


def _cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=settings.TRASH_RETENTION_DAYS)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def list_trash(db: Session, owner_id: int) -> TrashResponse:
    cutoff = _cutoff()

    deleted_categories = db.scalars(
        select(Category).where(
            Category.owner_id == owner_id,
            Category.deleted_at.isnot(None),
            Category.deleted_at >= cutoff,
        )
    ).all()

    # Subcategories deleted individually (parent category is still alive)
    deleted_subs = db.scalars(
        select(SubCategory)
        .join(Category, SubCategory.category_id == Category.id)
        .where(
            SubCategory.owner_id == owner_id,
            SubCategory.deleted_at.isnot(None),
            SubCategory.deleted_at >= cutoff,
            Category.deleted_at.is_(None),
        )
    ).all()

    # Flashcards deleted individually (parent subcategory is still alive)
    deleted_cards = db.scalars(
        select(Flashcard)
        .join(SubCategory, Flashcard.sub_category_id == SubCategory.id)
        .where(
            Flashcard.owner_id == owner_id,
            Flashcard.deleted_at.isnot(None),
            Flashcard.deleted_at >= cutoff,
            SubCategory.deleted_at.is_(None),
        )
    ).all()

    category_items = [
        TrashCategoryItem(
            id=c.id,
            title=c.title,
            description=c.description,
            deleted_at=c.deleted_at,
        )
        for c in deleted_categories
    ]
    sub_items = [
        TrashSubCategoryItem(
            id=s.id,
            title=s.title,
            description=s.description,
            category_id=s.category_id,
            deleted_at=s.deleted_at,
        )
        for s in deleted_subs
    ]
    card_items = [
        TrashFlashcardItem(
            id=c.id,
            sub_category_id=c.sub_category_id,
            front_preview=_truncate(c.front_text),
            deleted_at=c.deleted_at,
        )
        for c in deleted_cards
    ]

    total = len(category_items) + len(sub_items) + len(card_items)
    return TrashResponse(
        categories=category_items,
        subcategories=sub_items,
        flashcards=card_items,
        total=total,
    )


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_category(db: Session, category_id: int, owner_id: int) -> None:
    category = db.get(Category, category_id)
    if category is None or category.owner_id != owner_id or category.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in trash.")
    if category.deleted_at < _cutoff():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Trash retention period has expired for this item.")

    category.deleted_at = None

    # Restore all subcategories and flashcards belonging to this category
    subs = db.scalars(
        select(SubCategory).where(SubCategory.category_id == category_id)
    ).all()
    for sub in subs:
        if sub.deleted_at is not None:
            sub.deleted_at = None
        cards = db.scalars(
            select(Flashcard).where(Flashcard.sub_category_id == sub.id)
        ).all()
        for card in cards:
            if card.deleted_at is not None:
                card.deleted_at = None

    db.commit()


def restore_subcategory(db: Session, sub_id: int, owner_id: int) -> None:
    sub = db.get(SubCategory, sub_id)
    if sub is None or sub.owner_id != owner_id or sub.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in trash.")
    if sub.deleted_at < _cutoff():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Trash retention period has expired for this item.")

    # Ensure parent category is active
    parent = db.get(Category, sub.category_id)
    if parent is None or parent.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot restore: the parent category has been deleted.",
        )

    sub.deleted_at = None

    # Restore all flashcards inside
    cards = db.scalars(
        select(Flashcard).where(Flashcard.sub_category_id == sub_id)
    ).all()
    for card in cards:
        if card.deleted_at is not None:
            card.deleted_at = None

    db.commit()


def restore_flashcard(db: Session, card_id: int, owner_id: int) -> None:
    card = db.get(Flashcard, card_id)
    if card is None or card.owner_id != owner_id or card.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in trash.")
    if card.deleted_at < _cutoff():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Trash retention period has expired for this item.")

    # Ensure parent subcategory is active
    sub = db.get(SubCategory, card.sub_category_id)
    if sub is None or sub.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot restore: the parent subcategory has been deleted.",
        )

    card.deleted_at = None
    # Restore user progress for this card so ensure_subcategory_initialized doesn't try to re-insert (unique violation)
    for prog in db.scalars(
        select(UserCardProgress).where(
            UserCardProgress.flashcard_id == card_id,
            UserCardProgress.deleted_at.isnot(None),
        )
    ).all():
        prog.deleted_at = None
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str | None, max_len: int = 80) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[:max_len] + "…"
