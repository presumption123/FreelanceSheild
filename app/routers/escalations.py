"""Escalation routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import EscalationStage, User
from app.schemas import EscalationStatusResponse, MessageResponse
from app.services.document_service import DocumentService
from app.services.escalation_service import EscalationService

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("/{invoice_id}/status", response_model=EscalationStatusResponse)
def get_escalation_status(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = EscalationService(db, user.id)
    return service.get_status(invoice_id)


@router.post("/{invoice_id}/start", response_model=MessageResponse, status_code=201)
def start_enforcement(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = EscalationService(db, user.id)
    escalation = service.start_enforcement(invoice_id)
    return MessageResponse(
        message="Enforcement started",
        data={"escalationId": escalation.id, "stage": escalation.current_stage.value},
    )


@router.post("/{invoice_id}/advance", response_model=MessageResponse)
def advance_escalation(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    esc_service = EscalationService(db, user.id)
    doc_service = DocumentService(db, user.id)
    result = esc_service.advance_stage(invoice_id, triggered_by="user")

    if result["document_queued"]:
        stage = result["stage"]
        if stage == EscalationStage.COURT_READY:
            doc_service.generate_court_packet(invoice_id)
        elif stage in (EscalationStage.DEMAND_LETTER, EscalationStage.FINAL_NOTICE):
            doc_service.generate_demand_letter(invoice_id, stage=stage)

    return MessageResponse(
        message=f"Advanced to {result['escalation'].current_stage.value}",
        data={
            "stage": result["escalation"].current_stage.value,
            "documentQueued": result["document_queued"],
        },
    )


@router.post("/{invoice_id}/pause", response_model=MessageResponse)
def pause_escalation(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    reason: str | None = None,
):
    service = EscalationService(db, user.id)
    service.pause(invoice_id, reason)
    return MessageResponse(message="Escalation paused")


@router.post("/{invoice_id}/resume", response_model=MessageResponse)
def resume_escalation(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = EscalationService(db, user.id)
    service.resume(invoice_id)
    return MessageResponse(message="Escalation resumed")
