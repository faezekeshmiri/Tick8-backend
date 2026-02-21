from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserListResponse, AdminUserView

router = APIRouter()


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: str | None = Query(default=None, description="Search by name or email"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminUserListResponse:
    query = db.query(User)
    if search:
        term = f"%{search.lower()}%"
        query = query.filter(
            User.display_name.ilike(term) | User.email.ilike(term)
        )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    return AdminUserListResponse(
        users=[AdminUserView.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}/suspend", response_model=AdminUserView)
def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend their own account.",
        )
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot suspend other administrators.",
        )
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/reactivate", response_model=AdminUserView)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/make-admin", response_model=AdminUserView)
def make_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an administrator.",
        )
    user.role = UserRole.ADMIN
    db.commit()
    db.refresh(user)
    return user
