"""Image upload service — validates, stores, and returns a URL-safe path."""

from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024


async def save_image(file: UploadFile, owner_id: int) -> str:
    """Validate and persist an uploaded image.

    Returns the URL path (e.g. ``/uploads/1/abc123.jpg``) that the client
    can use to display the image.
    """
    # --- content-type check ---
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type '{content_type}'. "
                "Accepted formats: JPG, PNG, WebP."
            ),
        )

    # --- extension check ---
    original_name = file.filename or ""
    _, ext = os.path.splitext(original_name.lower())
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file extension '{ext}'. Accepted: .jpg, .png, .webp",
        )
    # Normalise .jpeg → .jpg
    if ext == ".jpeg":
        ext = ".jpg"

    # --- read & size check ---
    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {settings.MAX_IMAGE_SIZE_MB} MB size limit.",
        )
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    # --- persist ---
    owner_dir = os.path.join(settings.UPLOAD_DIR, str(owner_id))
    os.makedirs(owner_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(owner_dir, filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    return f"/uploads/{owner_id}/{filename}"
