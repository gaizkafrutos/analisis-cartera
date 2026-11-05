from datetime import date

import pytest

from radiografia.reporting.formatting import (
    format_date,
    format_eur,
    format_number,
    format_percent,
    short_fund_name,
)


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [(1234.5, 2, "1.234,50"), (19.6, 2, "19,60"), (1234567.891, 0, "1.234.568"), (0, 2, "0,00")],
)
def test_spanish_number_format(value, decimals, expected):
    assert format_number(value, decimals) == expected


def test_eur_and_percent():
    assert format_eur(6000) == "6.000,00 €"
    assert format_percent(0.00196, decimals=3) == "0,196 %"
    assert format_percent(0.002) == "0,20 %"
    assert format_eur(None) == "—"
    assert format_percent(None) == "—"


def test_date():
    assert format_date(date(2026, 11, 5)) == "5 nov 2026"
    assert format_date(None) == "—"


def test_short_fund_name():
    assert short_fund_name("iShares Core MSCI World UCITS ETF") == "Core MSCI World"
    assert short_fund_name("iShares MSCI World EUR Hedged UCITS ETF (Acc)") == (
        "MSCI World EUR Hedged (Acc)"
    )
    assert short_fund_name("IE00BK5BQT80") == "IE00BK5BQT80"
