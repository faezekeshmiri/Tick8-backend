from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.subcategory import (
    SubCategoryCreate,
    SubCategoryListResponse,
    SubCategoryResponse,
    SubCategoryUpdate,
)
from app.services import subcategory_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Nested under /categories/{category_id}/subcategories
# ---------------------------------------------------------------------------

@router.get("/categories/{category_id}/subcategories", response_model=SubCategoryListResponse)
def list_subcategories(
    category_id: int,
    search: str | None = Query(default=None, description="Filter by title (case-insensitive)"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubCategoryListResponse:
    return subcategory_service.list_subcategories(
        db, category_id, current_user.id, search=search, page=page, per_page=per_page
    )


@router.post(
    "/categories/{category_id}/subcategories",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subcategory(
    category_id: int,
    data: SubCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubCategoryResponse:
    return subcategory_service.create_subcategory(db, category_id, current_user.id, data)


# ---------------------------------------------------------------------------
# Direct access by subcategory ID
# ---------------------------------------------------------------------------

@router.get("/subcategories/{sub_id}", response_model=SubCategoryResponse)
def get_subcategory(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubCategoryResponse:
    return subcategory_service.get_subcategory(db, sub_id, current_user.id)


@router.patch("/subcategories/{sub_id}", response_model=SubCategoryResponse)
def update_subcategory(
    sub_id: int,
    data: SubCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubCategoryResponse:
    return subcategory_service.update_subcategory(db, sub_id, current_user.id, data)


@router.delete("/subcategories/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subcategory(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    subcategory_service.delete_subcategory(db, sub_id, current_user.id)
