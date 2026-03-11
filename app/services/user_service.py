from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UpdateProfileRequest


def update_profile(db: Session, user: User, data: UpdateProfileRequest) -> User:
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.avatar_url is not None:
        user.avatar_url = (data.avatar_url.strip() or None) if data.avatar_url else None
    if data.preferred_language is not None:
        user.preferred_language = data.preferred_language
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    user.hashed_password = hash_password(data.new_password)
    db.commit()
