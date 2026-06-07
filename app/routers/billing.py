"""Stripe billing routes."""

from typing import Annotated

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Plan, User
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/usage")
def get_usage(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return BillingService(db).get_usage(user)


@router.post("/checkout")
def create_checkout(
    plan: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return BillingService(db).create_checkout_session(user, Plan(plan.upper()))


@router.post("/portal")
def billing_portal(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return BillingService(db).create_portal_session(user)


@router.get("/plans")
def list_plans():
    return {
        "plans": [
            {"id": "FREE", "name": "Free", "price": 0, "limit": 3},
            {"id": "STARTER", "name": "Starter", "price": 15, "limit": 25},
            {"id": "PRO", "name": "Pro", "price": 25, "limit": None},
        ]
    }
