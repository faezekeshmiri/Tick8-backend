from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.category import Category


_USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{3,50}$")
_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(username)) > 0",
            name="ck_users_username_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(email)) > 0",
            name="ck_users_email_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(password)) > 0",
            name="ck_users_password_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("username")
    def validate_username(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("username cannot be blank")
        if not _USERNAME_REGEX.fullmatch(normalized):
            raise ValueError(
                "username must be 3-50 characters and contain only letters, numbers, or underscores"
            )
        return normalized

    @validates("email")
    def validate_email(self, key: str, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email cannot be blank")
        if not _EMAIL_REGEX.fullmatch(normalized):
            raise ValueError("email must be a valid email address")
        return normalized

    @validates("password")
    def validate_password(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password cannot be blank")
        if len(value) < 4:
            raise ValueError("password must be at least 4 characters long")
        return value
