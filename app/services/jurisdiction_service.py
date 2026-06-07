"""Jurisdiction-aware interest calculation."""

from app.legal_templates.jurisdictions import JurisdictionConfig


def calculate_accrued_interest(principal_cents: int, days_overdue: int, jurisdiction: JurisdictionConfig) -> int:
    if days_overdue <= 0:
        return 0
    annual_rate = jurisdiction.late_interest_rate_annual / 100
    daily_rate = annual_rate / 365
    interest = principal_cents * daily_rate * days_overdue
    return round(interest)


def format_currency(amount_cents: int | float, currency: str = "USD") -> str:
    symbols = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$"}
    symbol = symbols.get(currency, f"{currency} ")
    value = float(amount_cents) / 100
    return f"{symbol}{value:,.2f}"
