from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TrashItemType(str, Enum):
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    FLASHCARD = "flashcard"


class TrashCategoryItem(BaseModel):
    id: int
    type: TrashItemType = TrashItemType.CATEGORY
    title: str
    description: str | None
    deleted_at: datetime

    model_config = {"from_attributes": True}


class TrashSubCategoryItem(BaseModel):
    id: int
    type: TrashItemType = TrashItemType.SUBCATEGORY
    title: str
    description: str | None
    category_id: int
    deleted_at: datetime

    model_config = {"from_attributes": True}


class TrashFlashcardItem(BaseModel):
    id: int
    type: TrashItemType = TrashItemType.FLASHCARD
    sub_category_id: int
    front_preview: str | None
    deleted_at: datetime

    model_config = {"from_attributes": True}


class TrashResponse(BaseModel):
    categories: list[TrashCategoryItem]
    subcategories: list[TrashSubCategoryItem]
    flashcards: list[TrashFlashcardItem]
    total: int
