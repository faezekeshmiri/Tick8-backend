from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SubCategoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped


class SubCategoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("title cannot be blank")
            return stripped
        return v


class SubCategoryResponse(BaseModel):
    id: int
    category_id: int
    title: str
    description: str | None
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
