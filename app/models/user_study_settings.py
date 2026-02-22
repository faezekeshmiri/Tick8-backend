"""User study preferences: daily new card limit, session cap, phase regression toggle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserStudySettings(Base):
    __tablename__ = "user_study_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    daily_new_card_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, server_default="20"
    )
    session_cap: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default="50"
    )
    phase_regression_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    skip_off_schedule_progress_prompt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    user: Mapped["User"] = relationship(back_populates="study_settings")
