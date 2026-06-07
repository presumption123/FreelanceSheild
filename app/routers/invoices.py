"""Invoice routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import InvoiceStatus, User
from app.schemas import CreateInvoiceRequest, InvoiceResponse, MarkPaidRequest, UpdateInvoiceRequest
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _to_response(invoice) -> InvoiceResponse:
    from app.schemas import ClientResponse

    client_resp = None
    if invoice.client:
        c = invoice.client
        client_resp = ClientResponse(
            id=c.id,
            name=c.name,
            companyName=c.company_name,
            email=c.email,
            phone=c.phone,
            totalOutstanding=c.total_outstanding,
            overdueCount=c.overdue_count,
            riskScore=c.risk_score,
            autoAdvance=c.auto_advance,
        )
    return InvoiceResponse(
        id=invoice.id,
        clientId=invoice.client_id,
        invoiceNumber=invoice.invoice_number,
        amount=invoice.amount,
        amountPaid=invoice.amount_paid,
        currency=invoice.currency,
        issuedAt=invoice.issued_at,
        dueAt=invoice.due_at,
        daysOverdue=invoice.days_overdue,
        status=invoice.status.value,
        escalationStage=invoice.escalation_stage.value,
        description=invoice.description,
        client=client_resp,
    )


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status: Annotated[str | None, Query()] = None,
):
    service = InvoiceService(db, user.id)
    invoice_status = InvoiceStatus(status) if status else None
    return [_to_response(inv) for inv in service.list_invoices(invoice_status)]


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    data: CreateInvoiceRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.create_invoice(data))


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.get_invoice(invoice_id))


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    data: UpdateInvoiceRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.update_invoice(invoice_id, data))


@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
def mark_sent(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.mark_sent(invoice_id))


@router.post("/{invoice_id}/paid", response_model=InvoiceResponse)
def mark_paid(
    invoice_id: str,
    data: MarkPaidRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.mark_paid(invoice_id, data.amount_paid, data.paid_at))


@router.post("/{invoice_id}/write-off", response_model=InvoiceResponse)
def write_off(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = InvoiceService(db, user.id)
    return _to_response(service.write_off(invoice_id))
