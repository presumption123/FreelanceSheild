"""Integration OAuth and sync routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import IntegrationProvider, User
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("")
def list_integrations(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = IntegrationService(db, user.id)
    integrations = service.list_integrations()
    return [
        {
            "provider": i.provider.value,
            "status": i.status.value,
            "lastSyncAt": i.last_sync_at.isoformat() if i.last_sync_at else None,
            "lastSyncError": i.last_sync_error,
            "syncEnabled": i.sync_enabled,
        }
        for i in integrations
    ]


@router.get("/{provider}/connect")
def connect_integration(
    provider: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = IntegrationService(db, user.id)
    url = service.get_oauth_url(IntegrationProvider(provider.upper()))
    return {"authUrl": url}


@router.get("/{provider}/callback")
def oauth_callback(
    provider: str,
    code: str = Query(...),
    realmId: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user_id = state.split(":")[0] if state else None
    if not user_id:
        from app.exceptions import AppError

        raise AppError("Invalid OAuth state", 400)

    service = IntegrationService(db, user_id)
    service.handle_oauth_callback(IntegrationProvider(provider.upper()), code, realmId)
    from app.config import get_settings

    return RedirectResponse(f"{get_settings().app_url}/app/settings/integrations?connected={provider}")


@router.delete("/{provider}")
def disconnect_integration(
    provider: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = IntegrationService(db, user.id)
    service.disconnect(IntegrationProvider(provider.upper()))
    return {"message": f"{provider} disconnected"}


@router.post("/{provider}/sync")
def sync_integration(
    provider: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = IntegrationService(db, user.id)
    return service.sync_invoices(IntegrationProvider(provider.upper()))
