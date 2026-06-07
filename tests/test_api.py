"""Test suite for FreelanceShield."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.services import auth_service


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    email = f"test-{datetime.now().timestamp()}@example.com"
    r = client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": "securepassword123",
        "name": "Test User",
    })
    token = r.json()["data"]["verificationToken"]
    auth_service.verify_email(SessionLocal(), token)
    client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    return client


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_signup_and_login(client):
    email = f"signup-{datetime.now().timestamp()}@example.com"
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "password": "securepassword123", "name": "New User",
    })
    assert r.status_code == 200
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_create_client_and_invoice(auth_client):
    r = auth_client.post("/api/v1/clients", json={"name": "Acme", "email": "acme@test.com"})
    assert r.status_code == 201
    client_id = r.json()["id"]

    now = datetime.now(timezone.utc)
    r = auth_client.post("/api/v1/invoices", json={
        "clientId": client_id,
        "invoiceNumber": f"INV-{int(now.timestamp())}",
        "amount": 1000,
        "currency": "USD",
        "issuedAt": (now - timedelta(days=30)).isoformat(),
        "dueAt": (now - timedelta(days=10)).isoformat(),
    })
    assert r.status_code == 201


def test_jurisdictions(client):
    r = client.get("/api/v1/jurisdictions")
    assert r.status_code == 200
    assert len(r.json()) >= 5


def test_csv_import(auth_client):
    csv_content = (
        "invoiceNumber,clientName,clientEmail,amount,currency,issuedDate,dueDate\n"
        "CSV-001,CSV Client,csv@test.com,250.00,USD,2024-01-01,2024-02-01\n"
    )
    r = auth_client.post(
        "/api/v1/imports/csv",
        files={"file": ("invoices.csv", csv_content.encode(), "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["created"] >= 1


def test_billing_plans(client):
    r = client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    assert len(r.json()["plans"]) == 3


def test_dashboard(auth_client):
    r = auth_client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    assert "totalOutstanding" in r.json()
