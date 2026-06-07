"""Client portal service — public invoice view and disputes."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.exceptions import NotFoundError
from app.lib.portal_token import verify_portal_token
from app.models import AuditActor, AuditEventType, Invoice, InvoiceStatus
from app.schemas import DisputeSubmission
from app.services.audit_service import AuditService
from app.services.payment_link_service import PaymentLinkService


class PortalService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
        self.settings = get_settings()
        self.payment_links = PaymentLinkService(db)

    def get_invoice_by_token(self, invoice_id: str, token: str) -> dict:
        if not verify_portal_token(token, invoice_id):
            raise NotFoundError("Invalid or expired portal link")

        invoice = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client), joinedload(Invoice.user))
            .filter(Invoice.id == invoice_id)
            .first()
        )
        if not invoice:
            raise NotFoundError("Invoice not found")

        self.audit.log(
            user_id=invoice.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.CLIENT_PORTAL_VIEWED,
            actor=AuditActor.CLIENT,
            description=f"Client portal viewed for invoice {invoice.invoice_number}",
        )

        user = invoice.user
        payment_links = self.payment_links.get_payment_links(invoice)
        return {
            "invoiceNumber": invoice.invoice_number,
            "issuerName": user.name,
            "issuerBusinessName": user.business_name,
            "amount": float(invoice.amount),
            "amountPaid": float(invoice.amount_paid),
            "currency": invoice.currency,
            "issuedAt": invoice.issued_at.isoformat(),
            "dueAt": invoice.due_at.isoformat(),
            "daysOverdue": invoice.days_overdue,
            "description": invoice.description,
            "lineItems": invoice.line_items,
            "currentStage": invoice.escalation_stage.value,
            "paymentLinks": payment_links,
            "canDispute": invoice.status not in (InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF),
            "disputeDeadline": None,
        }

    def submit_dispute(self, invoice_id: str, token: str, data: DisputeSubmission) -> dict:
        if not verify_portal_token(token, invoice_id):
            raise NotFoundError("Invalid or expired portal link")

        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise NotFoundError("Invoice not found")

        invoice.status = InvoiceStatus.DISPUTED
        self.db.commit()

        self.audit.log(
            user_id=invoice.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.CLIENT_DISPUTE_SUBMITTED,
            actor=AuditActor.CLIENT,
            description=f"Dispute submitted: {data.reason.value} — {data.details[:100]}",
            metadata={"reason": data.reason.value, "contactEmail": data.contact_email},
        )
        return {"message": "Dispute submitted successfully"}
