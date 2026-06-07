"""Application configuration validated at startup."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite:///./freelanceshield.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    session_secret: str = Field(min_length=64, alias="SESSION_SECRET")
    encryption_key: str = Field(min_length=64, alias="ENCRYPTION_KEY")
    portal_hmac_secret: str = Field(min_length=64, alias="PORTAL_HMAC_SECRET")

    email_provider: Literal["console", "resend", "sendgrid"] = Field(default="console", alias="EMAIL_PROVIDER")
    email_from: str = Field(default="noreply@freelanceshield.com", alias="EMAIL_FROM")
    email_from_name: str = Field(default="FreelanceShield", alias="EMAIL_FROM_NAME")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    sendgrid_api_key: str | None = Field(default=None, alias="SENDGRID_API_KEY")

    storage_backend: Literal["local", "s3"] = Field(default="local", alias="STORAGE_BACKEND")
    local_storage_path: str = Field(default="./storage", alias="LOCAL_STORAGE_PATH")
    s3_bucket: str = Field(default="freelanceshield-documents", alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    app_url: str = Field(default="http://localhost:8000", alias="APP_URL")
    portal_url: str = Field(default="http://localhost:8000/portal", alias="PORTAL_URL")
    node_env: Literal["development", "production", "test"] = Field(default="development", alias="NODE_ENV")

    # Stripe billing
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_starter_price_id: str | None = Field(default=None, alias="STRIPE_STARTER_PRICE_ID")
    stripe_pro_price_id: str | None = Field(default=None, alias="STRIPE_PRO_PRICE_ID")

    # OAuth integrations
    freshbooks_client_id: str | None = Field(default=None, alias="FRESHBOOKS_CLIENT_ID")
    freshbooks_client_secret: str | None = Field(default=None, alias="FRESHBOOKS_CLIENT_SECRET")
    quickbooks_client_id: str | None = Field(default=None, alias="QUICKBOOKS_CLIENT_ID")
    quickbooks_client_secret: str | None = Field(default=None, alias="QUICKBOOKS_CLIENT_SECRET")
    wave_client_id: str | None = Field(default=None, alias="WAVE_CLIENT_ID")
    wave_client_secret: str | None = Field(default=None, alias="WAVE_CLIENT_SECRET")

    # Scheduler
    enable_scheduler: bool = Field(default=True, alias="ENABLE_SCHEDULER")
    job_poll_interval_seconds: int = Field(default=60, alias="JOB_POLL_INTERVAL_SECONDS")

    @field_validator("encryption_key", "session_secret", "portal_hmac_secret")
    @classmethod
    def validate_hex_key(cls, value: str) -> str:
        if len(value) < 64:
            raise ValueError("Key must be at least 64 characters")
        return value

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
