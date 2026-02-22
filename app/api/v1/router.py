from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    categories,
    flashcards,
    health,
    study,
    subcategories,
    trash,
    upload,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Content management (Story 2)
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
# Subcategory routes use both /categories/{id}/subcategories and /subcategories/{id},
# so they are mounted at the root with no prefix.
api_router.include_router(subcategories.router, tags=["subcategories"])
api_router.include_router(flashcards.router, tags=["flashcards"])
api_router.include_router(study.router, prefix="/study", tags=["study"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(trash.router, prefix="/trash", tags=["trash"])
