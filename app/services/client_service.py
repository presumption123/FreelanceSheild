"""Client CRUD and stats."""

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.lib.scoped import ScopedQueries
from app.models import Client, Invoice, InvoiceStatus
from app.schemas import CreateClientRequest, UpdateClientRequest


class ClientService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.scoped = ScopedQueries(db, user_id)

    def list_clients(self) -> list[Client]:
        return (
            self.db.query(Client)
            .filter(Client.user_id == self.user_id, Client.deleted_at.is_(None))
            .order_by(Client.total_outstanding.desc())
            .all()
        )

    def get_client(self, client_id: str) -> Client:
        client = self.scoped.find_client(client_id)
        if not client or client.deleted_at:
            raise NotFoundError("Client not found")
        return client

    def create_client(self, data: CreateClientRequest) -> Client:
        existing = (
            self.db.query(Client)
            .filter(Client.user_id == self.user_id, Client.email == data.email.lower())
            .first()
        )
        if existing:
            raise ConflictError(f"Client with email {data.email} already exists")

        client = Client(
            user_id=self.user_id,
            name=data.name.strip(),
            company_name=data.company_name,
            email=data.email.lower(),
            phone=data.phone,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state_province=data.state_province,
            postal_code=data.postal_code,
            country=data.country,
            jurisdiction_code=data.jurisdiction_code or "CA",
            notes=data.notes,
            auto_advance=data.auto_advance,
        )
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def update_client(self, client_id: str, data: UpdateClientRequest) -> Client:
        client = self.get_client(client_id)
        updates = data.model_dump(exclude_unset=True)
        if "email" in updates and updates["email"]:
            updates["email"] = updates["email"].lower()
        for field, value in updates.items():
            setattr(client, field, value)
        self.db.commit()
        self.db.refresh(client)
        return client

    def update_client_stats(self, client_id: str) -> None:
        client = self.get_client(client_id)
        invoices = self.db.query(Invoice).filter(Invoice.client_id == client_id, Invoice.deleted_at.is_(None)).all()

        total_invoiced = Decimal("0")
        total_outstanding = Decimal("0")
        total_paid = Decimal("0")
        overdue_count = 0

        for inv in invoices:
            total_invoiced += inv.amount
            total_paid += inv.amount_paid
            if inv.status not in (InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF, InvoiceStatus.DRAFT):
                total_outstanding += inv.amount - inv.amount_paid
            if inv.status in (InvoiceStatus.OVERDUE, InvoiceStatus.IN_ENFORCEMENT):
                overdue_count += 1

        client.total_invoiced = total_invoiced
        client.total_outstanding = total_outstanding
        client.total_paid = total_paid
        client.invoice_count = len(invoices)
        client.overdue_count = overdue_count
        self.db.commit()

    def update_risk_scores(self) -> None:
        clients = self.db.query(Client).filter(Client.user_id == self.user_id).all()
        for client in clients:
            invoices = self.db.query(Invoice).filter(Invoice.client_id == client.id).all()
            score = 0
            for inv in invoices:
                if inv.status in (InvoiceStatus.OVERDUE, InvoiceStatus.IN_ENFORCEMENT):
                    score += 20 + inv.days_overdue // 5
                if inv.status == InvoiceStatus.WRITTEN_OFF:
                    score += 30
                if inv.status == InvoiceStatus.PAID:
                    score -= 5
            client.risk_score = max(0, min(100, score))
        self.db.commit()
