from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.trash import TrashItemType, TrashResponse
from app.services import trash_service

router = APIRouter()


@router.get("", response_model=TrashResponse)
def list_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrashResponse:
    """List all soft-deleted content owned by the current user within the
    30-day retention window, grouped by type."""
    return trash_service.list_trash(db, current_user.id)


@router.post("/restore/{item_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def restore_item(
    item_type: TrashItemType,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Restore a soft-deleted item from the trash.

    - Restoring a **category** also restores all of its subcategories and flashcards.
    - Restoring a **subcategory** also restores all of its flashcards.
    - Restoring a **flashcard** restores only that card.
    - Returns 409 if the parent item is still deleted.
    - Returns 410 if the 30-day retention window has passed.
    """
    if item_type == TrashItemType.CATEGORY:
        trash_service.restore_category(db, item_id, current_user.id)
    elif item_type == TrashItemType.SUBCATEGORY:
        trash_service.restore_subcategory(db, item_id, current_user.id)
    elif item_type == TrashItemType.FLASHCARD:
        trash_service.restore_flashcard(db, item_id, current_user.id)
