"""Invoice management service."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.constants.escalation_stages import VALID_INVOICE_TRANSITIONS
from app.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError
from app.lib.scoped import ScopedQueries
from app.models import AuditActor, AuditEventType, EscalationStage, Invoice, InvoiceStatus
from app.schemas import CreateInvoiceRequest, UpdateInvoiceRequest
from app.services.audit_service import AuditService
from app.services.client_service import ClientService


class InvoiceService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.scoped = ScopedQueries(db, user_id)
        self.audit = AuditService(db)
        self.clients = ClientService(db, user_id)

    def list_invoices(self, status: InvoiceStatus | None = None) -> list[Invoice]:
        query = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client))
            .filter(Invoice.user_id == self.user_id, Invoice.deleted_at.is_(None))
        )
        if status:
            query = query.filter(Invoice.status == status)
        return query.order_by(Invoice.due_at.desc()).all()

    def get_invoice(self, invoice_id: str) -> Invoice:
        invoice = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client), joinedload(Invoice.escalation))
            .filter(Invoice.id == invoice_id, Invoice.user_id == self.user_id, Invoice.deleted_at.is_(None))
            .first()
        )
        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    def create_invoice(self, data: CreateInvoiceRequest) -> Invoice:
        self.scoped.find_client_or_raise(data.client_id)

        existing = (
            self.db.query(Invoice)
            .filter(Invoice.user_id == self.user_id, Invoice.invoice_number == data.invoice_number)
            .first()
        )
        if existing:
            raise ConflictError(f"Invoice number {data.invoice_number} already exists")

        line_items = [item.model_dump(by_alias=True) for item in data.line_items] if data.line_items else None

        invoice = Invoice(
            user_id=self.user_id,
            client_id=data.client_id,
            invoice_number=data.invoice_number,
            amount=Decimal(str(data.amount)),
            currency=data.currency,
            issued_at=data.issued_at,
            due_at=data.due_at,
            description=data.description,
            line_items=line_items,
            status=InvoiceStatus.DRAFT,
            escalation_stage=EscalationStage.NONE,
        )
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)

        client = self.scoped.find_client_or_raise(data.client_id)
        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.INVOICE_CREATED,
            actor=AuditActor.USER,
            description=f"Invoice {invoice.invoice_number} created for {client.name}",
        )
        self.clients.update_client_stats(data.client_id)
        return self.get_invoice(invoice.id)

    def update_invoice(self, invoice_id: str, data: UpdateInvoiceRequest) -> Invoice:
        invoice = self.get_invoice(invoice_id)
        updates = data.model_dump(exclude_unset=True)

        if "status" in updates and updates["status"]:
            new_status = updates["status"]
            allowed = VALID_INVOICE_TRANSITIONS.get(invoice.status.value, set())
            if new_status not in allowed:
                raise InvalidStateTransitionError(
                    f"Cannot transition from {invoice.status.value} to {new_status}"
                )
            invoice.status = InvoiceStatus(new_status)

        if "amount" in updates and updates["amount"] is not None:
            invoice.amount = Decimal(str(updates["amount"]))
        if "due_at" in updates and updates["due_at"] is not None:
            invoice.due_at = updates["due_at"]
        if "description" in updates:
            invoice.description = updates["description"]

        self.db.commit()
        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.INVOICE_UPDATED,
            actor=AuditActor.USER,
            description=f"Invoice {invoice.invoice_number} updated",
        )
        self.clients.update_client_stats(invoice.client_id)
        return self.get_invoice(invoice_id)

    def mark_sent(self, invoice_id: str) -> Invoice:
        return self.update_invoice(invoice_id, UpdateInvoiceRequest(status=InvoiceStatus.SENT.value))

    def mark_paid(self, invoice_id: str, amount_paid: float, paid_at: datetime | None = None) -> Invoice:
        invoice = self.get_invoice(invoice_id)
        new_amount_paid = invoice.amount_paid + Decimal(str(amount_paid))
        fully_paid = new_amount_paid >= invoice.amount

        invoice.amount_paid = new_amount_paid
        invoice.paid_at = paid_at or datetime.now(timezone.utc) if fully_paid else None
        invoice.status = InvoiceStatus.PAID if fully_paid else InvoiceStatus.PARTIALLY_PAID
        if fully_paid:
            invoice.escalation_stage = EscalationStage.RESOLVED
            if invoice.escalation:
                invoice.escalation.current_stage = EscalationStage.RESOLVED
                invoice.escalation.paused = True
                invoice.escalation.paused_reason = "Invoice paid in full"

        self.db.commit()

        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.INVOICE_MARKED_PAID,
            actor=AuditActor.USER,
            description=(
                f"Invoice marked fully paid (${amount_paid:.2f})"
                if fully_paid
                else f"Partial payment recorded (${amount_paid:.2f})"
            ),
        )
        self.clients.update_client_stats(invoice.client_id)
        return self.get_invoice(invoice_id)

    def write_off(self, invoice_id: str) -> Invoice:
        invoice = self.get_invoice(invoice_id)
        invoice.status = InvoiceStatus.WRITTEN_OFF
        invoice.escalation_stage = EscalationStage.WRITTEN_OFF
        if invoice.escalation:
            invoice.escalation.current_stage = EscalationStage.WRITTEN_OFF
            invoice.escalation.paused = True
        self.db.commit()
        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice.id,
            event_type=AuditEventType.INVOICE_WRITTEN_OFF,
            actor=AuditActor.USER,
            description=f"Invoice {invoice.invoice_number} written off",
        )
        self.clients.update_client_stats(invoice.client_id)
        return self.get_invoice(invoice_id)

    def update_days_overdue(self) -> None:
        today = datetime.now(timezone.utc)
        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.user_id == self.user_id,
                Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF, InvoiceStatus.DRAFT]),
            )
            .all()
        )
        for invoice in invoices:
            due = invoice.due_at.replace(tzinfo=timezone.utc) if invoice.due_at.tzinfo is None else invoice.due_at
            days = max(0, (today - due).days)
            invoice.days_overdue = days
            if invoice.status == InvoiceStatus.SENT and invoice.due_at < today:
                invoice.status = InvoiceStatus.OVERDUE
        self.db.commit()
        self.clients.update_risk_scores()
