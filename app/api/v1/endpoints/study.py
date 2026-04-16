"""Study queue, session, and tick recording endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.tick_result import TickResultKind
from app.models.user import User
from app.schemas.study import (
    PostponeRequest,
    PostponeResponse,
    QueueItem,
    RecordTickRequest,
    RecordTickResponse,
    SetProgressTicksRequest,
    StudyCardResponse,
    StudyCardSideResponse,
    TodaysQueueResponse,
    UpcomingDay,
)
from app.services import study_service

router = APIRouter()


@router.get("/queue", response_model=TodaysQueueResponse)
def get_todays_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TodaysQueueResponse:
    """Today's study queue (priority-ordered, session cap applied)."""
    data = study_service.get_todays_queue(db, current_user.id)
    return TodaysQueueResponse(
        queue=[QueueItem(**item) for item in data["queue"]],
        total_due=data["total_due"],
        capped=data["capped"],
        session_cap=data["session_cap"],
        daily_new_card_limit=data["daily_new_card_limit"],
    )


@router.get("/queue/with-cards")
def get_todays_queue_with_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Today's queue with card content (front, back) and marks for each. For home page."""
    return study_service.get_todays_queue_with_cards(db, current_user.id)


@router.get("/upcoming", response_model=list[UpcomingDay])
def get_upcoming_reviews(
    days: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UpcomingDay]:
    """Next N calendar days with card count per day."""
    data = study_service.get_upcoming_reviews(db, current_user.id, days=days)
    return [UpcomingDay(date=d["date"], count=d["count"]) for d in data]


@router.get("/next-review-date")
def get_next_review_date(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Earliest future review date (for 'all caught up' message)."""
    d = study_service.get_earliest_next_review_date(db, current_user.id)
    return {"date": d.isoformat() if d else None}


@router.get("/card/{progress_id}", response_model=StudyCardResponse)
def get_study_card(
    progress_id: int,
    tick_in_phase: int = 1,
    catch_up_n: int = 0,
    catch_up_total: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StudyCardResponse:
    """Get the card side to display for this queue item (Phase 1=front, Phase 2=back)."""
    try:
        data = study_service.get_study_card(
            db,
            current_user.id,
            progress_id,
            tick_in_phase=tick_in_phase,
            catch_up_n=catch_up_n,
            catch_up_total=catch_up_total,
        )
        return StudyCardResponse(
            progress_id=data["progress_id"],
            flashcard_id=data["flashcard_id"],
            phase=data["phase"],
            tick_in_phase=data["tick_in_phase"],
            catch_up_n=data["catch_up_n"],
            catch_up_total=data["catch_up_total"],
            side=data["side"],
            content=StudyCardSideResponse(**data["content"]),
            content_hidden=StudyCardSideResponse(**data["content_hidden"]),
            hidden_side_label=data["hidden_side_label"],
            subcategory_color=data["subcategory_color"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/progress/{progress_id}/tick", response_model=RecordTickResponse)
def record_tick(
  progress_id: int,
  body: RecordTickRequest,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
) -> RecordTickResponse:
    """Record one tick response (remembered / forgot)."""
    if body.result not in ("remembered", "forgot"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="result must be one of: remembered, forgot",
        )
    kind = TickResultKind(body.result)
    try:
        data = study_service.record_tick(
            db,
            current_user.id,
            progress_id,
            kind,
            response_time_ms=body.response_time_ms,
        )
        return RecordTickResponse(**data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/progress/{progress_id}/ticks")
def set_progress_ticks(
    progress_id: int,
    body: SetProgressTicksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Replace tick results for this progress (e.g. from editing the card strip). Max 16 marks."""
    try:
        study_service.set_progress_ticks(db, current_user.id, progress_id, body.marks)
        return {"status": "ok"}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/postpone", response_model=PostponeResponse)
def postpone_session(
    body: PostponeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostponeResponse:
    """Postpone today's study session by N days. Shifts all due/overdue cards forward."""
    try:
        data = study_service.postpone_todays_session(db, current_user.id, body.days)
        return PostponeResponse(**data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/subcategories/{sub_id}/initialize")
def initialize_subcategory(
  sub_id: int,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
) -> dict:
    """Ensure subcategory has UserCardProgress for all cards (idempotent)."""
    study_service.ensure_subcategory_initialized(db, sub_id, current_user.id)
    return {"status": "ok"}
