"""Immutable append-only log of each tick response (remembered/forgot). Legacy DB may still have 'difficult'."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user_card_progress import UserCardProgress


class TickResultKind(str, enum.Enum):
    REMEMBERED = "remembered"
    DIFFICULT = "difficult"
    FORGOT = "forgot"


_tick_result_kind_sa = SAEnum(
    TickResultKind,
    name="tick_result_kind_enum",
    values_callable=lambda obj: [e.value for e in obj],
    create_type=False,
)


class TickResult(Base):
    __tablename__ = "tick_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_card_progress_id: Mapped[int] = mapped_column(
        ForeignKey("user_card_progress.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    reviewed_on_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[TickResultKind] = mapped_column(
        _tick_result_kind_sa,
        nullable=False,
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_regression_tick: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user_card_progress: Mapped["UserCardProgress"] = relationship(
        back_populates="tick_results"
    )
