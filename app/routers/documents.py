"""Document routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import EscalationStage, User
from app.schemas import DocumentResponse, MessageResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    invoice_id: str | None = None,
):
    service = DocumentService(db, user.id)
    docs = service.list_documents(invoice_id)
    return [
        DocumentResponse(
            id=d.id,
            invoiceId=d.invoice_id,
            type=d.type.value,
            stage=d.stage.value,
            filename=d.filename,
            sizeBytes=d.size_bytes,
            createdAt=d.created_at,
            jurisdictionCode=d.jurisdiction_code,
            courtName=d.court_name,
        )
        for d in docs
    ]


@router.post("/invoices/{invoice_id}/demand-letter", response_model=DocumentResponse, status_code=201)
def generate_demand_letter(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    stage: str = "DEMAND_LETTER",
):
    service = DocumentService(db, user.id)
    doc = service.generate_demand_letter(invoice_id, stage=EscalationStage(stage))
    return DocumentResponse(
        id=doc.id,
        invoiceId=doc.invoice_id,
        type=doc.type.value,
        stage=doc.stage.value,
        filename=doc.filename,
        sizeBytes=doc.size_bytes,
        createdAt=doc.created_at,
        jurisdictionCode=doc.jurisdiction_code,
        courtName=doc.court_name,
    )


@router.post("/invoices/{invoice_id}/court-packet", response_model=DocumentResponse, status_code=201)
def generate_court_packet(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = DocumentService(db, user.id)
    doc = service.generate_court_packet(invoice_id)
    return DocumentResponse(
        id=doc.id,
        invoiceId=doc.invoice_id,
        type=doc.type.value,
        stage=doc.stage.value,
        filename=doc.filename,
        sizeBytes=doc.size_bytes,
        createdAt=doc.created_at,
        jurisdictionCode=doc.jurisdiction_code,
        courtName=doc.court_name,
    )


@router.post("/invoices/{invoice_id}/audit-export", response_model=DocumentResponse, status_code=201)
def generate_audit_export(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = DocumentService(db, user.id)
    doc = service.generate_audit_trail_export(invoice_id)
    return DocumentResponse(
        id=doc.id,
        invoiceId=doc.invoice_id,
        type=doc.type.value,
        stage=doc.stage.value,
        filename=doc.filename,
        sizeBytes=doc.size_bytes,
        createdAt=doc.created_at,
        jurisdictionCode=doc.jurisdiction_code,
        courtName=doc.court_name,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = DocumentService(db, user.id)
    url = service.get_download_url(document_id)
    return RedirectResponse(url=url, status_code=302)
