from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import (
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
    send_email_change_verification,
)
from app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    verify_password,
)
from app.models.token import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    VerificationPurpose,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


def register_user(db: Session, data: RegisterRequest) -> tuple[User, str, str]:
    """Create a new user, return (user, access_token, refresh_token_value)."""
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        display_name=data.display_name,
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()  # get user.id before token creation

    _issue_email_verification_token(db, user, VerificationPurpose.REGISTRATION)
    db.commit()
    db.refresh(user)

    send_welcome_email(user.email, user.display_name)
    send_verification_email(
        user.email,
        user.display_name,
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.purpose == VerificationPurpose.REGISTRATION,
            EmailVerificationToken.used.is_(False),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
        .token,
    )

    access_token = create_access_token(user.id, user.role.value)
    refresh_value = _create_refresh_token(db, user, remember_me=True)
    return user, access_token, refresh_value


def login_user(db: Session, data: LoginRequest) -> tuple[User, str, str]:
    """Authenticate user, return (user, access_token, refresh_token_value)."""
    user = db.query(User).filter(User.email == data.email.lower()).first()

    # Generic error for both "no account" and "wrong password"
    _invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    if not user:
        raise _invalid_credentials

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact support.",
        )

    if user.is_locked():
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account temporarily locked due to too many failed attempts. "
                f"Try again in {remaining} minute(s)."
            ),
        )

    if not verify_password(data.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )
        db.commit()
        raise _invalid_credentials

    # Successful login — reset lockout state
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    access_token = create_access_token(user.id, user.role.value)
    refresh_value = _create_refresh_token(db, user, remember_me=data.remember_me)
    return user, access_token, refresh_value


def logout_user(db: Session, refresh_token_value: str) -> None:
    token = (
        db.query(RefreshToken).filter(RefreshToken.token == refresh_token_value).first()
    )
    if token:
        db.delete(token)
        db.commit()


def refresh_access_token(db: Session, refresh_token_value: str) -> tuple[User, str, str]:
    """Rotate refresh token and issue new access token."""
    token_row = (
        db.query(RefreshToken).filter(RefreshToken.token == refresh_token_value).first()
    )
    if not token_row or token_row.is_expired():
        if token_row:
            db.delete(token_row)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )

    user = token_row.user
    if not user.is_active:
        db.delete(token_row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended. Please contact support.",
        )

    remember_me = token_row.remember_me
    db.delete(token_row)

    access_token = create_access_token(user.id, user.role.value)
    new_refresh_value = _create_refresh_token(db, user, remember_me=remember_me)
    return user, access_token, new_refresh_value


def request_password_reset(db: Session, email: str) -> None:
    """Always returns a neutral response regardless of whether the email exists."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user or not user.is_active:
        return

    # Invalidate any existing reset tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update({"used": True})

    token_value = generate_secure_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token_value,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
    )
    db.add(reset_token)
    db.commit()

    send_password_reset_email(user.email, user.display_name, token_value)


def reset_password(db: Session, token_value: str, new_password: str) -> None:
    token_row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == token_value)
        .first()
    )
    if not token_row or not token_row.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired.",
        )

    user = token_row.user
    user.hashed_password = hash_password(new_password)
    token_row.used = True

    # Invalidate all active sessions for security
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
    db.commit()


def verify_email(db: Session, token_value: str) -> None:
    token_row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token == token_value)
        .first()
    )
    if not token_row or not token_row.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or has expired.",
        )

    user = token_row.user
    if token_row.purpose == VerificationPurpose.REGISTRATION:
        user.is_email_verified = True
    elif token_row.purpose == VerificationPurpose.EMAIL_CHANGE:
        if token_row.new_email:
            user.email = token_row.new_email
            user.pending_email = None
            user.is_email_verified = True

    token_row.used = True
    db.commit()


def resend_verification_email(db: Session, user: User) -> None:
    if user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your email address is already verified.",
        )

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.purpose == VerificationPurpose.REGISTRATION,
        EmailVerificationToken.used.is_(False),
    ).update({"used": True})

    token_row = _issue_email_verification_token(db, user, VerificationPurpose.REGISTRATION)
    db.commit()
    send_verification_email(user.email, user.display_name, token_row.token)


def initiate_email_change(db: Session, user: User, new_email: str) -> None:
    existing = db.query(User).filter(User.email == new_email.lower()).first()
    if existing and existing.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already in use.",
        )

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id,
        EmailVerificationToken.purpose == VerificationPurpose.EMAIL_CHANGE,
        EmailVerificationToken.used.is_(False),
    ).update({"used": True})

    user.pending_email = new_email.lower()
    token_row = _issue_email_verification_token(
        db, user, VerificationPurpose.EMAIL_CHANGE, new_email=new_email.lower()
    )
    db.commit()
    send_email_change_verification(new_email, user.display_name, token_row.token)


# ── internal helpers ──────────────────────────────────────────────────────────

def _create_refresh_token(db: Session, user: User, remember_me: bool) -> str:
    days = (
        settings.REFRESH_TOKEN_EXPIRE_DAYS
        if remember_me
        else settings.REFRESH_TOKEN_NO_REMEMBER_DAYS
    )
    token_value = generate_secure_token()
    rt = RefreshToken(
        user_id=user.id,
        token=token_value,
        remember_me=remember_me,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    db.add(rt)
    db.commit()
    return token_value


def _issue_email_verification_token(
    db: Session,
    user: User,
    purpose: VerificationPurpose,
    new_email: str | None = None,
) -> EmailVerificationToken:
    token_value = generate_secure_token()
    token_row = EmailVerificationToken(
        user_id=user.id,
        token=token_value,
        purpose=purpose,
        new_email=new_email,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )
    db.add(token_row)
    return token_row
