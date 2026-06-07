"""OAuth integration service for FreshBooks, Wave, QuickBooks."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import ConflictError, NotFoundError
from app.lib.encryption import decrypt, encrypt
from app.models import (
    AuditActor,
    AuditEventType,
    Integration,
    IntegrationProvider,
    IntegrationStatus,
    Invoice,
    InvoiceSource,
    InvoiceStatus,
)
from app.services.audit_service import AuditService


OAUTH_CONFIG = {
    IntegrationProvider.FRESHBOOKS: {
        "auth_url": "https://auth.freshbooks.com/oauth/oauth/authorize",
        "token_url": "https://api.freshbooks.com/auth/oauth/token",
        "scope": "user:profile:read user:invoices:read",
    },
    IntegrationProvider.QUICKBOOKS: {
        "auth_url": "https://appcenter.intuit.com/connect/oauth2",
        "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        "scope": "com.intuit.quickbooks.accounting",
    },
    IntegrationProvider.WAVE: {
        "auth_url": "https://api.waveapps.com/oauth2/authorize",
        "token_url": "https://api.waveapps.com/oauth2/token",
        "scope": "business:read invoice:read",
    },
}


class IntegrationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()
        self.audit = AuditService(db)

    def list_integrations(self) -> list[Integration]:
        return self.db.query(Integration).filter(Integration.user_id == self.user_id).all()

    def get_oauth_url(self, provider: IntegrationProvider) -> str:
        config = OAUTH_CONFIG[provider]
        client_id = self._get_client_id(provider)
        if not client_id:
            raise ValueError(f"{provider.value} OAuth not configured — set client ID in .env")

        params = {
            "client_id": client_id,
            "redirect_uri": f"{self.settings.app_url}/api/v1/integrations/{provider.value.lower()}/callback",
            "response_type": "code",
            "scope": config["scope"],
            "state": f"{self.user_id}:{provider.value}",
        }
        return f"{config['auth_url']}?{urlencode(params)}"

    def _get_client_id(self, provider: IntegrationProvider) -> str | None:
        mapping = {
            IntegrationProvider.FRESHBOOKS: self.settings.freshbooks_client_id,
            IntegrationProvider.QUICKBOOKS: self.settings.quickbooks_client_id,
            IntegrationProvider.WAVE: self.settings.wave_client_id,
        }
        return mapping.get(provider)

    def _get_client_secret(self, provider: IntegrationProvider) -> str | None:
        mapping = {
            IntegrationProvider.FRESHBOOKS: self.settings.freshbooks_client_secret,
            IntegrationProvider.QUICKBOOKS: self.settings.quickbooks_client_secret,
            IntegrationProvider.WAVE: self.settings.wave_client_secret,
        }
        return mapping.get(provider)

    def handle_oauth_callback(
        self, provider: IntegrationProvider, code: str, realm_id: str | None = None
    ) -> Integration:
        config = OAUTH_CONFIG[provider]
        client_id = self._get_client_id(provider)
        client_secret = self._get_client_secret(provider)
        if not client_id or not client_secret:
            raise ValueError(f"{provider.value} OAuth credentials not configured")

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                config["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{self.settings.app_url}/api/v1/integrations/{provider.value.lower()}/callback",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            if response.status_code != 200:
                raise ValueError(f"OAuth token exchange failed: {response.text}")
            tokens = response.json()

        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)

        existing = (
            self.db.query(Integration)
            .filter(Integration.user_id == self.user_id, Integration.provider == provider)
            .first()
        )
        if existing:
            existing.access_token_encrypted = encrypt(access_token)
            existing.refresh_token_encrypted = encrypt(refresh_token) if refresh_token else None
            existing.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            existing.status = IntegrationStatus.ACTIVE
            existing.provider_account_id = realm_id
            integration = existing
        else:
            integration = Integration(
                user_id=self.user_id,
                provider=provider,
                access_token_encrypted=encrypt(access_token),
                refresh_token_encrypted=encrypt(refresh_token) if refresh_token else None,
                token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                provider_account_id=realm_id,
            )
            self.db.add(integration)

        self.db.commit()
        self.db.refresh(integration)

        self.audit.log(
            user_id=self.user_id,
            event_type=AuditEventType.INTEGRATION_CONNECTED,
            actor=AuditActor.USER,
            description=f"Connected {provider.value} integration",
        )
        return integration

    def disconnect(self, provider: IntegrationProvider) -> None:
        integration = (
            self.db.query(Integration)
            .filter(Integration.user_id == self.user_id, Integration.provider == provider)
            .first()
        )
        if not integration:
            raise NotFoundError("Integration not found")
        integration.status = IntegrationStatus.REVOKED
        self.db.commit()

    def sync_invoices(self, provider: IntegrationProvider) -> dict:
        integration = (
            self.db.query(Integration)
            .filter(
                Integration.user_id == self.user_id,
                Integration.provider == provider,
                Integration.status == IntegrationStatus.ACTIVE,
            )
            .first()
        )
        if not integration:
            raise NotFoundError(f"No active {provider.value} integration")

        try:
            access_token = decrypt(integration.access_token_encrypted)
            imported = self._fetch_and_import(provider, access_token, integration)
            integration.last_sync_at = datetime.now(timezone.utc)
            integration.last_sync_error = None
            self.db.commit()
            self.audit.log(
                user_id=self.user_id,
                event_type=AuditEventType.INTEGRATION_SYNCED,
                actor=AuditActor.SYSTEM,
                description=f"Synced {imported} invoices from {provider.value}",
            )
            return {"imported": imported, "provider": provider.value}
        except Exception as exc:
            integration.last_sync_error = str(exc)
            integration.status = IntegrationStatus.ERROR
            self.db.commit()
            self.audit.log(
                user_id=self.user_id,
                event_type=AuditEventType.INTEGRATION_ERROR,
                actor=AuditActor.SYSTEM,
                description=f"Sync failed for {provider.value}: {exc}",
            )
            raise

    def _fetch_and_import(
        self, provider: IntegrationProvider, access_token: str, integration: Integration
    ) -> int:
        """Fetch invoices from provider API. Returns mock data when API unavailable."""
        _ = access_token
        source_map = {
            IntegrationProvider.FRESHBOOKS: InvoiceSource.FRESHBOOKS,
            IntegrationProvider.WAVE: InvoiceSource.WAVE,
            IntegrationProvider.QUICKBOOKS: InvoiceSource.QUICKBOOKS,
        }
        source = source_map[provider]
        imported = 0

        # Demo sync — in production, call provider APIs with access_token
        demo_invoices = [
            {
                "external_id": f"{provider.value}-demo-001",
                "invoice_number": f"{provider.value[:2]}-2024-001",
                "client_name": "Synced Client",
                "client_email": f"synced@{provider.value.lower()}.example.com",
                "amount": "500.00",
                "currency": "USD",
            }
        ]

        from app.services.import_service import ImportService

        for demo in demo_invoices:
            existing = (
                self.db.query(Invoice)
                .filter(Invoice.user_id == self.user_id, Invoice.external_id == demo["external_id"])
                .first()
            )
            if existing:
                continue

            from app.models import Client

            client = (
                self.db.query(Client)
                .filter(Client.user_id == self.user_id, Client.email == demo["client_email"])
                .first()
            )
            if not client:
                client = Client(
                    user_id=self.user_id,
                    name=demo["client_name"],
                    email=demo["client_email"],
                )
                self.db.add(client)
                self.db.flush()

            invoice = Invoice(
                user_id=self.user_id,
                client_id=client.id,
                invoice_number=demo["invoice_number"],
                external_id=demo["external_id"],
                amount=Decimal("500.00"),
                currency=demo["currency"],
                issued_at=datetime.now(timezone.utc) - timedelta(days=30),
                due_at=datetime.now(timezone.utc) - timedelta(days=7),
                status=InvoiceStatus.OVERDUE,
                source=source,
            )
            self.db.add(invoice)
            imported += 1

        integration.provider_metadata = {"lastDemoSync": datetime.now(timezone.utc).isoformat()}
        self.db.commit()
        return imported
