from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_admin
from app.db.session import get_db
from app.models.category import Category
from app.models.flashcard import Flashcard
from app.models.sub_category import SubCategory
from app.models.tick_result import TickResult
from app.models.user import User, UserRole
from app.models.user_card_progress import UserCardProgress, ProgressStatus
from app.schemas.admin import (
    AdminCategorySummary,
    AdminStats,
    AdminSubCategorySummary,
    AdminUserDetail,
    AdminUserDetailStats,
    AdminUserListResponse,
    AdminUserView,
)
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardListResponse,
    FlashcardReorderRequest,
    FlashcardResponse,
    FlashcardUpdate,
)
from app.schemas.subcategory import (
    SubCategoryCreate,
    SubCategoryListResponse,
    SubCategoryResponse,
    SubCategoryUpdate,
)
from app.services import category_service, flashcard_service, subcategory_service

router = APIRouter()


def get_target_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminStats:
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    suspended_users = db.query(User).filter(User.is_active.is_(False)).count()
    admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        admin_count=admin_count,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: str | None = Query(default=None, description="Search by name or email"),
    role: UserRole | None = Query(default=None, description="Filter by role"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminUserListResponse:
    query = db.query(User)
    if search:
        term = f"%{search.lower()}%"
        query = query.filter(
            User.display_name.ilike(term) | User.email.ilike(term)
        )
    if role is not None:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AdminUserListResponse(
        users=[AdminUserView.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminUserDetail:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Content counts (non-deleted only)
    categories_count = (
        db.query(func.count(Category.id))
        .where(Category.owner_id == user_id, Category.deleted_at.is_(None))
        .scalar()
        or 0
    )
    subcategories_count = (
        db.query(func.count(SubCategory.id))
        .where(SubCategory.owner_id == user_id, SubCategory.deleted_at.is_(None))
        .scalar()
        or 0
    )
    flashcards_count = (
        db.query(func.count(Flashcard.id))
        .where(Flashcard.owner_id == user_id, Flashcard.deleted_at.is_(None))
        .scalar()
        or 0
    )

    # Progress counts for this user (non-deleted progress only)
    cards_with_progress_count = (
        db.query(func.count(UserCardProgress.id))
        .where(
            UserCardProgress.user_id == user_id,
            UserCardProgress.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    total_reviews_count = (
        db.query(func.count(TickResult.id))
        .join(UserCardProgress, TickResult.user_card_progress_id == UserCardProgress.id)
        .where(UserCardProgress.user_id == user_id, UserCardProgress.deleted_at.is_(None))
        .scalar()
        or 0
    )

    status_counts = (
        db.query(UserCardProgress.status, func.count(UserCardProgress.id))
        .where(UserCardProgress.user_id == user_id, UserCardProgress.deleted_at.is_(None))
        .group_by(UserCardProgress.status)
        .all()
    )
    by_status = {s.value: c for s, c in status_counts}
    stats = AdminUserDetailStats(
        categories_count=categories_count,
        subcategories_count=subcategories_count,
        flashcards_count=flashcards_count,
        cards_with_progress_count=cards_with_progress_count,
        total_reviews_count=total_reviews_count,
        progress_pending=by_status.get(ProgressStatus.PENDING.value, 0),
        progress_phase1=by_status.get(ProgressStatus.PHASE1.value, 0),
        progress_phase2=by_status.get(ProgressStatus.PHASE2.value, 0),
        progress_graduated=by_status.get(ProgressStatus.GRADUATED.value, 0),
        progress_long_term_mastered=by_status.get(ProgressStatus.LONG_TERM_MASTERED.value, 0),
    )

    # Categories with subcategories and card counts (non-deleted)
    categories_q = (
        db.query(Category)
        .where(Category.owner_id == user_id, Category.deleted_at.is_(None))
        .order_by(Category.created_at.asc())
    )
    categories_out: list[AdminCategorySummary] = []
    for cat in categories_q:
        subs = (
            db.query(SubCategory)
            .where(
                SubCategory.category_id == cat.id,
                SubCategory.deleted_at.is_(None),
            )
            .order_by(SubCategory.created_at.asc())
            .all()
        )
        sub_summaries: list[AdminSubCategorySummary] = []
        cat_flashcards = 0
        for sub in subs:
            card_count = (
                db.query(func.count(Flashcard.id))
                .where(Flashcard.sub_category_id == sub.id, Flashcard.deleted_at.is_(None))
                .scalar()
                or 0
            )
            cat_flashcards += card_count
            sub_summaries.append(
                AdminSubCategorySummary(
                    id=sub.id,
                    title=sub.title,
                    flashcards_count=card_count,
                    created_at=sub.created_at,
                )
            )
        categories_out.append(
            AdminCategorySummary(
                id=cat.id,
                title=cat.title,
                description=cat.description,
                subcategories_count=len(sub_summaries),
                flashcards_count=cat_flashcards,
                subcategories=sub_summaries,
                created_at=cat.created_at,
            )
        )

    return AdminUserDetail(
        user=AdminUserView.model_validate(user),
        stats=stats,
        categories=categories_out,
    )


@router.patch("/users/{user_id}/suspend", response_model=AdminUserView)
def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own account.",
        )
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend other administrators.",
        )
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/reactivate", response_model=AdminUserView)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/make-admin", response_model=AdminUserView)
def make_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an administrator.",
        )
    user.role = UserRole.ADMIN
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/remove-admin", response_model=AdminUserView)
def remove_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own administrator role.",
        )
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an administrator.",
        )
    user.role = UserRole.USER
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Admin CRUD for a user's content (categories, subcategories, flashcards)
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/categories", response_model=CategoryListResponse)
def admin_list_categories(
    user_id: int,
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> CategoryListResponse:
    return category_service.list_categories(
        db, target_user.id, search=search, page=page, per_page=per_page
    )


@router.post(
    "/users/{user_id}/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_category(
    user_id: int,
    data: CategoryCreate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> CategoryResponse:
    return category_service.create_category(db, target_user.id, data)


@router.get("/users/{user_id}/categories/{category_id}", response_model=CategoryResponse)
def admin_get_category(
    user_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> CategoryResponse:
    return category_service.get_category(db, category_id, target_user.id)


@router.patch(
    "/users/{user_id}/categories/{category_id}",
    response_model=CategoryResponse,
)
def admin_update_category(
    user_id: int,
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> CategoryResponse:
    return category_service.update_category(db, category_id, target_user.id, data)


@router.delete(
    "/users/{user_id}/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_category(
    user_id: int,
    category_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> None:
    category_service.delete_category(db, category_id, target_user.id)


@router.get(
    "/users/{user_id}/categories/{category_id}/subcategories",
    response_model=SubCategoryListResponse,
)
def admin_list_subcategories(
    user_id: int,
    category_id: int,
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> SubCategoryListResponse:
    return subcategory_service.list_subcategories(
        db, category_id, target_user.id, search=search, page=page, per_page=per_page
    )


@router.post(
    "/users/{user_id}/categories/{category_id}/subcategories",
    response_model=SubCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_subcategory(
    user_id: int,
    category_id: int,
    data: SubCategoryCreate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> SubCategoryResponse:
    return subcategory_service.create_subcategory(db, category_id, target_user.id, data)


@router.get("/users/{user_id}/subcategories/{sub_id}", response_model=SubCategoryResponse)
def admin_get_subcategory(
    user_id: int,
    sub_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> SubCategoryResponse:
    return subcategory_service.get_subcategory(db, sub_id, target_user.id)


@router.patch(
    "/users/{user_id}/subcategories/{sub_id}",
    response_model=SubCategoryResponse,
)
def admin_update_subcategory(
    user_id: int,
    sub_id: int,
    data: SubCategoryUpdate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> SubCategoryResponse:
    return subcategory_service.update_subcategory(db, sub_id, target_user.id, data)


@router.delete(
    "/users/{user_id}/subcategories/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_subcategory(
    user_id: int,
    sub_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> None:
    subcategory_service.delete_subcategory(db, sub_id, target_user.id)


@router.get(
    "/users/{user_id}/subcategories/{sub_id}/flashcards",
    response_model=FlashcardListResponse,
)
def admin_list_flashcards(
    user_id: int,
    sub_id: int,
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> FlashcardListResponse:
    return flashcard_service.list_flashcards(
        db, sub_id, target_user.id, search=search, page=page, per_page=per_page
    )


@router.post(
    "/users/{user_id}/subcategories/{sub_id}/flashcards",
    response_model=FlashcardResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_flashcard(
    user_id: int,
    sub_id: int,
    data: FlashcardCreate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> FlashcardResponse:
    return flashcard_service.create_flashcard(db, sub_id, target_user.id, data)


@router.post(
    "/users/{user_id}/subcategories/{sub_id}/flashcards/reorder",
    response_model=list[FlashcardResponse],
)
def admin_reorder_flashcards(
    user_id: int,
    sub_id: int,
    data: FlashcardReorderRequest,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> list[FlashcardResponse]:
    return flashcard_service.reorder_flashcards(db, sub_id, target_user.id, data)


@router.get("/users/{user_id}/flashcards/{card_id}", response_model=FlashcardResponse)
def admin_get_flashcard(
    user_id: int,
    card_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> FlashcardResponse:
    return flashcard_service.get_flashcard(db, card_id, target_user.id)


@router.patch(
    "/users/{user_id}/flashcards/{card_id}",
    response_model=FlashcardResponse,
)
def admin_update_flashcard(
    user_id: int,
    card_id: int,
    data: FlashcardUpdate,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> FlashcardResponse:
    return flashcard_service.update_flashcard(db, card_id, target_user.id, data)


@router.delete(
    "/users/{user_id}/flashcards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_flashcard(
    user_id: int,
    card_id: int,
    db: Session = Depends(get_db),
    target_user: User = Depends(get_target_user),
) -> None:
    flashcard_service.delete_flashcard(db, card_id, target_user.id)
