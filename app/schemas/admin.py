from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


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
