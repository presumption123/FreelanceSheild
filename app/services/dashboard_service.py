"""Dashboard aging summary."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import EscalationStage, Invoice, InvoiceStatus
from app.schemas import AgingBucket, DashboardSummary


class DashboardService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_summary(self) -> DashboardSummary:
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.user_id == self.user_id, Invoice.deleted_at.is_(None))
            .all()
        )

        total_outstanding = 0.0
        overdue_count = 0
        enforcement_active = 0
        paid_count = 0
        resolved_this_month = 0
        payment_days: list[int] = []

        now = datetime.now(timezone.utc)
        buckets_def = [
            ("Current", 0, 0),
            ("1-30 days", 1, 30),
            ("31-60 days", 31, 60),
            ("61-90 days", 61, 90),
            ("90+ days", 91, None),
        ]
        bucket_totals = {label: {"count": 0, "amount": 0.0} for label, _, _ in buckets_def}

        for inv in invoices:
            outstanding = float(inv.amount - inv.amount_paid)
            if inv.status not in (InvoiceStatus.PAID, InvoiceStatus.WRITTEN_OFF, InvoiceStatus.DRAFT):
                total_outstanding += outstanding

            if inv.status in (InvoiceStatus.OVERDUE, InvoiceStatus.IN_ENFORCEMENT):
                overdue_count += 1

            if inv.status == InvoiceStatus.IN_ENFORCEMENT:
                enforcement_active += 1

            if inv.status == InvoiceStatus.PAID and inv.paid_at:
                paid_count += 1
                if inv.paid_at.month == now.month and inv.paid_at.year == now.year:
                    resolved_this_month += 1
                days = (inv.paid_at - inv.due_at).days
                payment_days.append(days)

            days = inv.days_overdue
            for label, min_d, max_d in buckets_def:
                if max_d is None and days >= min_d:
                    bucket_totals[label]["count"] += 1
                    bucket_totals[label]["amount"] += outstanding
                    break
                if max_d is not None and min_d <= days <= max_d:
                    bucket_totals[label]["count"] += 1
                    bucket_totals[label]["amount"] += outstanding
                    break
                if label == "Current" and days == 0 and inv.status not in (
                    InvoiceStatus.PAID,
                    InvoiceStatus.WRITTEN_OFF,
                ):
                    bucket_totals[label]["count"] += 1
                    bucket_totals[label]["amount"] += outstanding

        aging_buckets = [
            AgingBucket(
                label=label,
                daysMin=min_d,
                daysMax=max_d,
                invoiceCount=bucket_totals[label]["count"],
                totalAmount=bucket_totals[label]["amount"],
            )
            for label, min_d, max_d in buckets_def
        ]

        collection_rate = paid_count / len(invoices) if invoices else 0.0
        avg_days = sum(payment_days) / len(payment_days) if payment_days else 0.0

        return DashboardSummary(
            totalOutstanding=total_outstanding,
            overdueCount=overdue_count,
            averageDaysToPayment=avg_days,
            enforcementActiveCount=enforcement_active,
            resolvedThisMonth=resolved_this_month,
            collectionRate=collection_rate,
            agingBuckets=aging_buckets,
        )
