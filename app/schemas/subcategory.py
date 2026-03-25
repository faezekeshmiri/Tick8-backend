import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex_color(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    if not _HEX_COLOR.match(s):
        raise ValueError("color must be a #RRGGBB hex string")
    return s.lower()


class SubCategoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    color: str | None = Field(default=None, description="Accent color #RRGGBB")

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped

    @field_validator("color")
    @classmethod
    def color_hex(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class SubCategoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    color: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("title cannot be blank")
            return stripped
        return v

    @field_validator("color")
    @classmethod
    def color_hex(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class SubCategoryResponse(BaseModel):
    id: int
    category_id: int
    title: str
    description: str | None
    color: str | None
    flashcard_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubCategoryListResponse(BaseModel):
    items: list[SubCategoryResponse]
    total: int
    page: int
    per_page: int
    pages: int
