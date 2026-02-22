"""Service layer for Flashcard CRUD, ordering, and ownership enforcement."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.flashcard import ContentType, Flashcard
from app.models.sub_category import SubCategory
from app.models.user_card_progress import UserCardProgress
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardListResponse,
    FlashcardReorderRequest,
    FlashcardResponse,
    FlashcardSideResponse,
    FlashcardUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_subcategory_owned(db: Session, sub_id: int, owner_id: int) -> SubCategory:
    sub = db.get(SubCategory, sub_id)
    if sub is None or sub.owner_id != owner_id or sub.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategory not found.",
        )
    return sub


def _assert_owned(card: Flashcard | None, owner_id: int) -> Flashcard:
    if card is None or card.owner_id != owner_id or card.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found.",
        )
    return card


def _to_response(card: Flashcard) -> FlashcardResponse:
    return FlashcardResponse(
        id=card.id,
        sub_category_id=card.sub_category_id,
        front=FlashcardSideResponse(
            type=card.front_type,
            text=card.front_text,
            image_url=card.front_image_url,
        ),
        back=FlashcardSideResponse(
            type=card.back_type,
            text=card.back_text,
            image_url=card.back_image_url,
        ),
        order_index=card.order_index,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def _next_order_index(db: Session, sub_id: int) -> int:
    max_idx = db.scalar(
        select(func.max(Flashcard.order_index)).where(
            Flashcard.sub_category_id == sub_id,
            Flashcard.deleted_at.is_(None),
        )
    )
    return (max_idx or 0) + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_flashcards(
    db: Session,
    sub_id: int,
    owner_id: int,
    *,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> FlashcardListResponse:
    _assert_subcategory_owned(db, sub_id, owner_id)

    per_page = min(per_page, 100)
    page = max(page, 1)

    base_q = (
        select(Flashcard)
        .where(
            Flashcard.sub_category_id == sub_id,
            Flashcard.owner_id == owner_id,
            Flashcard.deleted_at.is_(None),
        )
        .order_by(Flashcard.order_index.asc(), Flashcard.created_at.asc())
    )
    if search:
        term = f"%{search.strip()}%"
        base_q = base_q.where(
            Flashcard.front_text.ilike(term) | Flashcard.back_text.ilike(term)
        )

    total: int = db.scalar(
        select(func.count()).select_from(base_q.subquery())
    ) or 0

    rows = db.scalars(base_q.offset((page - 1) * per_page).limit(per_page)).all()
    pages = math.ceil(total / per_page) if total else 1

    return FlashcardListResponse(
        items=[_to_response(c) for c in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


def get_flashcard(db: Session, card_id: int, owner_id: int) -> FlashcardResponse:
    card = db.get(Flashcard, card_id)
    _assert_owned(card, owner_id)
    return _to_response(card)


def create_flashcard(
    db: Session,
    sub_id: int,
    owner_id: int,
    data: FlashcardCreate,
) -> FlashcardResponse:
    _assert_subcategory_owned(db, sub_id, owner_id)

    # Enforce flashcard limit
    current_count: int = db.scalar(
        select(func.count(Flashcard.id)).where(
            Flashcard.sub_category_id == sub_id,
            Flashcard.deleted_at.is_(None),
        )
    ) or 0
    if current_count >= settings.MAX_FLASHCARDS_PER_SUBCATEGORY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"This subcategory has reached the limit of "
                f"{settings.MAX_FLASHCARDS_PER_SUBCATEGORY} flashcards."
            ),
        )

    card = Flashcard(
        sub_category_id=sub_id,
        owner_id=owner_id,
        front_type=data.front.type,
        front_text=data.front.text,
        front_image_url=data.front.image_url,
        back_type=data.back.type,
        back_text=data.back.text,
        back_image_url=data.back.image_url,
        order_index=_next_order_index(db, sub_id),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return _to_response(card)


def update_flashcard(
    db: Session,
    card_id: int,
    owner_id: int,
    data: FlashcardUpdate,
) -> FlashcardResponse:
    card = db.get(Flashcard, card_id)
    _assert_owned(card, owner_id)

    if data.front is not None:
        card.front_type = data.front.type
        card.front_text = data.front.text
        card.front_image_url = data.front.image_url

    if data.back is not None:
        card.back_type = data.back.type
        card.back_text = data.back.text
        card.back_image_url = data.back.image_url

    card.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(card)
    return _to_response(card)


def delete_flashcard(db: Session, card_id: int, owner_id: int) -> None:
    card = db.get(Flashcard, card_id)
    _assert_owned(card, owner_id)
    now = datetime.now(timezone.utc)
    card.deleted_at = now
    # Soft-delete all user progress for this card (Story 3)
    for prog in db.scalars(
        select(UserCardProgress).where(
            UserCardProgress.flashcard_id == card_id,
            UserCardProgress.deleted_at.is_(None),
        )
    ).all():
        prog.deleted_at = now
    db.commit()


def reorder_flashcards(
    db: Session,
    sub_id: int,
    owner_id: int,
    data: FlashcardReorderRequest,
) -> list[FlashcardResponse]:
    _assert_subcategory_owned(db, sub_id, owner_id)

    requested_ids = {item.id for item in data.flashcards}

    # Load all requested cards and verify they belong to this subcategory/owner
    cards: dict[int, Flashcard] = {}
    for item in data.flashcards:
        card = db.get(Flashcard, item.id)
        if (
            card is None
            or card.owner_id != owner_id
            or card.sub_category_id != sub_id
            or card.deleted_at is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flashcard {item.id} not found in this subcategory.",
            )
        cards[item.id] = card

    # Apply new order indexes
    now = datetime.now(timezone.utc)
    for item in data.flashcards:
        cards[item.id].order_index = item.order_index
        cards[item.id].updated_at = now

    db.commit()

    # Return all flashcards in the subcategory in new order
    all_cards = db.scalars(
        select(Flashcard)
        .where(
            Flashcard.sub_category_id == sub_id,
            Flashcard.owner_id == owner_id,
            Flashcard.deleted_at.is_(None),
        )
        .order_by(Flashcard.order_index.asc())
    ).all()
    return [_to_response(c) for c in all_cards]
