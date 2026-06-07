"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.middleware.errors import register_exception_handlers
from app.routers import (
    audit,
    auth,
    billing,
    clients,
    dashboard,
    documents,
    escalations,
    imports,
    integrations,
    invoices,
    jurisdictions,
    portal,
    settings as settings_router,
    storage,
    web,
    webhooks,
)

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.enable_scheduler:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="FreelanceShield API",
    description="Late-payment enforcement SaaS for freelancers",
    version="0.2.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(clients.router, prefix=api_prefix)
app.include_router(invoices.router, prefix=api_prefix)
app.include_router(escalations.router, prefix=api_prefix)
app.include_router(documents.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(portal.router, prefix=api_prefix)
app.include_router(jurisdictions.router, prefix=api_prefix)
app.include_router(storage.router, prefix=api_prefix)
app.include_router(imports.router, prefix=api_prefix)
app.include_router(integrations.router, prefix=api_prefix)
app.include_router(billing.router, prefix=api_prefix)
app.include_router(webhooks.router, prefix=api_prefix)
app.include_router(settings_router.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)
app.include_router(web.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "FreelanceShield", "version": "0.2.0"}


@app.get("/")
def root():
    return {
        "service": "FreelanceShield",
        "docs": "/docs",
        "dashboard": "/app",
        "api": "/api/v1",
    }
