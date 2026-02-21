from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.sub_category import SubCategory
    from app.models.user import User


class CategoryStatus(str, Enum):
    ACTIVE = "Active"
    ARCHIVED = "Archived"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_categories_user_name"),
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_categories_name_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[CategoryStatus] = mapped_column(
        SAEnum(CategoryStatus, name="category_status_enum", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CategoryStatus.ACTIVE,
        server_default=CategoryStatus.ACTIVE.value,
    )

    user: Mapped["User"] = relationship(back_populates="categories")
    sub_categories: Mapped[list["SubCategory"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("category name cannot be blank")
        return normalized
