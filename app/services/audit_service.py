"""Immutable audit trail logging."""

from sqlalchemy.orm import Session

from app.models import AuditActor, AuditEventType, AuditLog, DocumentType


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        *,
        user_id: str,
        event_type: AuditEventType,
        description: str,
        actor: AuditActor = AuditActor.USER,
        invoice_id: str | None = None,
        email_to: str | None = None,
        email_subject: str | None = None,
        email_provider_message_id: str | None = None,
        document_id: str | None = None,
        document_type: DocumentType | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            invoice_id=invoice_id,
            event_type=event_type,
            actor=actor,
            description=description,
            email_to=email_to,
            email_subject=email_subject,
            email_provider_message_id=email_provider_message_id,
            document_id=document_id,
            document_type=document_type,
            metadata_=metadata,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
