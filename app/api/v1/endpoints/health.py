from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    database_status = "connected"

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "unavailable"

    return {"status": "ok", "database": database_status}
