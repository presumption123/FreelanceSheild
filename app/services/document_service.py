"""PDF document generation — demand letters, court packets, audit exports."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from app.exceptions import NotFoundError
from app.legal_templates.jurisdictions import JurisdictionConfig, get_jurisdiction
from app.lib.scoped import ScopedQueries
from app.lib.storage import storage_service
from app.models import AuditActor, AuditEventType, Document, DocumentType, EscalationStage, Invoice, User
from app.services.audit_service import AuditService
from app.services.jurisdiction_service import calculate_accrued_interest, format_currency


@dataclass
class DemandLetterParams:
    sender_name: str
    sender_business_name: str | None
    sender_address: str
    sender_email: str
    recipient_name: str
    recipient_company_name: str | None
    recipient_address: str
    recipient_email: str
    invoice_number: str
    invoice_date: str
    due_date: str
    principal_amount: int
    interest_amount: int
    total_demand: int
    jurisdiction: JurisdictionConfig
    demand_deadline: str
    stage: Literal["DEMAND_LETTER", "FINAL_NOTICE"]
    currency: str
    today: str


def _format_date(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except ValueError:
        return iso_date


def _build_demand_letter_body(params: DemandLetterParams) -> list[str]:
    j = params.jurisdiction
    is_uk = j.type.value == "UK"
    is_final = params.stage == "FINAL_NOTICE"
    paragraphs: list[str] = []

    paragraphs.append(
        f"This letter constitutes a formal demand for payment of the outstanding balance owed "
        f"to {params.sender_name}"
        f"{f' / {params.sender_business_name}' if params.sender_business_name else ''} "
        f"by {params.recipient_name}"
        f"{f' / {params.recipient_company_name}' if params.recipient_company_name else ''}."
    )

    amount_block = (
        f"Invoice Number: {params.invoice_number}\n"
        f"Invoice Date: {_format_date(params.invoice_date)}\n"
        f"Payment Due Date: {_format_date(params.due_date)}\n"
        f"Principal Amount: {format_currency(params.principal_amount, params.currency)}\n"
    )
    if params.interest_amount > 0:
        amount_block += (
            f"Statutory Interest ({j.late_interest_rate_annual}% per annum per "
            f"{j.late_interest_statute}): {format_currency(params.interest_amount, params.currency)}\n"
        )
    amount_block += f"TOTAL AMOUNT DUE: {format_currency(params.total_demand, params.currency)}"
    paragraphs.append(amount_block)

    if is_uk:
        paragraphs.append(
            "Pursuant to the Late Payment of Commercial Debts (Interest) Act 1998, as amended by "
            "the Late Payment of Commercial Debts Regulations 2002, you are required to pay the "
            "outstanding amount plus statutory interest at 8% per annum above the Bank of England base rate."
        )
        if j.compensation_amounts:
            comp = (
                j.compensation_amounts.under1000
                if params.principal_amount < 100000
                else j.compensation_amounts.under10000
                if params.principal_amount < 1000000
                else j.compensation_amounts.over10000
            )
            paragraphs.append(
                f"In addition, you are liable for a fixed compensation amount of "
                f"{format_currency(comp, params.currency)} under the Late Payment Regulations 2002."
            )
    else:
        paragraphs.append(
            f"Under {j.late_interest_statute}, statutory interest accrues on the unpaid balance "
            f"at a rate of {j.late_interest_rate_annual}% per annum from the date payment was due."
        )

    paragraphs.append(
        f"DEMAND: You are hereby formally demanded to pay the total amount of "
        f"{format_currency(params.total_demand, params.currency)} no later than "
        f"{_format_date(params.demand_deadline)} ({j.demand_letter_notice_days} days from the date of this letter)."
    )

    if is_final:
        paragraphs.append(
            f"THIS IS YOUR FINAL NOTICE. If payment is not received in full by "
            f"{_format_date(params.demand_deadline)}, {params.sender_name} reserves the right to pursue "
            f"all available legal remedies, including filing a claim in {j.small_claims_court_name}."
        )
    else:
        paragraphs.append(
            f"Failure to pay may result in legal action in {j.small_claims_court_name}, which may "
            f"result in a judgment for the principal amount, statutory interest, court costs, and related expenses."
        )

    paragraphs.append(
        f"Payment may be made by contacting {params.sender_name} directly at {params.sender_email}. "
        f"All payments should reference Invoice Number {params.invoice_number}."
    )
    paragraphs.append(
        f"If you believe this demand is in error, please contact {params.sender_name} in writing within 7 days."
    )
    return paragraphs


def generate_demand_letter_pdf(params: DemandLetterParams) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=14, textColor=colors.HexColor("#1a3366"))
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=12)

    story = []
    title = (
        "FORMAL DEMAND FOR PAYMENT"
        if params.stage == "DEMAND_LETTER"
        else "FINAL NOTICE — INTENT TO FILE LEGAL PROCEEDINGS"
    )
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Date: {_format_date(params.today)}", body_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>FROM:</b>", body_style))
    story.append(Paragraph(params.sender_name, body_style))
    if params.sender_business_name:
        story.append(Paragraph(params.sender_business_name, body_style))
    for line in params.sender_address.split("\n"):
        story.append(Paragraph(line, body_style))
    story.append(Paragraph(params.sender_email, body_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>TO:</b>", body_style))
    story.append(Paragraph(params.recipient_name, body_style))
    if params.recipient_company_name:
        story.append(Paragraph(params.recipient_company_name, body_style))
    for line in params.recipient_address.split("\n"):
        if line.strip():
            story.append(Paragraph(line, body_style))
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            f"<b>RE: Unpaid Invoice {params.invoice_number} — "
            f"{format_currency(params.total_demand, params.currency)} now due</b>",
            body_style,
        )
    )
    story.append(Spacer(1, 12))

    for paragraph in _build_demand_letter_body(params):
        for part in paragraph.split("\n"):
            story.append(Paragraph(part, body_style))

    story.append(Spacer(1, 24))
    story.append(Paragraph("Sincerely,", body_style))
    story.append(Spacer(1, 36))
    story.append(Paragraph(f"<b>{params.sender_name}</b>", body_style))
    story.append(
        Paragraph(
            f"<i>Generated by FreelanceShield on {_format_date(params.today)}. "
            f"Applicable law: {params.jurisdiction.primary_statutes[0]}.</i>",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(story)
    return buffer.getvalue()


def render_court_packet_pdf(invoice: Invoice, user: User, jurisdiction: JurisdictionConfig, audit_trail: list) -> bytes:
    client = invoice.client
    principal_cents = int(float(invoice.amount) * 100)
    interest_cents = calculate_accrued_interest(principal_cents, invoice.days_overdue, jurisdiction)
    total_cents = principal_cents + interest_cents
    client_address = ", ".join(
        filter(None, [client.address_line1, client.city, client.state_province, client.postal_code])
    ) or "See attached"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>Small Claims Court Packet</b>", styles["Title"]),
        Paragraph(jurisdiction.small_claims_court_name, styles["Heading2"]),
        Spacer(1, 12),
    ]

    summary_data = [
        ["Plaintiff (You)", f"{user.name}{f' / {user.business_name}' if user.business_name else ''}"],
        ["Plaintiff Address", user.business_address or "See attached"],
        ["Defendant (Client)", f"{client.name}{f' / {client.company_name}' if client.company_name else ''}"],
        ["Defendant Address", client_address],
        ["Amount Claimed", format_currency(principal_cents, user.currency)],
        ["Statutory Interest", format_currency(interest_cents, user.currency)],
        ["Total Claim", format_currency(total_cents, user.currency)],
        ["Applicable Statute", jurisdiction.late_interest_statute],
    ]
    table = Table(summary_data, colWidths=[2 * inch, 4 * inch])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story.extend([
        Paragraph("<b>Section 1 — Claim Summary</b>", styles["Heading3"]),
        table,
        Spacer(1, 12),
        Paragraph("<b>Section 2 — Statement of Claim</b>", styles["Heading3"]),
        Paragraph(
            f"I, {user.name}, am the plaintiff. The defendant, {client.name}, owes me "
            f"{format_currency(principal_cents, user.currency)} for Invoice No. {invoice.invoice_number}.",
            styles["Normal"],
        ),
        PageBreak(),
        Paragraph("<b>Section 3 — Court Form Fields</b>", styles["Heading3"]),
        Paragraph(
            f"Transfer to official form {jurisdiction.claims_form_name or 'Standard'}: "
            f"Court: {jurisdiction.small_claims_court_name}",
            styles["Normal"],
        ),
        PageBreak(),
        Paragraph("<b>Section 4 — Communication Evidence Log</b>", styles["Heading3"]),
    ])

    for i, entry in enumerate(audit_trail):
        letter = chr(65 + i)
        story.append(
            Paragraph(
                f"<b>Exhibit {letter}</b> — {entry.created_at.strftime('%Y-%m-%d')} — {entry.description}",
                styles["Normal"],
            )
        )

    if not audit_trail:
        story.append(Paragraph("No communications logged yet.", styles["Normal"]))

    story.extend([
        PageBreak(),
        Paragraph("<b>Section 5 — Filing Checklist</b>", styles["Heading3"]),
        Paragraph("☐ Official court form ☐ Copy of invoice ☐ Demand letters ☐ Filing fee ☐ Government ID", styles["Normal"]),
    ])
    doc.build(story)
    return buffer.getvalue()


def generate_audit_trail_export_pdf(logs: list, invoice_number: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>Audit Trail Export — Invoice {invoice_number}</b>", styles["Heading1"]),
        Spacer(1, 12),
    ]

    data = [["Timestamp", "Event", "Description", "Actor"]]
    for log in logs:
        data.append([
            log.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            log.event_type.value,
            log.description[:80],
            log.actor.value,
        ])

    table = Table(data, colWidths=[1.2 * inch, 1.5 * inch, 3 * inch, 0.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)

    log_hash = hashlib.sha256(json.dumps([l.id for l in logs]).encode()).hexdigest()
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"<i>Integrity hash: {log_hash}</i>", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()


class DocumentService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.scoped = ScopedQueries(db, user_id)
        self.audit = AuditService(db)

    def list_documents(self, invoice_id: str | None = None) -> list[Document]:
        query = self.db.query(Document).filter(Document.user_id == self.user_id)
        if invoice_id:
            query = query.filter(Document.invoice_id == invoice_id)
        return query.order_by(Document.created_at.desc()).all()

    def generate_demand_letter(
        self, invoice_id: str, stage: EscalationStage = EscalationStage.DEMAND_LETTER
    ) -> Document:
        invoice = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client), joinedload(Invoice.user))
            .filter(Invoice.id == invoice_id, Invoice.user_id == self.user_id)
            .first()
        )
        if not invoice:
            raise NotFoundError("Invoice not found")

        user = invoice.user or self.db.query(User).filter(User.id == self.user_id).first()
        client = invoice.client
        jurisdiction = get_jurisdiction(user.jurisdiction_code)

        principal_cents = int(float(invoice.amount) * 100)
        interest_cents = calculate_accrued_interest(principal_cents, invoice.days_overdue, jurisdiction)
        total_cents = principal_cents + interest_cents
        deadline = (datetime.now(timezone.utc) + timedelta(days=jurisdiction.demand_letter_notice_days)).isoformat()
        today = datetime.now(timezone.utc).isoformat()

        recipient_address = "\n".join(
            filter(None, [client.address_line1, client.address_line2, client.city, client.state_province, client.postal_code])
        ) or "Address on file"

        params = DemandLetterParams(
            sender_name=user.name,
            sender_business_name=user.business_name,
            sender_address=user.business_address or "Address on file",
            sender_email=user.email,
            recipient_name=client.name,
            recipient_company_name=client.company_name,
            recipient_address=recipient_address,
            recipient_email=client.email,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.issued_at.isoformat(),
            due_date=invoice.due_at.isoformat(),
            principal_amount=principal_cents,
            interest_amount=interest_cents,
            total_demand=total_cents,
            jurisdiction=jurisdiction,
            demand_deadline=deadline,
            stage="FINAL_NOTICE" if stage == EscalationStage.FINAL_NOTICE else "DEMAND_LETTER",
            currency=invoice.currency,
            today=today,
        )

        pdf_bytes = generate_demand_letter_pdf(params)
        doc_type = DocumentType.FINAL_NOTICE if stage == EscalationStage.FINAL_NOTICE else DocumentType.DEMAND_LETTER
        filename = f"demand-letter-{invoice.invoice_number}-{int(datetime.now().timestamp())}.pdf"
        s3_key = f"users/{self.user_id}/documents/{filename}"
        storage_service.upload(s3_key, pdf_bytes)

        document = Document(
            user_id=self.user_id,
            invoice_id=invoice_id,
            type=doc_type,
            stage=stage,
            s3_key=s3_key,
            filename=filename,
            size_bytes=len(pdf_bytes),
            jurisdiction_code=jurisdiction.code,
            statutes_cited=jurisdiction.primary_statutes,
            demand_deadline=datetime.fromisoformat(deadline.replace("Z", "+00:00")),
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.DOCUMENT_GENERATED,
            actor=AuditActor.USER,
            description=f"Generated {doc_type.value}: {filename}",
            document_id=document.id,
            document_type=doc_type,
        )
        return document

    def generate_court_packet(self, invoice_id: str) -> Document:
        invoice = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.client), joinedload(Invoice.user))
            .filter(Invoice.id == invoice_id, Invoice.user_id == self.user_id)
            .first()
        )
        if not invoice:
            raise NotFoundError("Invoice not found")

        user = invoice.user
        jurisdiction = get_jurisdiction(user.jurisdiction_code)
        principal_cents = int(float(invoice.amount) * 100)

        if principal_cents > jurisdiction.small_claims_limit:
            raise ValueError(
                f"Invoice amount exceeds small claims limit of "
                f"{format_currency(jurisdiction.small_claims_limit, user.currency)} for {jurisdiction.name}"
            )

        audit_trail = self.scoped.get_audit_trail(invoice_id)
        pdf_bytes = render_court_packet_pdf(invoice, user, jurisdiction, audit_trail)

        filename = f"court-packet-{invoice.invoice_number}-{int(datetime.now().timestamp())}.pdf"
        s3_key = f"users/{self.user_id}/court-packets/{filename}"
        storage_service.upload(s3_key, pdf_bytes)

        document = Document(
            user_id=self.user_id,
            invoice_id=invoice_id,
            type=DocumentType.SMALL_CLAIMS_PACKET,
            stage=EscalationStage.COURT_READY,
            s3_key=s3_key,
            filename=filename,
            size_bytes=len(pdf_bytes),
            jurisdiction_code=jurisdiction.code,
            court_name=jurisdiction.small_claims_court_name,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        self.audit.log(
            user_id=self.user_id,
            invoice_id=invoice_id,
            event_type=AuditEventType.DOCUMENT_GENERATED,
            actor=AuditActor.USER,
            description=f"Generated court packet: {filename}",
            document_id=document.id,
            document_type=DocumentType.SMALL_CLAIMS_PACKET,
        )
        return document

    def generate_audit_trail_export(self, invoice_id: str) -> Document:
        invoice = self.scoped.find_invoice_or_raise(invoice_id)
        logs = self.scoped.get_audit_trail(invoice_id)
        pdf_bytes = generate_audit_trail_export_pdf(logs, invoice.invoice_number)

        filename = f"audit-trail-{invoice.invoice_number}-{int(datetime.now().timestamp())}.pdf"
        s3_key = f"users/{self.user_id}/audit-exports/{filename}"
        storage_service.upload(s3_key, pdf_bytes)

        document = Document(
            user_id=self.user_id,
            invoice_id=invoice_id,
            type=DocumentType.AUDIT_TRAIL_EXPORT,
            stage=invoice.escalation_stage,
            s3_key=s3_key,
            filename=filename,
            size_bytes=len(pdf_bytes),
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_download_url(self, document_id: str) -> str:
        document = self.scoped.find_document(document_id)
        if not document:
            raise NotFoundError("Document not found")
        document.download_count += 1
        document.last_downloaded_at = datetime.now(timezone.utc)
        self.db.commit()
        self.audit.log(
            user_id=self.user_id,
            invoice_id=document.invoice_id,
            event_type=AuditEventType.DOCUMENT_DOWNLOADED,
            actor=AuditActor.USER,
            description=f"Downloaded {document.type.value}: {document.filename}",
            document_id=document.id,
            document_type=document.type,
        )
        return storage_service.get_signed_download_url(document.s3_key)
