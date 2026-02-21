from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_refresh_token_from_cookie
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserPublic
from app.services import auth_service

router = APIRouter()

_COOKIE_NAME = "refresh_token"
_COOKIE_PATH = "/api/v1/auth"
_COOKIE_SAMESITE = "lax"


def _set_refresh_cookie(response: Response, token: str, remember_me: bool) -> None:
    max_age = (
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400 if remember_me else None
    )
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # set to True in production (HTTPS)
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
        max_age=max_age,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path=_COOKIE_PATH)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, access_token, refresh_value = auth_service.register_user(db, data)
    _set_refresh_cookie(response, refresh_value, remember_me=True)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, access_token, refresh_value = auth_service.login_user(db, data)
    _set_refresh_cookie(response, refresh_value, remember_me=data.remember_me)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if refresh_token:
        auth_service.logout_user(db, refresh_token)
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully."}


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str = Depends(get_refresh_token_from_cookie),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user, access_token, new_refresh = auth_service.refresh_access_token(db, refresh_token)
    _set_refresh_cookie(response, new_refresh, remember_me=True)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    auth_service.request_password_reset(db, data.email)
    return {
        "message": "If an account exists for this email, you will receive a reset link shortly."
    }


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    auth_service.reset_password(db, data.token, data.new_password)
    _clear_refresh_cookie(response)
    return {"message": "Password reset successfully. Please log in with your new password."}


@router.post("/verify-email")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> dict:
    auth_service.verify_email(db, data.token)
    return {"message": "Email address verified successfully."}


@router.post("/resend-verification")
def resend_verification(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    auth_service.resend_verification_email(db, current_user)
    return {"message": "Verification email sent."}
