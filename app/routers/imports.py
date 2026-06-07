"""CSV import routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.import_service import ImportResult, ImportService

router = APIRouter(prefix="/imports", tags=["imports"])

MAX_CSV_SIZE = 5 * 1024 * 1024


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "text/plain", "application/csv"):
        from app.exceptions import AppError

        raise AppError("Only CSV files are allowed", 400)

    content = await file.read()
    if len(content) > MAX_CSV_SIZE:
        from app.exceptions import AppError

        raise AppError("File too large (max 5MB)", 400)

    service = ImportService(db, user.id)
    return service.import_csv(content)
