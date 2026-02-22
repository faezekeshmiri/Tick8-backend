from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.flashcard import Flashcard
    from app.models.user import User


class SubCategory(Base):
    __tablename__ = "sub_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped["Category"] = relationship(back_populates="sub_categories")
    # owner relationship is unidirectional (no back_populates on User to avoid cascade conflicts)
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="sub_category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("title")
    def validate_title(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("subcategory title cannot be blank")
        return normalized
