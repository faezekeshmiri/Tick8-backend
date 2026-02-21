import re

from pydantic import BaseModel, EmailStr, field_validator

_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*\d).{8,}$")


class RegisterRequest(BaseModel):
    display_name: str
    email: EmailStr
    password: str

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be blank")
        if len(stripped) > 100:
            raise ValueError("Display name must be 100 characters or fewer")
        return stripped

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not _PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain at least "
                "one uppercase letter and one number"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not _PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 8 characters and contain at least "
                "one uppercase letter and one number"
            )
        return v


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    pass
