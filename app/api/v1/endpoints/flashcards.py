from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardListResponse,
    FlashcardReorderRequest,
    FlashcardResponse,
    FlashcardUpdate,
)
from app.services import flashcard_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Nested under /subcategories/{sub_id}/flashcards
# ---------------------------------------------------------------------------

@router.get("/subcategories/{sub_id}/flashcards", response_model=FlashcardListResponse)
def list_flashcards(
    sub_id: int,
    search: str | None = Query(
        default=None,
        description="Search in front or back text (case-insensitive)",
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FlashcardListResponse:
    return flashcard_service.list_flashcards(
        db, sub_id, current_user.id, search=search, page=page, per_page=per_page
    )


@router.post(
    "/subcategories/{sub_id}/flashcards",
    response_model=FlashcardResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_flashcard(
    sub_id: int,
    data: FlashcardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FlashcardResponse:
    return flashcard_service.create_flashcard(db, sub_id, current_user.id, data)


@router.post(
    "/subcategories/{sub_id}/flashcards/reorder",
    response_model=list[FlashcardResponse],
)
def reorder_flashcards(
    sub_id: int,
    data: FlashcardReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FlashcardResponse]:
    return flashcard_service.reorder_flashcards(db, sub_id, current_user.id, data)


# ---------------------------------------------------------------------------
# Direct access by flashcard ID
# ---------------------------------------------------------------------------

@router.get("/flashcards/{card_id}", response_model=FlashcardResponse)
def get_flashcard(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FlashcardResponse:
    return flashcard_service.get_flashcard(db, card_id, current_user.id)


@router.patch("/flashcards/{card_id}", response_model=FlashcardResponse)
def update_flashcard(
    card_id: int,
    data: FlashcardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FlashcardResponse:
    return flashcard_service.update_flashcard(db, card_id, current_user.id, data)


@router.delete("/flashcards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard(
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    flashcard_service.delete_flashcard(db, card_id, current_user.id)
