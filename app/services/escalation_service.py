"""Escalation engine — core enforcement ladder."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.constants.escalation_stages import STAGE_CONFIGS, STAGE_ORDER, get_next_stage
from app.constants.plans import enforce_plan_limit
from app.exceptions import ConflictError, NotFoundError
from app.lib.portal_token import generate_portal_token
from app.lib.scoped import ScopedQueries
from app.models import AuditActor, AuditEventType, Escalation, EscalationStage, Invoice, InvoiceStatus, User
from app.schemas import EscalationStatusResponse, StageHistoryEntry
from app.services.audit_service import AuditService
from app.services.auth_service import require_verified_for_enforcement


def compute_next_action_date(stage: EscalationStage, auto_advance: bool) -> datetime | None:
    if not auto_advance:
        return None
    try:
        stage_idx = STAGE_ORDER.index(stage)
        next_stage = STAGE_ORDER[stage_idx + 1]
    except (ValueError, IndexError):
        return None
    if next_stage in (EscalationStage.RESOLVED, EscalationStage.WRITTEN_OFF):
        return None
    current_trigger = STAGE_CONFIGS[stage].trigger_days_overdue
    next_trigger = STAGE_CONFIGS[next_stage].trigger_days_overdue
    days_until_next = next_trigger - current_trigger
    return datetime.now(timezone.utc) + timedelta(days=days_until_next)


class EscalationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.scoped = ScopedQueries(db, user_id)
        self.audit = AuditService(db)
        self.settings = get_settings()

    def _regenerate_portal_token(self, invoice_id: str) -> str:
        token = generate_portal_token(invoice_id)
        invoice = self.scoped.find_invoice_or_raise(invoice_id)
        invoice.portal_token = token
        invoice.portal_token_expires_at = datetime.now(timezone.utc) + timedelta(days=90)
        self.db.commit()
        return token

    def get_status(self, invoice_id: str) -> EscalationStatusResponse:
        escalation = self.scoped.find_escalation(invoice_id)
        invoice = self.scoped.find_invoice_or_raise(invoice_id)
        if not escalation:
            return EscalationStatusResponse(
                invoiceId=invoice_id,
                currentStage=EscalationStage.NONE.value,
                nextStage=EscalationStage.REMINDER_1.value,
                nextActionAt=None,
                paused=False,
                stageHistory=[],
                canAdvance=invoice.status in (InvoiceStatus.OVERDUE, InvoiceStatus.IN_ENFORCEMENT),
                requiresApproval=True,
            )

        next_stage = get_next_stage(escalation.current_stage)
        history = [StageHistoryEntry.model_validate(h) for h in (escalation.stage_history or [])]
        auto_advance = invoice.client.auto_advance if invoice.client else False

        return EscalationStatusResponse(
            invoiceId=invoice_id,
            currentStage=escalation.current_stage.value,
            nextStage=next_stage.value if next_stage else None,
            nextActionAt=escalation.next_action_at,
            paused=escalation.paused,
            stageHistory=history,
            canAdvance=not escalation.paused and next_stage is not None,
            requiresApproval=not auto_advance,
        )

    def start_enforcement(self, invoice_id: str) -> Escalation:
        user = self.db.query(User).filter(User.id == self.user_id).first()
        require_verified_for_enforcement(user)

        invoice = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client), joinedload(Invoice.escalation))
            .filter(Invoice.id == invoice_id, Invoice.user_id == self.user_id)
            .first()
        )
        if not invoice:
            raise NotFoundError("Invoice not found")
        if invoice.status == InvoiceStatus.PAID:
            raise ConflictError("Cannot enforce a paid invoice")
        if invoice.escalation:
            raise ConflictError("Enforcement already active")

        active_count = (
            self.db.query(Escalation)
            .join(Invoice)
            .filter(Escalation.user_id == self.user_id, Invoice.status == InvoiceStatus.IN_ENFORCEMENT)
            .count()
        )
        enforce_plan_limit(user, active_count)

        auto_advance = invoice.client.auto_advance if invoice.client else False
        history_entry = {
            "stage": EscalationStage.REMINDER_1.value,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
            "triggeredBy": "user",
        }

        escalation = Escalation(
            invoice_id=invoice_id,
            user_id=self.user_id,
            current_stage=EscalationStage.REMINDER_1,
            last_action_at=datetime.now(timezone.utc),
            next_action_at=compute_next_action_date(EscalationStage.REMINDER_1, auto_advance),
            stage_history=[history_entry],
        )
        invoice.status = InvoiceStatus.IN_ENFORCEMENT
        invoice.escalation_stage = EscalationStage.REMINDER_1

        self.db.add(escalation)
        self._regenerate_portal_token(invoice_id)
        self.db.commit()
        self.db.refresh(escalation)

        from app.services.queue_service import QueueService

        QueueService(self.db).enqueue(
            "escalation-email",
            {"escalationId": escalation.id, "stage": EscalationStage.REMINDER_1.value, "invoiceId": invoice_id},
            user_id=self.user_id,
        )

        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.ESCALATION_STARTED,
            actor=AuditActor.USER,
            description="Enforcement started — Reminder 1 queued",
        )
        return escalation

    def advance_stage(self, invoice_id: str, triggered_by: str = "user") -> dict:
        escalation = (
            self.db.query(Escalation)
            .options(joinedload(Escalation.invoice).joinedload(Invoice.client))
            .filter(Escalation.invoice_id == invoice_id, Escalation.user_id == self.user_id)
            .first()
        )
        if not escalation:
            raise NotFoundError("Escalation not found")
        if escalation.paused:
            raise ConflictError("Escalation is paused")

        next_stage = get_next_stage(escalation.current_stage)
        if not next_stage:
            raise ConflictError("Already at final stage")

        stage_config = STAGE_CONFIGS[next_stage]
        history = list(escalation.stage_history or [])
        history.append(
            {
                "stage": next_stage.value,
                "triggeredAt": datetime.now(timezone.utc).isoformat(),
                "triggeredBy": triggered_by,
            }
        )

        auto_advance = escalation.invoice.client.auto_advance if escalation.invoice.client else False
        escalation.current_stage = next_stage
        escalation.last_action_at = datetime.now(timezone.utc)
        escalation.next_action_at = compute_next_action_date(next_stage, auto_advance)
        escalation.stage_history = history
        escalation.invoice.escalation_stage = next_stage

        self._regenerate_portal_token(invoice_id)
        self.db.commit()
        self.db.refresh(escalation)

        document_queued = stage_config.generates_document
        from app.services.queue_service import QueueService

        queue = QueueService(self.db)
        if document_queued:
            queue.enqueue(
                "generate-document",
                {"invoiceId": invoice_id, "userId": self.user_id, "stage": next_stage.value},
                user_id=self.user_id,
            )

        queue.enqueue(
            "escalation-email",
            {"escalationId": escalation.id, "stage": next_stage.value, "invoiceId": invoice_id},
            user_id=self.user_id,
        )

        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.ESCALATION_STAGE_ADVANCED,
            actor=AuditActor.USER if triggered_by == "user" else AuditActor.SYSTEM,
            description=f"Escalation advanced to {next_stage.value}",
            metadata={"stage": next_stage.value, "triggeredBy": triggered_by},
        )

        return {
            "escalation": escalation,
            "email_queued": True,
            "document_queued": document_queued,
            "stage": next_stage,
        }

    def pause(self, invoice_id: str, reason: str | None = None) -> Escalation:
        escalation = self.scoped.find_escalation(invoice_id)
        if not escalation:
            raise NotFoundError("Escalation not found")
        escalation.paused = True
        escalation.paused_reason = reason
        self.db.commit()
        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.ESCALATION_PAUSED,
            actor=AuditActor.USER,
            description=f"Escalation paused: {reason or 'No reason given'}",
        )
        return escalation

    def resume(self, invoice_id: str) -> Escalation:
        escalation = self.scoped.find_escalation(invoice_id)
        if not escalation:
            raise NotFoundError("Escalation not found")
        escalation.paused = False
        escalation.paused_reason = None
        self.db.commit()
        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.ESCALATION_RESUMED,
            actor=AuditActor.USER,
            description="Escalation resumed",
        )
        return escalation

    def process_auto_advances(self) -> int:
        now = datetime.now(timezone.utc)
        from app.models import Client

        due = (
            self.db.query(Escalation)
            .join(Invoice)
            .join(Client)
            .filter(
                Escalation.paused.is_(False),
                Escalation.next_action_at <= now,
                Escalation.user_id == self.user_id,
                Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.IN_ENFORCEMENT]),
                Client.auto_advance.is_(True),
            )
            .all()
        )
        count = 0
        for escalation in due:
            try:
                self.advance_stage(escalation.invoice_id, triggered_by="auto")
                count += 1
            except Exception:
                continue
        return count
