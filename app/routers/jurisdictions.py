"""Jurisdiction reference routes."""

from fastapi import APIRouter

from app.legal_templates.jurisdictions import JURISDICTIONS, list_jurisdiction_codes

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


@router.get("")
def list_jurisdictions():
    return [
        {
            "code": j.code,
            "name": j.name,
            "type": j.type.value,
            "currency": j.currency,
            "smallClaimsLimit": j.small_claims_limit,
            "lateInterestRateAnnual": j.late_interest_rate_annual,
        }
        for j in JURISDICTIONS.values()
    ]


@router.get("/{code}")
def get_jurisdiction_detail(code: str):
    from app.legal_templates.jurisdictions import get_jurisdiction

    j = get_jurisdiction(code)
    return {
        "code": j.code,
        "name": j.name,
        "type": j.type.value,
        "currency": j.currency,
        "smallClaimsLimit": j.small_claims_limit,
        "smallClaimsCourtName": j.small_claims_court_name,
        "lateInterestRateAnnual": j.late_interest_rate_annual,
        "lateInterestStatute": j.late_interest_statute,
        "demandLetterNoticeDays": j.demand_letter_notice_days,
        "primaryStatutes": j.primary_statutes,
        "smallClaimsFilingFee": j.small_claims_filing_fee,
        "claimsFormName": j.claims_form_name,
        "filingUrl": j.filing_url,
    }
