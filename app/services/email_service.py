"""Provider-agnostic email service."""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import get_settings
from app.lib.logger import get_logger
from app.services.audit_service import AuditService

logger = get_logger(__name__)


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str


@dataclass
class SendEmailOptions:
    to: str
    subject: str
    html_body: str
    text_body: str
    from_name: str | None = None
    reply_to: str | None = None
    attachments: list[EmailAttachment] | None = None


class EmailProvider(Protocol):
    async def send(self, options: SendEmailOptions) -> str: ...


class ConsoleEmailProvider:
    async def send(self, options: SendEmailOptions) -> str:
        logger.info("EMAIL to=%s subject=%s", options.to, options.subject)
        return "console-message-id"


class ResendEmailProvider:
    async def send(self, options: SendEmailOptions) -> str:
        settings = get_settings()
        payload = {
            "from": f"{options.from_name or settings.email_from_name} <{settings.email_from}>",
            "to": [options.to],
            "subject": options.subject,
            "html": options.html_body,
            "text": options.text_body,
        }
        if options.reply_to:
            payload["reply_to"] = options.reply_to
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["id"]


def get_email_provider() -> EmailProvider:
    provider = get_settings().email_provider
    if provider == "resend":
        return ResendEmailProvider()
    return ConsoleEmailProvider()


class EmailService:
    def __init__(self, audit: AuditService):
        self.audit = audit
        self.provider = get_email_provider()

    async def send_escalation_email(
        self,
        *,
        user_id: str,
        invoice_id: str,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_name: str,
        reply_to: str,
        actor: str = "SYSTEM",
    ) -> str:
        message_id = await self.provider.send(
            SendEmailOptions(
                to=to,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_name=from_name,
                reply_to=reply_to,
            )
        )
        from app.models import AuditActor, AuditEventType

        self.audit.log(
            user_id=user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.EMAIL_SENT,
            actor=AuditActor.SYSTEM if actor == "SYSTEM" else AuditActor.USER,
            description=f"Email sent: {subject}",
            email_to=to,
            email_subject=subject,
            email_provider_message_id=message_id,
        )
        return message_id
