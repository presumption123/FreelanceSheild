"""Background job worker — processes email and document queues."""

from sqlalchemy.orm import Session, joinedload

from app.constants.escalation_stages import STAGE_CONFIGS
from app.database import SessionLocal
from app.lib.logger import get_logger
from app.models import Escalation, EscalationStage, Invoice
from app.services.audit_service import AuditService
from app.services.document_service import DocumentService
from app.services.email_service import EmailService
from app.services.email_templates import TEMPLATE_MAP
from app.services.jurisdiction_service import format_currency
from app.services.queue_service import QueueService

logger = get_logger(__name__)


async def process_escalation_email(db: Session, payload: dict) -> None:
    escalation_id = payload.get("escalationId")
    stage_name = payload.get("stage")
    if not escalation_id or not stage_name:
        return

    escalation = (
        db.query(Escalation)
        .options(joinedload(Escalation.invoice).joinedload(Invoice.client), joinedload(Escalation.invoice).joinedload(Invoice.user))
        .filter(Escalation.id == escalation_id)
        .first()
    )
    if not escalation or not escalation.invoice:
        return

    invoice = escalation.invoice
    client = invoice.client
    user = invoice.user
    if not client or not user:
        return

    stage = EscalationStage(stage_name)
    config = STAGE_CONFIGS[stage]
    template_fn = TEMPLATE_MAP.get(config.email_template_key)
    if not template_fn:
        return

    portal_url = f"{__import__('app.config', fromlist=['get_settings']).get_settings().portal_url}/{invoice.id}?token={invoice.portal_token or ''}"
    amount = format_currency(int(float(invoice.amount) * 100), invoice.currency)

    if config.email_template_key == "reminder_1":
        tmpl = template_fn(user.name, client.name, invoice.invoice_number, amount, invoice.days_overdue, invoice.due_at.strftime("%B %d, %Y"), portal_url)
    elif config.email_template_key in ("reminder_2", "reminder_3"):
        tmpl = template_fn(user.name, client.name, invoice.invoice_number, amount, invoice.days_overdue, portal_url)
    elif config.email_template_key == "demand_letter":
        tmpl = template_fn(user.name, client.name, invoice.invoice_number, amount, "30 days", portal_url)
    elif config.email_template_key == "final_notice":
        from app.legal_templates.jurisdictions import get_jurisdiction
        j = get_jurisdiction(user.jurisdiction_code)
        tmpl = template_fn(user.name, client.name, invoice.invoice_number, amount, "7 days", j.small_claims_court_name, portal_url)
    elif config.email_template_key == "court_notice":
        from app.legal_templates.jurisdictions import get_jurisdiction
        j = get_jurisdiction(user.jurisdiction_code)
        tmpl = template_fn(user.name, client.name, invoice.invoice_number, j.small_claims_court_name)
    else:
        return

    email_service = EmailService(AuditService(db))
    await email_service.send_escalation_email(
        user_id=user.id,
        invoice_id=invoice.id,
        to=client.email,
        subject=tmpl.subject,
        html_body=tmpl.html_body,
        text_body=tmpl.text_body,
        from_name=user.name,
        reply_to=user.email,
    )


def process_generate_document(db: Session, payload: dict) -> None:
    invoice_id = payload.get("invoiceId")
    user_id = payload.get("userId")
    stage_name = payload.get("stage")
    if not invoice_id or not user_id:
        return

    doc_service = DocumentService(db, user_id)
    stage = EscalationStage(stage_name) if stage_name else EscalationStage.DEMAND_LETTER
    if stage == EscalationStage.COURT_READY:
        doc_service.generate_court_packet(invoice_id)
    else:
        doc_service.generate_demand_letter(invoice_id, stage=stage)


async def process_job(db: Session, job) -> None:
    handlers = {
        "escalation-email": process_escalation_email,
        "generate-document": lambda db, payload: process_generate_document(db, payload),
        "payment-confirmation": lambda db, payload: None,
    }
    handler = handlers.get(job.job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job.job_type}")
    result = handler(db, job.payload)
    if hasattr(result, "__await__"):
        await result


async def process_pending_jobs() -> int:
    db = SessionLocal()
    queue = QueueService(db)
    processed = 0
    try:
        jobs = queue.fetch_pending(limit=20)
        for job in jobs:
            try:
                await process_job(db, job)
                queue.complete(job.id)
                processed += 1
            except Exception as exc:
                logger.error("Job %s failed: %s", job.id, exc)
                queue.fail(job.id, str(exc))
    finally:
        db.close()
    return processed
