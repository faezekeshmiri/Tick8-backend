from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import ChangeEmailRequest, ChangePasswordRequest, UpdateProfileRequest, UserPublic
from app.services import auth_service, user_service

router = APIRouter()


@router.get("/me", response_model=UserPublic)
def get_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_profile(
    data: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    return user_service.update_profile(db, current_user, data)


@router.post("/me/change-email")
def change_email(
    data: ChangeEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.core.security import verify_password
    from fastapi import HTTPException, status

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    auth_service.initiate_email_change(db, current_user, str(data.new_email))
    return {
        "message": (
            f"A verification link has been sent to {data.new_email}. "
            "Your old email remains active until you confirm the new one."
        )
    }


@router.post("/me/change-password")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    user_service.change_password(db, current_user, data)
    return {"message": "Password changed successfully."}
