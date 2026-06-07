"""Webhook handlers."""

from fastapi import APIRouter, Header, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.billing_service import BillingService
from fastapi import Depends

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(alias="Stripe-Signature"),
):
    payload = await request.body()
    return BillingService(db).handle_webhook_event(payload, stripe_signature)
