"""Audit log routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    invoice_id: Annotated[str | None, Query(alias="invoiceId")] = None,
    limit: int = Query(default=50, le=200),
):
    query = db.query(AuditLog).filter(AuditLog.user_id == user.id)
    if invoice_id:
        query = query.filter(AuditLog.invoice_id == invoice_id)
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": log.id,
            "invoiceId": log.invoice_id,
            "eventType": log.event_type.value,
            "actor": log.actor.value,
            "description": log.description,
            "createdAt": log.created_at.isoformat(),
            "emailTo": log.email_to,
            "emailSubject": log.email_subject,
        }
        for log in logs
    ]


@router.get("/invoices/{invoice_id}")
def get_invoice_audit_trail(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.invoice_id == invoice_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    return [
        {
            "id": log.id,
            "eventType": log.event_type.value,
            "actor": log.actor.value,
            "description": log.description,
            "createdAt": log.created_at.isoformat(),
        }
        for log in logs
    ]
