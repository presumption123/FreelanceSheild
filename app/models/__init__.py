"""SQLAlchemy ORM models for FreelanceShield."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_cuid() -> str:
    return uuid.uuid4().hex[:25]


class Plan(str, enum.Enum):
    FREE = "FREE"
    STARTER = "STARTER"
    PRO = "PRO"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    OVERDUE = "OVERDUE"
    IN_ENFORCEMENT = "IN_ENFORCEMENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    WRITTEN_OFF = "WRITTEN_OFF"
    DISPUTED = "DISPUTED"


class EscalationStage(str, enum.Enum):
    NONE = "NONE"
    REMINDER_1 = "REMINDER_1"
    REMINDER_2 = "REMINDER_2"
    REMINDER_3 = "REMINDER_3"
    DEMAND_LETTER = "DEMAND_LETTER"
    FINAL_NOTICE = "FINAL_NOTICE"
    COURT_READY = "COURT_READY"
    RESOLVED = "RESOLVED"
    WRITTEN_OFF = "WRITTEN_OFF"


class InvoiceSource(str, enum.Enum):
    MANUAL = "MANUAL"
    CSV_IMPORT = "CSV_IMPORT"
    FRESHBOOKS = "FRESHBOOKS"
    WAVE = "WAVE"
    QUICKBOOKS = "QUICKBOOKS"


class DocumentType(str, enum.Enum):
    DEMAND_LETTER = "DEMAND_LETTER"
    FINAL_NOTICE = "FINAL_NOTICE"
    SMALL_CLAIMS_PACKET = "SMALL_CLAIMS_PACKET"
    AUDIT_TRAIL_EXPORT = "AUDIT_TRAIL_EXPORT"
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT"


class AuditEventType(str, enum.Enum):
    INVOICE_CREATED = "INVOICE_CREATED"
    INVOICE_UPDATED = "INVOICE_UPDATED"
    INVOICE_MARKED_PAID = "INVOICE_MARKED_PAID"
    INVOICE_WRITTEN_OFF = "INVOICE_WRITTEN_OFF"
    ESCALATION_STARTED = "ESCALATION_STARTED"
    ESCALATION_STAGE_ADVANCED = "ESCALATION_STAGE_ADVANCED"
    ESCALATION_PAUSED = "ESCALATION_PAUSED"
    ESCALATION_RESUMED = "ESCALATION_RESUMED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_BOUNCED = "EMAIL_BOUNCED"
    EMAIL_OPENED = "EMAIL_OPENED"
    EMAIL_CLICKED = "EMAIL_CLICKED"
    DOCUMENT_GENERATED = "DOCUMENT_GENERATED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    CLIENT_PORTAL_VIEWED = "CLIENT_PORTAL_VIEWED"
    CLIENT_DISPUTE_SUBMITTED = "CLIENT_DISPUTE_SUBMITTED"
    PAYMENT_LINK_CLICKED = "PAYMENT_LINK_CLICKED"
    INTEGRATION_CONNECTED = "INTEGRATION_CONNECTED"
    INTEGRATION_SYNCED = "INTEGRATION_SYNCED"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"


class AuditActor(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    CLIENT = "CLIENT"


class IntegrationProvider(str, enum.Enum):
    FRESHBOOKS = "FRESHBOOKS"
    WAVE = "WAVE"
    QUICKBOOKS = "QUICKBOOKS"


class IntegrationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"


class JurisdictionType(str, enum.Enum):
    US_STATE = "US_STATE"
    UK = "UK"
    CANADA_PROVINCE = "CANADA_PROVINCE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email_verified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    jurisdiction_type: Mapped[JurisdictionType] = mapped_column(
        Enum(JurisdictionType), default=JurisdictionType.US_STATE
    )
    jurisdiction_code: Mapped[str] = mapped_column(String(50), default="CA")

    escalation_auto_advance: Mapped[bool] = mapped_column(Boolean, default=False)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    plan: Mapped[Plan] = mapped_column(Enum(Plan), default=Plan.FREE)
    plan_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    clients: Mapped[list["Client"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    escalations: Mapped[list["Escalation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_client_user_email"),)

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    name: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="US")

    jurisdiction_type: Mapped[JurisdictionType] = mapped_column(
        Enum(JurisdictionType), default=JurisdictionType.US_STATE
    )
    jurisdiction_code: Mapped[str] = mapped_column(String(50), default="CA")

    auto_advance: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_invoiced: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_outstanding: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    invoice_count: Mapped[int] = mapped_column(Integer, default=0)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="clients")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="client")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("user_id", "invoice_number", name="uq_invoice_user_number"),
        Index("idx_invoices_user_status", "user_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(25), ForeignKey("clients.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    invoice_number: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[InvoiceSource] = mapped_column(Enum(InvoiceSource), default=InvoiceSource.MANUAL)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(DateTime)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    days_overdue: Mapped[int] = mapped_column(Integer, default=0)
    interest_accrued: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_items: Mapped[list | None] = mapped_column(JSON, nullable=True)

    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, index=True)
    escalation_stage: Mapped[EscalationStage] = mapped_column(
        Enum(EscalationStage), default=EscalationStage.NONE, index=True
    )

    portal_token: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True, index=True)
    portal_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attachment_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="invoices")
    client: Mapped["Client"] = relationship(back_populates="invoices")
    escalation: Mapped["Escalation | None"] = relationship(back_populates="invoice", uselist=False)
    documents: Mapped[list["Document"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="invoice")


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    invoice_id: Mapped[str] = mapped_column(
        String(25), ForeignKey("invoices.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    current_stage: Mapped[EscalationStage] = mapped_column(Enum(EscalationStage), default=EscalationStage.REMINDER_1)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_history: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship(back_populates="escalations")
    invoice: Mapped["Invoice"] = relationship(back_populates="escalation")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[str] = mapped_column(String(25), ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))
    stage: Mapped[EscalationStage] = mapped_column(Enum(EscalationStage))
    s3_key: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")

    jurisdiction_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    statutes_cited: Mapped[list | None] = mapped_column(JSON, nullable=True)
    demand_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    court_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    download_count: Mapped[int] = mapped_column(Integer, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="documents")
    invoice: Mapped["Invoice"] = relationship(back_populates="documents")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_logs_invoice", "invoice_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[str | None] = mapped_column(
        String(25), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType), index=True)
    actor: Mapped[AuditActor] = mapped_column(Enum(AuditActor), default=AuditActor.USER)
    description: Mapped[str] = mapped_column(Text)

    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document_id: Mapped[str | None] = mapped_column(String(25), nullable=True)
    document_type: Mapped[DocumentType | None] = mapped_column(Enum(DocumentType), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="audit_logs")
    invoice: Mapped["Invoice | None"] = relationship(back_populates="audit_logs")


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_integration_user_provider"),)

    id: Mapped[str] = mapped_column(String(25), primary_key=True, default=generate_cuid)
    user_id: Mapped[str] = mapped_column(String(25), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    provider: Mapped[IntegrationProvider] = mapped_column(Enum(IntegrationProvider))
    status: Mapped[IntegrationStatus] = mapped_column(Enum(IntegrationStatus), default=IntegrationStatus.ACTIVE)

    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="integrations")


from app.models.job_queue import JobStatus, QueuedJob  # noqa: E402, F401
