"""Service layer for SubCategory CRUD and ownership enforcement."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.flashcard import Flashcard
from app.models.sub_category import SubCategory
from app.schemas.subcategory import (
    SubCategoryCreate,
    SubCategoryListResponse,
    SubCategoryResponse,
    SubCategoryUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_category_owned(db: Session, category_id: int, owner_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.owner_id != owner_id or category.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    return category


def _assert_owned(sub: SubCategory | None, owner_id: int) -> SubCategory:
    if sub is None or sub.owner_id != owner_id or sub.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategory not found.",
        )
    return sub


def _flashcard_count(db: Session, sub_category_id: int) -> int:
    return db.scalar(
        select(func.count(Flashcard.id)).where(
            Flashcard.sub_category_id == sub_category_id,
            Flashcard.deleted_at.is_(None),
        )
    ) or 0


def _to_response(db: Session, sub: SubCategory) -> SubCategoryResponse:
    return SubCategoryResponse(
        id=sub.id,
        category_id=sub.category_id,
        title=sub.title,
        description=sub.description,
        flashcard_count=_flashcard_count(db, sub.id),
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_subcategories(
    db: Session,
    category_id: int,
    owner_id: int,
    *,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> SubCategoryListResponse:
    # Verify the parent category belongs to the user
    _assert_category_owned(db, category_id, owner_id)

    per_page = min(per_page, 100)
    page = max(page, 1)

    base_q = (
        select(SubCategory)
        .where(
            SubCategory.category_id == category_id,
            SubCategory.owner_id == owner_id,
            SubCategory.deleted_at.is_(None),
        )
        .order_by(SubCategory.created_at.asc())
    )
    if search:
        term = f"%{search.strip()}%"
        base_q = base_q.where(SubCategory.title.ilike(term))

    total: int = db.scalar(
        select(func.count()).select_from(base_q.subquery())
    ) or 0

    rows = db.scalars(base_q.offset((page - 1) * per_page).limit(per_page)).all()
    pages = math.ceil(total / per_page) if total else 1

    return SubCategoryListResponse(
        items=[_to_response(db, s) for s in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


def get_subcategory(db: Session, sub_id: int, owner_id: int) -> SubCategoryResponse:
    sub = db.get(SubCategory, sub_id)
    _assert_owned(sub, owner_id)
    return _to_response(db, sub)


def create_subcategory(
    db: Session,
    category_id: int,
    owner_id: int,
    data: SubCategoryCreate,
) -> SubCategoryResponse:
    _assert_category_owned(db, category_id, owner_id)
    title = data.title.strip()

    existing = db.scalar(
        select(SubCategory).where(
            SubCategory.category_id == category_id,
            SubCategory.title == title,
            SubCategory.deleted_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A subcategory with this title already exists in this category.",
        )

    sub = SubCategory(
        category_id=category_id,
        owner_id=owner_id,
        title=title,
        description=data.description,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return _to_response(db, sub)


def update_subcategory(
    db: Session,
    sub_id: int,
    owner_id: int,
    data: SubCategoryUpdate,
) -> SubCategoryResponse:
    sub = db.get(SubCategory, sub_id)
    _assert_owned(sub, owner_id)

    if data.title is not None:
        new_title = data.title.strip()
        if new_title != sub.title:
            clash = db.scalar(
                select(SubCategory).where(
                    SubCategory.category_id == sub.category_id,
                    SubCategory.title == new_title,
                    SubCategory.deleted_at.is_(None),
                    SubCategory.id != sub_id,
                )
            )
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A subcategory with this title already exists in this category.",
                )
        sub.title = new_title

    if "description" in data.model_fields_set:
        sub.description = data.description

    sub.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sub)
    return _to_response(db, sub)


def delete_subcategory(db: Session, sub_id: int, owner_id: int) -> None:
    sub = db.get(SubCategory, sub_id)
    _assert_owned(sub, owner_id)

    now = datetime.now(timezone.utc)
    sub.deleted_at = now

    # Cascade soft-delete all flashcards in this subcategory
    flashcards = db.scalars(
        select(Flashcard).where(
            Flashcard.sub_category_id == sub_id,
            Flashcard.deleted_at.is_(None),
        )
    ).all()
    for card in flashcards:
        card.deleted_at = now

    db.commit()
