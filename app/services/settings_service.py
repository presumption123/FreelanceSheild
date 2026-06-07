"""User settings and profile management."""

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models import JurisdictionType, User


class SettingsService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def _get_user(self) -> User:
        user = self.db.query(User).filter(User.id == self.user_id, User.deleted_at.is_(None)).first()
        if not user:
            raise NotFoundError("User not found")
        return user

    def get_profile(self) -> dict:
        user = self._get_user()
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "businessName": user.business_name,
            "businessAddress": user.business_address,
            "jurisdictionType": user.jurisdiction_type.value,
            "jurisdictionCode": user.jurisdiction_code,
            "timezone": user.timezone,
            "currency": user.currency,
            "escalationAutoAdvance": user.escalation_auto_advance,
            "emailNotifications": user.email_notifications,
            "plan": user.plan.value,
            "emailVerified": user.email_verified is not None,
        }

    def update_profile(self, data: dict) -> dict:
        user = self._get_user()
        allowed = {
            "name", "business_name", "business_address", "jurisdiction_code",
            "jurisdiction_type", "timezone", "currency", "escalation_auto_advance",
            "email_notifications",
        }
        field_map = {
            "businessName": "business_name",
            "businessAddress": "business_address",
            "jurisdictionCode": "jurisdiction_code",
            "jurisdictionType": "jurisdiction_type",
            "escalationAutoAdvance": "escalation_auto_advance",
            "emailNotifications": "email_notifications",
        }
        for key, value in data.items():
            attr = field_map.get(key, key)
            if attr in allowed and value is not None:
                if attr == "jurisdiction_type":
                    value = JurisdictionType(value)
                setattr(user, attr, value)
        self.db.commit()
        return self.get_profile()

    def export_data(self) -> dict:
        from app.models import AuditLog, Client, Document, Invoice

        user = self._get_user()
        return {
            "user": self.get_profile(),
            "clients": [
                {"name": c.name, "email": c.email}
                for c in self.db.query(Client).filter(Client.user_id == self.user_id).all()
            ],
            "invoices": [
                {"invoiceNumber": i.invoice_number, "amount": str(i.amount), "status": i.status.value}
                for i in self.db.query(Invoice).filter(Invoice.user_id == self.user_id).all()
            ],
            "documents": self.db.query(Document).filter(Document.user_id == self.user_id).count(),
            "auditLogs": self.db.query(AuditLog).filter(AuditLog.user_id == self.user_id).count(),
        }

    def delete_account(self) -> None:
        from datetime import datetime, timezone

        user = self._get_user()
        user.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
