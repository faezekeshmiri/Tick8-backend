from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel

from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.upload_service import save_image

router = APIRouter()


class ImageUploadResponse(BaseModel):
    url: str


@router.post("/upload/image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> ImageUploadResponse:
    """Upload an image to use as a flashcard front or back.

    - Accepted formats: JPG, PNG, WebP
    - Maximum size: 5 MB
    - Returns a URL path that can be stored in ``front_image_url`` or ``back_image_url``.
    """
    url = await save_image(file, current_user.id)
    return ImageUploadResponse(url=url)
