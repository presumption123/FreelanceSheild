"""Jurisdiction configuration types and registry."""

from dataclasses import dataclass, field
from typing import Literal

from app.models import JurisdictionType


@dataclass(frozen=True)
class UKCompensationAmounts:
    under1000: int
    under10000: int
    over10000: int


@dataclass(frozen=True)
class JurisdictionConfig:
    code: str
    name: str
    type: JurisdictionType
    currency: str
    small_claims_limit: int
    small_claims_court_name: str
    late_interest_rate_annual: float
    late_interest_statute: str
    demand_letter_notice_days: int
    primary_statutes: list[str]
    small_claims_filing_fee: int
    claims_form_name: str | None = None
    filing_url: str | None = None
    compensation_amounts: UKCompensationAmounts | None = None


# US States — representative sample + common states; extensible registry
US_STATES: dict[str, JurisdictionConfig] = {
    "CA": JurisdictionConfig(
        code="CA",
        name="California",
        type=JurisdictionType.US_STATE,
        currency="USD",
        small_claims_limit=1_000_000,
        small_claims_court_name="Superior Court of California (Small Claims Division)",
        late_interest_rate_annual=10.0,
        late_interest_statute="Cal. Civ. Code § 3289(b)",
        demand_letter_notice_days=30,
        primary_statutes=[
            "California Civil Code § 3289(b)",
            "California Code of Civil Procedure § 116.220 (Small Claims)",
        ],
        small_claims_filing_fee=3000,
        claims_form_name="SC-100",
        filing_url="https://courts.ca.gov/selfhelp/smallclaims",
    ),
    "NY": JurisdictionConfig(
        code="NY",
        name="New York",
        type=JurisdictionType.US_STATE,
        currency="USD",
        small_claims_limit=1_000_000,
        small_claims_court_name="New York City Civil Court (Small Claims Part) / City Court",
        late_interest_rate_annual=9.0,
        late_interest_statute="N.Y. C.P.L.R. § 5004",
        demand_letter_notice_days=30,
        primary_statutes=[
            "New York CPLR § 5004 (9% statutory interest)",
            "New York Uniform City Court Act § 1801 (Small Claims)",
        ],
        small_claims_filing_fee=1500,
        claims_form_name="Small Claims Summons",
        filing_url="https://www.nycourts.gov/courts/nyc/smallclaims/",
    ),
    "TX": JurisdictionConfig(
        code="TX",
        name="Texas",
        type=JurisdictionType.US_STATE,
        currency="USD",
        small_claims_limit=2_000_000,
        small_claims_court_name="Justice Court (Small Claims)",
        late_interest_rate_annual=6.0,
        late_interest_statute="Tex. Fin. Code § 302.002",
        demand_letter_notice_days=30,
        primary_statutes=["Texas Finance Code § 302.002"],
        small_claims_filing_fee=5000,
        claims_form_name="Small Claims Petition",
        filing_url="https://www.txcourts.gov/",
    ),
    "FL": JurisdictionConfig(
        code="FL",
        name="Florida",
        type=JurisdictionType.US_STATE,
        currency="USD",
        small_claims_limit=800_000,
        small_claims_court_name="County Court (Small Claims Division)",
        late_interest_rate_annual=8.0,
        late_interest_statute="Fla. Stat. § 55.03",
        demand_letter_notice_days=30,
        primary_statutes=["Florida Statutes § 55.03"],
        small_claims_filing_fee=3000,
        claims_form_name="Statement of Claim",
    ),
    "IL": JurisdictionConfig(
        code="IL",
        name="Illinois",
        type=JurisdictionType.US_STATE,
        currency="USD",
        small_claims_limit=1_000_000,
        small_claims_court_name="Circuit Court (Small Claims)",
        late_interest_rate_annual=5.0,
        late_interest_statute="815 ILCS 205/2",
        demand_letter_notice_days=30,
        primary_statutes=["815 ILCS 205/2"],
        small_claims_filing_fee=2500,
    ),
}

ENGLAND_WALES = JurisdictionConfig(
    code="england-wales",
    name="England and Wales",
    type=JurisdictionType.UK,
    currency="GBP",
    small_claims_limit=1_000_000,
    small_claims_court_name="County Court",
    late_interest_rate_annual=8.0,
    late_interest_statute="Late Payment of Commercial Debts (Interest) Act 1998, s.6(1)",
    demand_letter_notice_days=30,
    primary_statutes=[
        "Late Payment of Commercial Debts (Interest) Act 1998",
        "Late Payment of Commercial Debts Regulations 2002",
    ],
    small_claims_filing_fee=3500,
    claims_form_name="N1 Claim Form",
    filing_url="https://www.gov.uk/make-court-claim-for-money/overview",
    compensation_amounts=UKCompensationAmounts(under1000=4000, under10000=7000, over10000=10000),
)

JURISDICTIONS: dict[str, JurisdictionConfig] = {
    **US_STATES,
    "england-wales": ENGLAND_WALES,
}


def get_jurisdiction(code: str) -> JurisdictionConfig:
    jurisdiction = JURISDICTIONS.get(code)
    if not jurisdiction:
        raise ValueError(f"Unknown jurisdiction: {code}")
    return jurisdiction


def list_jurisdiction_codes() -> list[str]:
    return sorted(JURISDICTIONS.keys())
