"""Service layer for Category CRUD and ownership enforcement."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.flashcard import Flashcard
from app.models.sub_category import SubCategory
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_owned(category: Category | None, owner_id: int) -> Category:
    if category is None or category.owner_id != owner_id or category.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )
    return category


def _subcategory_count(db: Session, category_id: int) -> int:
    return db.scalar(
        select(func.count(SubCategory.id)).where(
            SubCategory.category_id == category_id,
            SubCategory.deleted_at.is_(None),
        )
    ) or 0


def _flashcard_count_for_category(db: Session, category_id: int) -> int:
    return db.scalar(
        select(func.count(Flashcard.id))
        .join(SubCategory, Flashcard.sub_category_id == SubCategory.id)
        .where(
            SubCategory.category_id == category_id,
            SubCategory.deleted_at.is_(None),
            Flashcard.deleted_at.is_(None),
        )
    ) or 0


def _to_response(db: Session, category: Category) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        title=category.title,
        description=category.description,
        subcategory_count=_subcategory_count(db, category.id),
        flashcard_count=_flashcard_count_for_category(db, category.id),
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_categories(
    db: Session,
    owner_id: int,
    *,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> CategoryListResponse:
    per_page = min(per_page, 100)
    page = max(page, 1)

    base_q = (
        select(Category)
        .where(Category.owner_id == owner_id, Category.deleted_at.is_(None))
        .order_by(Category.created_at.desc())
    )
    if search:
        term = f"%{search.strip()}%"
        base_q = base_q.where(Category.title.ilike(term))

    total: int = db.scalar(
        select(func.count()).select_from(base_q.subquery())
    ) or 0

    rows = db.scalars(base_q.offset((page - 1) * per_page).limit(per_page)).all()
    pages = math.ceil(total / per_page) if total else 1

    return CategoryListResponse(
        items=[_to_response(db, c) for c in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


def get_category(db: Session, category_id: int, owner_id: int) -> CategoryResponse:
    category = db.get(Category, category_id)
    _assert_owned(category, owner_id)
    return _to_response(db, category)


def create_category(
    db: Session,
    owner_id: int,
    data: CategoryCreate,
) -> CategoryResponse:
    title = data.title.strip()

    # Enforce uniqueness among active categories for this owner
    existing = db.scalar(
        select(Category).where(
            Category.owner_id == owner_id,
            Category.title == title,
            Category.deleted_at.is_(None),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a category with this title.",
        )

    category = Category(
        owner_id=owner_id,
        title=title,
        description=data.description,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _to_response(db, category)


def update_category(
    db: Session,
    category_id: int,
    owner_id: int,
    data: CategoryUpdate,
) -> CategoryResponse:
    category = db.get(Category, category_id)
    _assert_owned(category, owner_id)

    if data.title is not None:
        new_title = data.title.strip()
        # Check uniqueness only when the title actually changes
        if new_title != category.title:
            clash = db.scalar(
                select(Category).where(
                    Category.owner_id == owner_id,
                    Category.title == new_title,
                    Category.deleted_at.is_(None),
                    Category.id != category_id,
                )
            )
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You already have a category with this title.",
                )
        category.title = new_title

    if "description" in data.model_fields_set:
        category.description = data.description

    category.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(category)
    return _to_response(db, category)


def delete_category(db: Session, category_id: int, owner_id: int) -> None:
    category = db.get(Category, category_id)
    _assert_owned(category, owner_id)

    now = datetime.now(timezone.utc)
    category.deleted_at = now

    # Cascade soft-delete all subcategories and their flashcards
    subcategories = db.scalars(
        select(SubCategory).where(
            SubCategory.category_id == category_id,
            SubCategory.deleted_at.is_(None),
        )
    ).all()

    for sub in subcategories:
        sub.deleted_at = now
        flashcards = db.scalars(
            select(Flashcard).where(
                Flashcard.sub_category_id == sub.id,
                Flashcard.deleted_at.is_(None),
            )
        ).all()
        for card in flashcards:
            card.deleted_at = now

    db.commit()
