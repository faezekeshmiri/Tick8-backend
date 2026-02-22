from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.flashcard import ContentType


class FlashcardSide(BaseModel):
    """Represents one side (front or back) of a flashcard."""

    type: ContentType = ContentType.TEXT
    text: str | None = Field(default=None)
    image_url: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_side(self) -> "FlashcardSide":
        if self.type == ContentType.TEXT:
            if not self.text or not self.text.strip():
                raise ValueError("text content is required when type is 'text'")
            self.image_url = None
        elif self.type == ContentType.IMAGE:
            if not self.image_url or not self.image_url.strip():
                raise ValueError("image_url is required when type is 'image'")
            self.text = None
        return self


class FlashcardCreate(BaseModel):
    front: FlashcardSide
    back: FlashcardSide


class FlashcardUpdate(BaseModel):
    front: FlashcardSide | None = None
    back: FlashcardSide | None = None


class FlashcardSideResponse(BaseModel):
    type: ContentType
    text: str | None
    image_url: str | None

    model_config = {"from_attributes": True}


class FlashcardResponse(BaseModel):
    id: int
    sub_category_id: int
    front: FlashcardSideResponse
    back: FlashcardSideResponse
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FlashcardListResponse(BaseModel):
    items: list[FlashcardResponse]
    total: int
    page: int
    per_page: int
    pages: int


class FlashcardReorderItem(BaseModel):
    id: int
    order_index: int


class FlashcardReorderRequest(BaseModel):
    flashcards: list[FlashcardReorderItem] = Field(..., min_length=1)
