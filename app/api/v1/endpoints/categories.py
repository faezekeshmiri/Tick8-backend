from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.services import category_service

router = APIRouter()


@router.get("", response_model=CategoryListResponse)
def list_categories(
    search: str | None = Query(default=None, description="Filter by title (case-insensitive)"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryListResponse:
    return category_service.list_categories(
        db, current_user.id, search=search, page=page, per_page=per_page
    )


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryResponse:
    return category_service.create_category(db, current_user.id, data)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryResponse:
    return category_service.get_category(db, category_id, current_user.id)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryResponse:
    return category_service.update_category(db, category_id, current_user.id, data)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    category_service.delete_category(db, category_id, current_user.id)
