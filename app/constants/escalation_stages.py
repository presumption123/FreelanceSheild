"""Shared constants for escalation stages and plans."""

from dataclasses import dataclass
from typing import Literal

from app.models import DocumentType, EscalationStage, Plan

PLAN_LIMITS: dict[Plan, int | None] = {
    Plan.FREE: 3,
    Plan.STARTER: 25,
    Plan.PRO: None,
}

PLAN_ORDER: dict[Plan, int] = {
    Plan.FREE: 0,
    Plan.STARTER: 1,
    Plan.PRO: 2,
}


@dataclass(frozen=True)
class StageConfig:
    stage: EscalationStage
    label: str
    description: str
    trigger_days_overdue: int
    email_template_key: str
    generates_document: bool
    document_type: DocumentType | None
    requires_user_approval: bool
    legal_weight: Literal["low", "medium", "high", "formal"]


STAGE_CONFIGS: dict[EscalationStage, StageConfig] = {
    EscalationStage.NONE: StageConfig(
        stage=EscalationStage.NONE,
        label="None",
        description="No enforcement active.",
        trigger_days_overdue=0,
        email_template_key="none",
        generates_document=False,
        document_type=None,
        requires_user_approval=True,
        legal_weight="low",
    ),
    EscalationStage.REMINDER_1: StageConfig(
        stage=EscalationStage.REMINDER_1,
        label="Polite Reminder",
        description="A friendly reminder that the invoice is now past due.",
        trigger_days_overdue=1,
        email_template_key="reminder_1",
        generates_document=False,
        document_type=None,
        requires_user_approval=True,
        legal_weight="low",
    ),
    EscalationStage.REMINDER_2: StageConfig(
        stage=EscalationStage.REMINDER_2,
        label="Firm Follow-Up",
        description="A firmer message noting the number of days overdue.",
        trigger_days_overdue=7,
        email_template_key="reminder_2",
        generates_document=False,
        document_type=None,
        requires_user_approval=True,
        legal_weight="medium",
    ),
    EscalationStage.REMINDER_3: StageConfig(
        stage=EscalationStage.REMINDER_3,
        label="Relationship Warning",
        description="Notes the impact on the professional relationship and requests immediate action.",
        trigger_days_overdue=14,
        email_template_key="reminder_3",
        generates_document=False,
        document_type=None,
        requires_user_approval=True,
        legal_weight="medium",
    ),
    EscalationStage.DEMAND_LETTER: StageConfig(
        stage=EscalationStage.DEMAND_LETTER,
        label="Statutory Demand Letter",
        description="A formal demand letter with statutory interest, deadline, and legal consequences.",
        trigger_days_overdue=30,
        email_template_key="demand_letter",
        generates_document=True,
        document_type=DocumentType.DEMAND_LETTER,
        requires_user_approval=True,
        legal_weight="high",
    ),
    EscalationStage.FINAL_NOTICE: StageConfig(
        stage=EscalationStage.FINAL_NOTICE,
        label="Final Notice",
        description="Last warning before small claims filing. 7-day deadline.",
        trigger_days_overdue=45,
        email_template_key="final_notice",
        generates_document=True,
        document_type=DocumentType.FINAL_NOTICE,
        requires_user_approval=True,
        legal_weight="formal",
    ),
    EscalationStage.COURT_READY: StageConfig(
        stage=EscalationStage.COURT_READY,
        label="Court Packet Ready",
        description="Small claims court packet generated. Ready for filing.",
        trigger_days_overdue=52,
        email_template_key="court_notice",
        generates_document=True,
        document_type=DocumentType.SMALL_CLAIMS_PACKET,
        requires_user_approval=True,
        legal_weight="formal",
    ),
    EscalationStage.RESOLVED: StageConfig(
        stage=EscalationStage.RESOLVED,
        label="Resolved",
        description="Invoice paid or otherwise resolved.",
        trigger_days_overdue=0,
        email_template_key="resolved",
        generates_document=False,
        document_type=None,
        requires_user_approval=False,
        legal_weight="low",
    ),
    EscalationStage.WRITTEN_OFF: StageConfig(
        stage=EscalationStage.WRITTEN_OFF,
        label="Written Off",
        description="Invoice written off.",
        trigger_days_overdue=0,
        email_template_key="written_off",
        generates_document=False,
        document_type=None,
        requires_user_approval=False,
        legal_weight="low",
    ),
}

STAGE_ORDER: list[EscalationStage] = [
    EscalationStage.NONE,
    EscalationStage.REMINDER_1,
    EscalationStage.REMINDER_2,
    EscalationStage.REMINDER_3,
    EscalationStage.DEMAND_LETTER,
    EscalationStage.FINAL_NOTICE,
    EscalationStage.COURT_READY,
    EscalationStage.RESOLVED,
    EscalationStage.WRITTEN_OFF,
]

VALID_INVOICE_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SENT"},
    "SENT": {"OVERDUE", "PAID", "PARTIALLY_PAID", "WRITTEN_OFF", "DISPUTED"},
    "OVERDUE": {"IN_ENFORCEMENT", "PAID", "PARTIALLY_PAID", "WRITTEN_OFF", "DISPUTED"},
    "IN_ENFORCEMENT": {"PAID", "PARTIALLY_PAID", "WRITTEN_OFF", "DISPUTED"},
    "PARTIALLY_PAID": {"PAID", "WRITTEN_OFF", "DISPUTED"},
    "PAID": set(),
    "WRITTEN_OFF": set(),
    "DISPUTED": {"PAID", "PARTIALLY_PAID", "WRITTEN_OFF", "OVERDUE", "IN_ENFORCEMENT"},
}


def get_next_stage(current: EscalationStage) -> EscalationStage | None:
    try:
        idx = STAGE_ORDER.index(current)
    except ValueError:
        return None
    court_ready_idx = STAGE_ORDER.index(EscalationStage.COURT_READY)
    if idx >= court_ready_idx:
        return None
    return STAGE_ORDER[idx + 1]
