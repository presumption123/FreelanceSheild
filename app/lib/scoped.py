"""User-scoped database query helpers to prevent IDOR."""

from sqlalchemy.orm import Session

from app.models import AuditLog, Client, Document, Escalation, Invoice


class ScopedQueries:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def find_invoice(self, invoice_id: str) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.user_id == self.user_id)
            .first()
        )

    def find_invoice_or_raise(self, invoice_id: str) -> Invoice:
        invoice = self.find_invoice(invoice_id)
        if not invoice:
            from app.exceptions import NotFoundError

            raise NotFoundError("Invoice not found")
        return invoice

    def find_client(self, client_id: str) -> Client | None:
        return (
            self.db.query(Client)
            .filter(Client.id == client_id, Client.user_id == self.user_id)
            .first()
        )

    def find_client_or_raise(self, client_id: str) -> Client:
        client = self.find_client(client_id)
        if not client:
            from app.exceptions import NotFoundError

            raise NotFoundError("Client not found")
        return client

    def find_document(self, document_id: str) -> Document | None:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == self.user_id)
            .first()
        )

    def find_escalation(self, invoice_id: str) -> Escalation | None:
        return (
            self.db.query(Escalation)
            .filter(Escalation.invoice_id == invoice_id, Escalation.user_id == self.user_id)
            .first()
        )

    def get_audit_trail(self, invoice_id: str) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.invoice_id == invoice_id, AuditLog.user_id == self.user_id)
            .order_by(AuditLog.created_at.asc())
            .all()
        )
