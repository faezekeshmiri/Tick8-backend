"""Per-user progress and scheduling state for a single flashcard (Tick 8 + SRS)."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.flashcard import Flashcard
    from app.models.tick_result import TickResult
    from app.models.user import User


class ProgressStatus(str, enum.Enum):
    PENDING = "pending"
    PHASE1 = "phase1"
    PHASE2 = "phase2"
    GRADUATED = "graduated"
    LONG_TERM_MASTERED = "long_term_mastered"


_progress_status_sa = SAEnum(
    ProgressStatus,
    name="progress_status_enum",
    values_callable=lambda obj: [e.value for e in obj],
    create_type=False,
)


class UserCardProgress(Base):
    __tablename__ = "user_card_progress"
    __table_args__ = (UniqueConstraint("user_id", "flashcard_id", name="uq_user_card_progress_user_flashcard"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flashcard_id: Mapped[int] = mapped_column(
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[ProgressStatus] = mapped_column(
        _progress_status_sa,
        nullable=False,
        default=ProgressStatus.PENDING,
        server_default=ProgressStatus.PENDING.value,
    )
    current_tick: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    phase1_ticks_done: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    phase2_ticks_done: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    schedule_anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    consecutive_missed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    consecutive_forgot_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    phase2_regression_active: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    phase2_regression_dismissed: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    regression_ticks_done: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    srs_ease_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    srs_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    srs_repetitions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    introduced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phase1_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    graduated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    flashcard: Mapped["Flashcard"] = relationship(back_populates="user_progress")
    tick_results: Mapped[list["TickResult"]] = relationship(
        back_populates="user_card_progress",
        order_by="TickResult.tick_number",
    )
