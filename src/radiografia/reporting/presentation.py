"""Display helpers shared by the UI and the summary: Spanish names and chart-ready lists.

Presentation only: no financial calculation happens here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from radiografia.analytics.fund_breakdown import CASH_LABEL
from radiografia.domain.metrics import BreakdownItem, BreakdownResult

if TYPE_CHECKING:
    from radiografia.analytics.lookthrough import LookThroughResult

CASH_NAME = "Liquidez y derivados"
REST_NAME = "Resto"

COUNTRY_NAMES = {
    "United States": "EE. UU.",
    "Japan": "Japón",
    "United Kingdom": "Reino Unido",
    "Canada": "Canadá",
    "Switzerland": "Suiza",
    "France": "Francia",
    "Germany": "Alemania",
    "Netherlands": "Países Bajos",
    "Taiwan": "Taiwán",
    "China": "China",
    "India": "India",
    "Korea (South)": "Corea del Sur",
    "Australia": "Australia",
    "Italy": "Italia",
    "Spain": "España",
    "Sweden": "Suecia",
    "Denmark": "Dinamarca",
    "Brazil": "Brasil",
    "Ireland": "Irlanda",
    "Hong Kong": "Hong Kong",
    "Saudi Arabia": "Arabia Saudí",
    "South Africa": "Sudáfrica",
    "Belgium": "Bélgica",
    "Finland": "Finlandia",
    "Singapore": "Singapur",
    "Israel": "Israel",
    "Norway": "Noruega",
    "Mexico": "México",
}

CURRENCY_NAMES = {
    "USD": "dólar",
    "EUR": "euro",
    "JPY": "yen",
    "GBP": "libra",
    "CHF": "franco suizo",
    "CAD": "dólar canadiense",
    "TWD": "dólar taiwanés",
    "INR": "rupia india",
    "HKD": "dólar de Hong Kong",
    "KRW": "won",
    "CNY": "yuan",
    "AUD": "dólar australiano",
    "DKK": "corona danesa",
    "SEK": "corona sueca",
}

SECTOR_NAMES = {
    "Information Technology": "Tecnología",
    "Financials": "Financiero",
    "Industrials": "Industria",
    "Health Care": "Salud",
    "Consumer Discretionary": "Consumo no básico",
    "Communication": "Comunicaciones",
    "Consumer Staples": "Consumo básico",
    "Energy": "Energía",
    "Materials": "Materiales",
    "Utilities": "Servicios públicos",
    "Real Estate": "Inmobiliario",
}


def _with_cash(names: dict[str, str], label: str) -> str:
    return CASH_NAME if label == CASH_LABEL else names.get(label, label)


def country_name(label: str) -> str:
    return _with_cash(COUNTRY_NAMES, label)


def sector_name(label: str) -> str:
    return _with_cash(SECTOR_NAMES, label)


def currency_name(code: str) -> str:
    return CURRENCY_NAMES.get(code, code)


def with_reference(
    items: Iterable[BreakdownItem], reference: Iterable[BreakdownItem] | None, n: int
) -> list[tuple[str, float, float | None]]:
    """`top_with_rest` plus the reference index's weight for each row (None without reference).

    The reference's 'Resto' is everything it holds outside the rows shown, so both columns sum
    to the same total and are read on the same scale.
    """
    rows = top_with_rest(items, n)
    if reference is None:
        return [(label, weight, None) for label, weight in rows]
    ref = {item.label: item.weight for item in reference}
    shown = {label for label, _ in rows if label != REST_NAME}
    out = [(label, weight, ref.get(label, 0.0)) for label, weight in rows if label != REST_NAME]
    rest = sum(weight for label, weight in rows if label == REST_NAME)
    ref_rest = sum(weight for label, weight in ref.items() if label not in shown)
    if rest > 0 or ref_rest > 0:
        out.append((REST_NAME, rest, ref_rest))
    return out


def top_with_rest(items: Iterable[BreakdownItem], n: int) -> list[tuple[str, float]]:
    """The n largest items plus one 'Resto' bucket with the sum of the others (if any)."""
    items = list(items)
    head = [(item.label, item.weight) for item in items[:n]]
    rest = sum(item.weight for item in items[n:])
    if rest > 0:
        head.append((REST_NAME, rest))
    return head


def _weight_of(breakdown: BreakdownResult, label: str) -> float | None:
    if not breakdown.items:
        return None
    return next((item.weight for item in breakdown.items if item.label == label), 0.0)


def versus_rows(
    portfolio: LookThroughResult, reference: LookThroughResult | None
) -> list[tuple[str, float | None, float | None]]:
    """(row key, portfolio value, reference value) for the side-by-side block, read from the
    already computed look-throughs (no new calculation). Rows without a portfolio value are
    left out; no rows without a reference."""
    if reference is None:
        return []
    rows = [
        ("us", _weight_of(portfolio.geography, "United States"),
         _weight_of(reference.geography, "United States")),
        ("usd", _weight_of(portfolio.currency, "USD"), _weight_of(reference.currency, "USD")),
        ("top10", portfolio.top10_weight.value, reference.top10_weight.value),
        ("effective", portfolio.effective_companies.value, reference.effective_companies.value),
    ]  # fmt: skip
    return [row for row in rows if row[1] is not None]
