"""Client routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.schemas import ClientResponse, CreateClientRequest, UpdateClientRequest
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientResponse])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = ClientService(db, user.id)
    clients = service.list_clients()
    return [
        ClientResponse(
            id=c.id,
            name=c.name,
            companyName=c.company_name,
            email=c.email,
            phone=c.phone,
            totalOutstanding=c.total_outstanding,
            overdueCount=c.overdue_count,
            riskScore=c.risk_score,
            autoAdvance=c.auto_advance,
        )
        for c in clients
    ]


@router.post("", response_model=ClientResponse, status_code=201)
def create_client(
    data: CreateClientRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = ClientService(db, user.id)
    client = service.create_client(data)
    return ClientResponse(
        id=client.id,
        name=client.name,
        companyName=client.company_name,
        email=client.email,
        phone=client.phone,
        totalOutstanding=client.total_outstanding,
        overdueCount=client.overdue_count,
        riskScore=client.risk_score,
        autoAdvance=client.auto_advance,
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = ClientService(db, user.id)
    client = service.get_client(client_id)
    return ClientResponse(
        id=client.id,
        name=client.name,
        companyName=client.company_name,
        email=client.email,
        phone=client.phone,
        totalOutstanding=client.total_outstanding,
        overdueCount=client.overdue_count,
        riskScore=client.risk_score,
        autoAdvance=client.auto_advance,
    )


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: str,
    data: UpdateClientRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    service = ClientService(db, user.id)
    client = service.update_client(client_id, data)
    return ClientResponse(
        id=client.id,
        name=client.name,
        companyName=client.company_name,
        email=client.email,
        phone=client.phone,
        totalOutstanding=client.total_outstanding,
        overdueCount=client.overdue_count,
        riskScore=client.risk_score,
        autoAdvance=client.auto_advance,
    )
