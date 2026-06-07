"""Stripe subscription billing service."""

from datetime import datetime, timezone

import stripe
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import PlanLimitError
from app.models import Plan, User
from app.services.audit_service import AuditService


PLAN_PRICES = {
    Plan.STARTER: "stripe_starter_price_id",
    Plan.PRO: "stripe_pro_price_id",
}


class BillingService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        if self.settings.stripe_secret_key:
            stripe.api_key = self.settings.stripe_secret_key
        self.audit = AuditService(db)

    def _ensure_stripe(self) -> None:
        if not self.settings.stripe_enabled:
            raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY in .env")

    def get_or_create_customer(self, user: User) -> str:
        self._ensure_stripe()
        if user.stripe_customer_id:
            return user.stripe_customer_id

        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"userId": user.id},
        )
        user.stripe_customer_id = customer.id
        self.db.commit()
        return customer.id

    def create_checkout_session(self, user: User, plan: Plan) -> dict:
        self._ensure_stripe()
        if plan == Plan.FREE:
            raise ValueError("Cannot checkout for free plan")

        price_attr = PLAN_PRICES[plan]
        price_id = getattr(self.settings, price_attr)
        if not price_id:
            raise ValueError(f"Stripe price ID not configured for {plan.value}")

        customer_id = self.get_or_create_customer(user)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{self.settings.app_url}/app/settings/billing?success=true",
            cancel_url=f"{self.settings.app_url}/app/settings/billing?cancelled=true",
            metadata={"userId": user.id, "plan": plan.value},
        )
        return {"checkoutUrl": session.url, "sessionId": session.id}

    def create_portal_session(self, user: User) -> dict:
        self._ensure_stripe()
        if not user.stripe_customer_id:
            raise ValueError("No billing account found")
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{self.settings.app_url}/app/settings/billing",
        )
        return {"portalUrl": session.url}

    def handle_webhook_event(self, payload: bytes, sig_header: str) -> dict:
        self._ensure_stripe()
        event = stripe.Webhook.construct_event(
            payload, sig_header, self.settings.stripe_webhook_secret or ""
        )

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = session.get("metadata", {}).get("userId")
            plan_name = session.get("metadata", {}).get("plan")
            if user_id and plan_name:
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user.plan = Plan(plan_name)
                    user.plan_started_at = datetime.now(timezone.utc)
                    self.db.commit()

        elif event["type"] == "customer.subscription.deleted":
            customer_id = event["data"]["object"].get("customer")
            user = self.db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user:
                user.plan = Plan.FREE
                user.plan_expires_at = datetime.now(timezone.utc)
                self.db.commit()

        elif event["type"] == "customer.subscription.updated":
            customer_id = event["data"]["object"].get("customer")
            status = event["data"]["object"].get("status")
            user = self.db.query(User).filter(User.stripe_customer_id == customer_id).first()
            if user and status == "active":
                items = event["data"]["object"].get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id")
                    if price_id == self.settings.stripe_pro_price_id:
                        user.plan = Plan.PRO
                    elif price_id == self.settings.stripe_starter_price_id:
                        user.plan = Plan.STARTER
                    user.plan_started_at = datetime.now(timezone.utc)
                    self.db.commit()

        return {"received": True, "type": event["type"]}

    def get_usage(self, user: User) -> dict:
        from app.constants.escalation_stages import PLAN_LIMITS
        from app.models import Escalation, Invoice, InvoiceStatus

        active_count = (
            self.db.query(Escalation)
            .join(Invoice)
            .filter(Escalation.user_id == user.id, Invoice.status == InvoiceStatus.IN_ENFORCEMENT)
            .count()
        )
        limit = PLAN_LIMITS[user.plan]
        return {
            "plan": user.plan.value,
            "activeEnforcementCases": active_count,
            "limit": limit,
            "remaining": None if limit is None else max(0, limit - active_count),
        }
