"""Schemas for Tick 8 study queue, session, and progress."""

from datetime import date

from pydantic import BaseModel, Field


class UserStudySettingsResponse(BaseModel):
    daily_new_card_limit: int
    session_cap: int
    phase_regression_enabled: bool
    skip_off_schedule_progress_prompt: bool


class UserStudySettingsUpdate(BaseModel):
    daily_new_card_limit: int | None = Field(default=None, ge=5, le=50)
    session_cap: int | None = Field(default=None, ge=20, le=200)
    phase_regression_enabled: bool | None = None
    skip_off_schedule_progress_prompt: bool | None = None


class QueueItem(BaseModel):
    progress_id: int
    flashcard_id: int
    phase: int  # 1 Phase1, 2 Phase2, 0 SRS
    tick_in_phase: int
    is_overdue: bool
    catch_up_n: int
    catch_up_total: int


class TodaysQueueResponse(BaseModel):
    queue: list[QueueItem]
    total_due: int
    capped: bool
    session_cap: int
    daily_new_card_limit: int


class UpcomingDay(BaseModel):
    date: str
    count: int


class RecordTickRequest(BaseModel):
    result: str  # "remembered" | "forgot"
    response_time_ms: int | None = None


class SetProgressTicksRequest(BaseModel):
    marks: list[str]  # "remembered" | "forgot", max 16


class RecordTickResponse(BaseModel):
    progress_id: int
    phase: int
    tick_in_phase: int
    result: str
    phase2_regression_offer: bool


class SubcategoryProgressResponse(BaseModel):
    total: int
    pending: int
    phase1: int
    phase2: int
    graduated: int
    long_term_mastered: int
    mastery_percent: float


class CardProgressItem(BaseModel):
    flashcard_id: int
    progress_id: int  # for recording ticks from subcategory (manual progress)
    marks: list[str]  # "remembered" | "forgot", length 0-16


class SubcategoryCardProgressResponse(BaseModel):
    card_progress: list[CardProgressItem]


class PostponeRequest(BaseModel):
    days: int = Field(..., ge=1, le=30)


class PostponeResponse(BaseModel):
    postponed_count: int


class SessionSummaryResponse(BaseModel):
    cards_reviewed: int
    remembered: int
    difficult: int
    forgot: int
    phase1_to_phase2_count: int
    graduated_count: int
    long_term_mastered_count: int
    streak_days: int
    next_review_date: str | None
    next_review_count: int


class StudyCardSideResponse(BaseModel):
    """One side of a card (for study: only the side shown)."""
    type: str
    text: str | None
    image_url: str | None


class StudyCardResponse(BaseModel):
    """Card content for current queue item; content = visible side, content_hidden = for reveal."""
    progress_id: int
    flashcard_id: int
    phase: int
    tick_in_phase: int
    catch_up_n: int
    catch_up_total: int
    side: str  # "front" | "back"
    content: StudyCardSideResponse
    content_hidden: StudyCardSideResponse
    hidden_side_label: str
    subcategory_color: str
