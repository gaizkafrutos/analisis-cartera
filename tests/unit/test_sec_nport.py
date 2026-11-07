"""SEC N-PORT reader, on a small synthetic filing with the structure of a real one."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from radiografia.analytics.fund_breakdown import is_cash_like
from radiografia.data.sources import sec_nport

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nport_small.xml"


@pytest.fixture
def filing():
    return sec_nport.parse_nport(FIXTURE.read_bytes())


def test_general_information(filing):
    assert filing.series_id == "S000000001"
    assert filing.series_name == "Example World ETF"
    assert filing.report_date == date(2026, 7, 31)  # repPdDate, not the fiscal year end


def test_holdings_use_the_engine_columns(filing):
    h = filing.holdings
    assert list(h.columns) == sec_nport.HOLDING_COLUMNS
    alphabet = h.iloc[0]
    assert alphabet["location"] == "United States"
    assert alphabet["market_currency"] == "USD"
    assert alphabet["security_isin"] == "US02079K3059"
    assert alphabet["ticker"] == "GOOGL"
    assert alphabet["asset_class"] == "Equity"
    assert alphabet["weight_published"] == pytest.approx(0.60)
    assert h["sector"].isna().all()  # N-PORT has no sectors


def test_non_usd_currency_and_unknown_country(filing):
    foreign = filing.holdings.iloc[1]
    assert foreign["market_currency"] == "AED"  # from currencyConditional
    assert foreign["location"] == "United Arab Emirates"


def test_cash_and_derivatives_are_cash_like(filing):
    h = filing.holdings
    assert list(is_cash_like(h)) == [False, False, True, True]
    money_market = h.iloc[2]
    assert pd.isna(money_market["lei"]) and pd.isna(money_market["ticker"])  # "N/A" -> missing


def test_monthly_returns_are_dated_month_ends(filing):
    r = filing.monthly_returns
    assert list(r["month_end"]) == [date(2026, 5, 31), date(2026, 6, 30), date(2026, 7, 31)]
    assert list(r["total_return"]) == pytest.approx([0.048, -0.0045, -0.0036])
    assert set(r["class_id"]) == {"C000000001"}


def test_bad_files_are_errors():
    with pytest.raises(sec_nport.NportFormatError):
        sec_nport.parse_nport(b"<not xml")
    with pytest.raises(sec_nport.NportFormatError):
        sec_nport.parse_nport(b'<edgarSubmission xmlns="http://www.sec.gov/edgar/nport"/>')


def test_harmonise_companies_merges_spellings_by_lei():
    holdings = pd.DataFrame(
        {
            "name": ["Alphabet, Inc.", "ALPHABET INC.", "ALPHABET INC.", "No LEI Corp"],
            "location": ["United States"] * 3 + ["Japan"],
            "lei": ["L1", "L1", "L1", None],
        }
    )
    result = sec_nport.harmonise_companies(holdings)
    assert list(result["name"]) == ["ALPHABET INC."] * 3 + ["No LEI Corp"]
