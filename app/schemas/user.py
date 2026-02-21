import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import UserRole

_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


class UserPublic(BaseModel):
    id: int
    display_name: str
    email: str
    role: UserRole
    is_email_verified: bool
    avatar_url: str | None
    pending_email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be blank")
        if len(stripped) > 100:
            raise ValueError("Display name must be 100 characters or fewer")
        return stripped


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    current_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not _PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain at least "
                "one uppercase letter and one number"
            )
        return v
