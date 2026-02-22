from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.sub_category import SubCategory
    from app.models.user import User


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
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

    owner: Mapped["User"] = relationship(back_populates="categories")
    sub_categories: Mapped[list["SubCategory"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("title")
    def validate_title(self, key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("category title cannot be blank")
        return normalized
