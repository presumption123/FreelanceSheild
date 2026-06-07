"""Local file storage download endpoint."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/{path:path}")
def serve_local_file(path: str):
    settings = get_settings()
    if settings.storage_backend != "local":
        raise HTTPException(status_code=404, detail="Not found")
    file_path = Path(settings.local_storage_path) / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/pdf")
