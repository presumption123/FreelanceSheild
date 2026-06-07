"""User settings routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    businessName: str | None = None
    businessAddress: str | None = None
    jurisdictionCode: str | None = None
    timezone: str | None = None
    currency: str | None = None
    escalationAutoAdvance: bool | None = None
    emailNotifications: bool | None = None


@router.get("/profile")
def get_profile(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return SettingsService(db, user.id).get_profile()


@router.patch("/profile")
def update_profile(
    data: UpdateProfileRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return SettingsService(db, user.id).update_profile(data.model_dump(exclude_unset=True))


@router.get("/export")
def export_data(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return SettingsService(db, user.id).export_data()


@router.delete("/account")
def delete_account(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    SettingsService(db, user.id).delete_account()
    return {"message": "Account scheduled for deletion"}
