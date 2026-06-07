"""Payment link generation for client portal."""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.lib.scoped import ScopedQueries
from app.models import AuditActor, AuditEventType, Invoice
from app.services.audit_service import AuditService


class PaymentLinkService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.audit = AuditService(db)

    def get_payment_links(self, invoice: Invoice) -> list[dict]:
        """Return payment options for the client portal."""
        links = []
        balance = float(invoice.amount - invoice.amount_paid)

        if balance <= 0:
            return links

        # Stripe payment link (if user has Stripe connected)
        user = invoice.user
        if user and user.stripe_customer_id and self.settings.stripe_enabled:
            links.append(
                {
                    "provider": "stripe",
                    "url": f"{self.settings.app_url}/api/v1/billing/pay-invoice/{invoice.id}",
                    "label": f"Pay {invoice.currency} {balance:,.2f} with card",
                }
            )

        links.append(
            {
                "provider": "custom",
                "url": f"mailto:{user.email if user else ''}?subject=Payment%20for%20{invoice.invoice_number}",
                "label": "Contact to arrange payment",
            }
        )
        return links

    def log_payment_click(self, invoice_id: str, user_id: str, provider: str) -> None:
        self.audit.log(
            user_id=user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.PAYMENT_LINK_CLICKED,
            actor=AuditActor.CLIENT,
            description=f"Payment link clicked ({provider})",
            metadata={"provider": provider},
        )
