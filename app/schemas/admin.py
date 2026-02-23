from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    admin_count: int


class AdminUserView(BaseModel):
    id: int
    display_name: str
    email: str
    role: UserRole
    is_active: bool
    is_email_verified: bool
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    users: list[AdminUserView]
    total: int
    page: int
    page_size: int


# --- User detail (for admin view) ---


class AdminUserDetailStats(BaseModel):
    categories_count: int
    subcategories_count: int
    flashcards_count: int
    cards_with_progress_count: int
    total_reviews_count: int
    progress_pending: int
    progress_phase1: int
    progress_phase2: int
    progress_graduated: int
    progress_long_term_mastered: int


class AdminSubCategorySummary(BaseModel):
    id: int
    title: str
    flashcards_count: int
    created_at: datetime


class AdminCategorySummary(BaseModel):
    id: int
    title: str
    description: str | None
    subcategories_count: int
    flashcards_count: int
    subcategories: list[AdminSubCategorySummary]
    created_at: datetime


class AdminUserDetail(BaseModel):
    user: AdminUserView
    stats: AdminUserDetailStats
    categories: list[AdminCategorySummary]
