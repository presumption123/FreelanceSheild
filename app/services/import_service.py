"""CSV invoice import service."""

import csv
import io
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.models import AuditActor, AuditEventType, Client, Invoice, InvoiceSource, InvoiceStatus
from app.services.audit_service import AuditService
from app.services.client_service import ClientService


class CsvImportRow(BaseModel):
    invoice_number: str = Field(alias="invoiceNumber")
    client_name: str = Field(alias="clientName")
    client_email: EmailStr = Field(alias="clientEmail")
    amount: str
    currency: str
    issued_date: str = Field(alias="issuedDate")
    due_date: str = Field(alias="dueDate")
    status: str | None = None
    description: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        if not v.replace(".", "", 1).isdigit():
            raise ValueError("Must be a number")
        return v


class ImportRowError(BaseModel):
    row: int
    field: str | None = None
    message: str
    raw_data: dict


class ImportResult(BaseModel):
    total: int
    created: int
    skipped: int
    errors: list[ImportRowError]


CSV_HEADERS = {
    "invoice_number": "invoiceNumber",
    "invoice number": "invoiceNumber",
    "invoicenumber": "invoiceNumber",
    "client_name": "clientName",
    "client name": "clientName",
    "clientname": "clientName",
    "client_email": "clientEmail",
    "client email": "clientEmail",
    "clientemail": "clientEmail",
    "amount": "amount",
    "currency": "currency",
    "issued_date": "issuedDate",
    "issued date": "issuedDate",
    "issueddate": "issuedDate",
    "due_date": "dueDate",
    "due date": "dueDate",
    "duedate": "dueDate",
    "status": "status",
    "description": "description",
}


class ImportService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.audit = AuditService(db)
        self.clients = ClientService(db, user_id)

    def _normalize_row(self, raw: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in raw.items():
            canonical = CSV_HEADERS.get(key.strip().lower())
            if canonical:
                normalized[canonical] = value.strip()
        return normalized

    def _get_or_create_client(self, name: str, email: str) -> Client:
        client = (
            self.db.query(Client)
            .filter(Client.user_id == self.user_id, Client.email == email.lower())
            .first()
        )
        if client:
            return client
        client = Client(user_id=self.user_id, name=name, email=email.lower())
        self.db.add(client)
        self.db.flush()
        return client

    def import_csv(self, file_content: bytes) -> ImportResult:
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("File must be valid UTF-8 CSV") from exc

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        created = 0
        skipped = 0
        errors: list[ImportRowError] = []
        rows = list(reader)

        for row_num, raw_row in enumerate(rows, start=2):
            normalized = self._normalize_row({k: v or "" for k, v in raw_row.items()})
            try:
                parsed = CsvImportRow.model_validate(normalized)
            except Exception as exc:
                errors.append(ImportRowError(row=row_num, message=str(exc), raw_data=normalized))
                continue

            existing = (
                self.db.query(Invoice)
                .filter(
                    Invoice.user_id == self.user_id,
                    Invoice.invoice_number == parsed.invoice_number,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            client = self._get_or_create_client(parsed.client_name, str(parsed.client_email))
            issued_at = datetime.strptime(parsed.issued_date, "%Y-%m-%d")
            due_at = datetime.strptime(parsed.due_date, "%Y-%m-%d")
            status = InvoiceStatus.SENT
            if parsed.status:
                try:
                    status = InvoiceStatus(parsed.status.upper())
                except ValueError:
                    pass

            invoice = Invoice(
                user_id=self.user_id,
                client_id=client.id,
                invoice_number=parsed.invoice_number,
                amount=Decimal(parsed.amount),
                currency=parsed.currency.upper(),
                issued_at=issued_at,
                due_at=due_at,
                description=parsed.description,
                status=status,
                source=InvoiceSource.CSV_IMPORT,
            )
            self.db.add(invoice)
            created += 1

        self.db.commit()
        self.clients.update_risk_scores()

        self.audit.log(
            user_id=self.user_id,
            event_type=AuditEventType.INTEGRATION_SYNCED,
            actor=AuditActor.USER,
            description=f"CSV import: {created} created, {skipped} skipped, {len(errors)} errors",
            metadata={"source": "CSV_IMPORT", "created": created, "skipped": skipped},
        )

        return ImportResult(total=len(rows), created=created, skipped=skipped, errors=errors)
