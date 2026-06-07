"""Public client portal routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DisputeSubmission, MessageResponse
from app.services.portal_service import PortalService

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/{invoice_id}")
def view_portal(invoice_id: str, token: str, db: Annotated[Session, Depends(get_db)]):
    service = PortalService(db)
    return service.get_invoice_by_token(invoice_id, token)


@router.post("/{invoice_id}/dispute", response_model=MessageResponse)
def submit_dispute(
    invoice_id: str,
    token: str,
    data: DisputeSubmission,
    db: Annotated[Session, Depends(get_db)],
):
    service = PortalService(db)
    return service.submit_dispute(invoice_id, token, data)
