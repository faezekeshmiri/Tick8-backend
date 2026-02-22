from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CategoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title cannot be blank")
        return stripped


class CategoryUpdate(BaseModel):
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


class CategoryResponse(BaseModel):
    id: int
    title: str
    description: str | None
    subcategory_count: int
    flashcard_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryDetailResponse(CategoryResponse):
    """Extended response that includes subcategory list."""
    pass


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
    page: int
    per_page: int
    pages: int
