"""Spanish number formatting for the UI (1.234,56 €; 0,20 %). Presentation only, no maths."""

from __future__ import annotations

from datetime import date

_MONTHS = (
    "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic",
)  # fmt: skip


def format_number(value: float, decimals: int = 2) -> str:
    """1234.5 -> '1.234,50' (Spanish separators)."""
    english = f"{value:,.{decimals}f}"
    return english.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


def format_eur(value: float | None, decimals: int = 2) -> str:
    return "—" if value is None else f"{format_number(value, decimals)} €"


def format_percent(fraction: float | None, decimals: int = 2) -> str:
    """0.00196 -> '0,20 %'. Input is a fraction, as stored everywhere in the engine."""
    return "—" if fraction is None else f"{format_number(fraction * 100, decimals)} %"


def short_fund_name(name: str) -> str:
    """'iShares Core MSCI World UCITS ETF' -> 'Core MSCI World' (fits on a phone screen)."""
    short = name.removeprefix("iShares ").replace(" UCITS ETF", "").strip()
    return short or name


def format_date(value: date | None) -> str:
    """date(2026, 11, 5) -> '5 nov 2026'."""
    return "—" if value is None else f"{value.day} {_MONTHS[value.month - 1]} {value.year}"
