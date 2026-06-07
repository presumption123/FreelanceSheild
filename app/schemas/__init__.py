"""Pydantic request/response schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LineItem(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0)
    unit_price: float = Field(gt=0, alias="unitPrice")
    total: float = Field(gt=0)

    model_config = ConfigDict(populate_by_name=True)


class CreateClientRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200, alias="companyName")
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = Field(default=None, max_length=200, alias="addressLine1")
    address_line2: str | None = Field(default=None, max_length=200, alias="addressLine2")
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100, alias="stateProvince")
    postal_code: str | None = Field(default=None, max_length=20, alias="postalCode")
    country: str = Field(default="US", min_length=2, max_length=2)
    jurisdiction_code: str | None = Field(default=None, max_length=20, alias="jurisdictionCode")
    notes: str | None = Field(default=None, max_length=5000)
    auto_advance: bool = Field(default=False, alias="autoAdvance")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, v: str) -> str:
        return v.upper()


class UpdateClientRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200, alias="companyName")
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = Field(default=None, max_length=200, alias="addressLine1")
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100, alias="stateProvince")
    postal_code: str | None = Field(default=None, max_length=20, alias="postalCode")
    country: str | None = Field(default=None, min_length=2, max_length=2)
    jurisdiction_code: str | None = Field(default=None, max_length=20, alias="jurisdictionCode")
    notes: str | None = Field(default=None, max_length=5000)
    auto_advance: bool | None = Field(default=None, alias="autoAdvance")

    model_config = ConfigDict(populate_by_name=True)


class CreateInvoiceRequest(BaseModel):
    client_id: str = Field(alias="clientId")
    invoice_number: str = Field(min_length=1, max_length=100, alias="invoiceNumber")
    amount: float = Field(gt=0, le=10_000_000)
    currency: str = Field(min_length=3, max_length=3)
    issued_at: datetime = Field(alias="issuedAt")
    due_at: datetime = Field(alias="dueAt")
    description: str | None = Field(default=None, max_length=2000)
    line_items: list[LineItem] | None = Field(default=None, max_length=100, alias="lineItems")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()


class UpdateInvoiceRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0, le=10_000_000)
    due_at: datetime | None = Field(default=None, alias="dueAt")
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class MarkPaidRequest(BaseModel):
    amount_paid: float = Field(gt=0, alias="amountPaid")
    paid_at: datetime | None = Field(default=None, alias="paidAt")

    model_config = ConfigDict(populate_by_name=True)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    password: str = Field(min_length=12)


class DisputeReason(str, Enum):
    WORK_NOT_COMPLETED = "work_not_completed"
    WORK_UNSATISFACTORY = "work_unsatisfactory"
    ALREADY_PAID = "already_paid"
    AMOUNT_INCORRECT = "amount_incorrect"
    NOT_AUTHORIZED = "not_authorized"
    OTHER = "other"


class DisputeSubmission(BaseModel):
    reason: DisputeReason
    details: str = Field(min_length=20, max_length=5000)
    contact_email: EmailStr = Field(alias="contactEmail")
    attachment_base64: str | None = Field(default=None, alias="attachmentBase64")
    attachment_mime_type: str | None = Field(default=None, alias="attachmentMimeType")

    model_config = ConfigDict(populate_by_name=True)


class StageHistoryEntry(BaseModel):
    stage: str
    triggered_at: str = Field(alias="triggeredAt")
    triggered_by: str = Field(alias="triggeredBy")
    email_id: str | None = Field(default=None, alias="emailId")
    document_id: str | None = Field(default=None, alias="documentId")
    note: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class EscalationStatusResponse(BaseModel):
    invoice_id: str = Field(alias="invoiceId")
    current_stage: str = Field(alias="currentStage")
    next_stage: str | None = Field(alias="nextStage")
    next_action_at: datetime | None = Field(alias="nextActionAt")
    paused: bool
    stage_history: list[StageHistoryEntry] = Field(alias="stageHistory")
    can_advance: bool = Field(alias="canAdvance")
    requires_approval: bool = Field(alias="requiresApproval")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class AgingBucket(BaseModel):
    label: str
    days_min: int = Field(alias="daysMin")
    days_max: int | None = Field(alias="daysMax")
    invoice_count: int = Field(alias="invoiceCount")
    total_amount: float = Field(alias="totalAmount")

    model_config = ConfigDict(populate_by_name=True)


class DashboardSummary(BaseModel):
    total_outstanding: float = Field(alias="totalOutstanding")
    overdue_count: int = Field(alias="overdueCount")
    average_days_to_payment: float = Field(alias="averageDaysToPayment")
    enforcement_active_count: int = Field(alias="enforcementActiveCount")
    resolved_this_month: int = Field(alias="resolvedThisMonth")
    collection_rate: float = Field(alias="collectionRate")
    aging_buckets: list[AgingBucket] = Field(alias="agingBuckets")

    model_config = ConfigDict(populate_by_name=True)


class ClientResponse(BaseModel):
    id: str
    name: str
    company_name: str | None = Field(alias="companyName")
    email: str
    phone: str | None
    total_outstanding: Decimal = Field(alias="totalOutstanding")
    overdue_count: int = Field(alias="overdueCount")
    risk_score: int = Field(alias="riskScore")
    auto_advance: bool = Field(alias="autoAdvance")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class InvoiceResponse(BaseModel):
    id: str
    client_id: str = Field(alias="clientId")
    invoice_number: str = Field(alias="invoiceNumber")
    amount: Decimal
    amount_paid: Decimal = Field(alias="amountPaid")
    currency: str
    issued_at: datetime = Field(alias="issuedAt")
    due_at: datetime = Field(alias="dueAt")
    days_overdue: int = Field(alias="daysOverdue")
    status: str
    escalation_stage: str = Field(alias="escalationStage")
    description: str | None = None
    client: ClientResponse | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentResponse(BaseModel):
    id: str
    invoice_id: str = Field(alias="invoiceId")
    type: str
    stage: str
    filename: str
    size_bytes: int = Field(alias="sizeBytes")
    created_at: datetime = Field(alias="createdAt")
    jurisdiction_code: str | None = Field(alias="jurisdictionCode")
    court_name: str | None = Field(alias="courtName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    plan: str
    jurisdiction_code: str = Field(alias="jurisdictionCode")
    email_verified: bool = Field(alias="emailVerified")
    business_name: str | None = Field(alias="businessName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageResponse(BaseModel):
    message: str
    data: dict[str, Any] | None = None
