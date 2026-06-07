"""Scheduled background jobs — overdue updates, auto-escalation, queue processing."""

import asyncio

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.jobs.worker import process_pending_jobs
from app.lib.logger import get_logger
from app.models import User
from app.services.escalation_service import EscalationService
from app.services.invoice_service import InvoiceService

logger = get_logger(__name__)
_scheduler: BackgroundScheduler | None = None


def update_days_overdue_all_users() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.deleted_at.is_(None)).all()
        for user in users:
            InvoiceService(db, user.id).update_days_overdue()
        logger.info("Updated days overdue for %d users", len(users))
    finally:
        db.close()


def process_auto_advances_all_users() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.deleted_at.is_(None)).all()
        total = 0
        for user in users:
            count = EscalationService(db, user.id).process_auto_advances()
            total += count
        if total:
            logger.info("Processed %d auto-advances", total)
    finally:
        db.close()


def run_queue_worker() -> None:
    processed = asyncio.run(process_pending_jobs())
    if processed:
        logger.info("Processed %d queued jobs", processed)


def run_daily_jobs() -> None:
    update_days_overdue_all_users()
    process_auto_advances_all_users()
    run_queue_worker()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    settings = get_settings()
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(update_days_overdue_all_users, "cron", hour=0, minute=0, id="daily-overdue")
    _scheduler.add_job(process_auto_advances_all_users, "interval", hours=1, id="hourly-auto-advance")
    _scheduler.add_job(
        run_queue_worker,
        "interval",
        seconds=settings.job_poll_interval_seconds,
        id="queue-worker",
    )
    _scheduler.start()
    logger.info("Background scheduler started")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
