from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.token import EmailVerificationToken, PasswordResetToken, RefreshToken


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


_EMAIL_REGEX_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(display_name)) >= 1",
            name="ck_users_display_name_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(email)) > 0",
            name="ck_users_email_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(hashed_password)) > 0",
            name="ck_users_hashed_password_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role_enum", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pending_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    categories: Mapped[list["Category"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("email")
    def validate_email(self, key: str, value: str) -> str:
        import re

        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email cannot be blank")
        if not re.fullmatch(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise ValueError("email must be a valid email address")
        return normalized

    @validates("display_name")
    def validate_display_name(self, key: str, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("display name cannot be blank")
        if len(stripped) > 100:
            raise ValueError("display name must be 100 characters or fewer")
        return stripped

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until
