"""Persistent job queue for emails and document generation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job_queue import JobStatus, QueuedJob


class QueueService:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        job_type: str,
        payload: dict,
        user_id: str | None = None,
        delay_seconds: int = 0,
    ) -> QueuedJob:
        scheduled = datetime.now(timezone.utc)
        if delay_seconds:
            from datetime import timedelta

            scheduled += timedelta(seconds=delay_seconds)

        job = QueuedJob(
            user_id=user_id,
            job_type=job_type,
            payload=payload,
            scheduled_at=scheduled,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def fetch_pending(self, limit: int = 10) -> list[QueuedJob]:
        now = datetime.now(timezone.utc)
        jobs = (
            self.db.query(QueuedJob)
            .filter(
                QueuedJob.status == JobStatus.PENDING,
                QueuedJob.scheduled_at <= now,
                QueuedJob.attempts < QueuedJob.max_attempts,
            )
            .order_by(QueuedJob.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        for job in jobs:
            job.status = JobStatus.PROCESSING
            job.started_at = now
            job.attempts += 1
        self.db.commit()
        return jobs

    def complete(self, job_id: str) -> None:
        job = self.db.query(QueuedJob).filter(QueuedJob.id == job_id).first()
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            self.db.commit()

    def fail(self, job_id: str, error: str) -> None:
        job = self.db.query(QueuedJob).filter(QueuedJob.id == job_id).first()
        if job:
            job.error_message = error
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.PENDING
            self.db.commit()
