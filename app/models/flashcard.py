from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.sub_category import SubCategory
    from app.models.user import User


class ContentType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"


# Shared SA enum type; create_type=False because DDL is managed by migrations.
_content_type_sa = SAEnum(
    ContentType,
    name="content_type_enum",
    values_callable=lambda obj: [e.value for e in obj],
    create_type=False,
)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sub_category_id: Mapped[int] = mapped_column(
        ForeignKey("sub_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    front_type: Mapped[ContentType] = mapped_column(
        _content_type_sa,
        nullable=False,
        default=ContentType.TEXT,
        server_default=ContentType.TEXT.value,
    )
    front_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    front_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    back_type: Mapped[ContentType] = mapped_column(
        _content_type_sa,
        nullable=False,
        default=ContentType.TEXT,
        server_default=ContentType.TEXT.value,
    )
    back_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    back_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sub_category: Mapped["SubCategory"] = relationship(back_populates="flashcards")
    # owner relationship is unidirectional (no back_populates on User)
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])

    @validates("front_text", "back_text")
    def validate_text_not_only_whitespace(self, key: str, value: str | None) -> str | None:
        if value is not None:
            return value.strip() or None
        return value
