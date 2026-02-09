from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": "Tick8 backend is running"}
