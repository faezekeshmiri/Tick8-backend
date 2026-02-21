from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.category import Category


_HEX_COLOR_REGEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


class SubCategory(Base):
    __tablename__ = "sub_categories"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_sub_categories_category_name"),
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_sub_categories_name_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(color)) > 0",
            name="ck_sub_categories_color_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)

    category: Mapped["Category"] = relationship(back_populates="sub_categories")
    # Flashcard relationship will be added once the Flashcard model is introduced.

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("sub-category name cannot be blank")
        return normalized

    @validates("color")
    def validate_color(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("sub-category color cannot be blank")
        if not _HEX_COLOR_REGEX.fullmatch(normalized):
            raise ValueError("color must be a valid HEX color code (e.g. #FFAA00)")
        return normalized.upper()
