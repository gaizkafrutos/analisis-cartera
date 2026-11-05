"""Holdings CSV and exposure-breakdown parsers on small synthetic files."""

from datetime import date

import pandas as pd
import pytest

from radiografia.analytics.fund_breakdown import fund_breakdown
from radiografia.data.sources.ishares import IsharesFormatError
from radiografia.data.sources.ishares_holdings import (
    holdings_csv_url,
    parse_exposure_breakdowns,
    parse_holdings_csv,
)

HEADER = (
    "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,"
    "Location,Exchange,Market Currency"
)
CSV = "\n".join(
    [
        '﻿Fund Holdings as of,"04/Nov/2026"',
        "",
        HEADER,
        '"AAPL","APPLE","Information Technology","Equity","6,000.00","60.00","6,000.00",'
        '"10.00","600.00","United States","NASDAQ","USD"',
        '"NESN","NESTLE SA","Consumer Staples","Equity","3,500.00","35.00","3,500.00",'
        '"5.00","700.00","Switzerland","SIX Swiss Exchange","CHF"',
        '"USD","USD CASH","Cash and/or Derivatives","Cash","500.00","5.00","500.00",'
        '"500.00","100.00","United States","-","USD"',
        '"ESZ6","S&P500 EMINI DEC 26","Cash and/or Derivatives","Futures","0.00","0.00",'
        '"400.00","1.00","-","-","Index And Options Market","USD"',
        "",
        '"The content contained herein is owned or licensed by BlackRock."',
    ]
)


def test_parse_holdings_csv():
    parsed = parse_holdings_csv(CSV)
    assert parsed.as_of == date(2026, 11, 4)
    holdings = parsed.holdings
    assert list(holdings["ticker"]) == ["AAPL", "NESN", "USD", "ESZ6"]  # trailing note ignored
    assert holdings.loc[0, "market_value"] == 6000.0
    assert holdings.loc[1, "location"] == "Switzerland"
    assert holdings.loc[0, "weight_published"] == pytest.approx(0.60)  # percent -> fraction
    assert holdings.loc[3, "notional_value"] == 400.0  # futures: exposure is the notional
    assert holdings.loc[3, "location"] == "-"


def test_holdings_csv_must_start_with_as_of_line():
    with pytest.raises(IsharesFormatError):
        parse_holdings_csv("Ticker,Name\n")


def test_holdings_csv_missing_columns():
    with pytest.raises(IsharesFormatError, match="lacks columns"):
        parse_holdings_csv('Fund Holdings as of,"04/Nov/2026"\n\nTicker,Name\n"A","B"\n')


def test_holdings_csv_url_from_page():
    html = '<a href="/uk/individual/en/products/1/x/latest-holdings.csv?a=1&amp;b=2">CSV</a>'
    assert holdings_csv_url(html) == (
        "https://www.ishares.com/uk/individual/en/products/1/x/latest-holdings.csv?a=1&b=2"
    )


def test_parse_exposure_breakdowns():
    rows = [
        ["Sector"],
        ["as of", "04/Nov/2026"],
        ["Type", "Fund", ""],
        ["Information Technology", "60.00"],
        ["Cash and/or Derivatives", "5.00"],
        [],
        [],
        ["Geography/Locations"],
        ["as of", "01/Oct/2026"],
        ["Type", "Fund", "", ""],
        ["United States", "65.00", "US"],
        ["Other", "35.00", "OTHR"],
        [],
        ["Allocations are subject to change."],
    ]
    parsed = parse_exposure_breakdowns(rows)
    assert list(parsed["section"]) == ["Sector"] * 2 + ["Geography/Locations"] * 2
    assert parsed.loc[2, "code"] == "US"
    assert pd.isna(parsed.loc[0, "code"])  # sector rows carry no country code
    assert parsed.loc[2, "as_of"] == date(2026, 10, 1)
    assert parsed["weight"].tolist() == pytest.approx([0.60, 0.05, 0.65, 0.35])


def test_no_sections_is_an_error():
    with pytest.raises(IsharesFormatError):
        parse_exposure_breakdowns([["Allocations are subject to change."]])


def test_parsed_csv_feeds_the_breakdown():
    holdings = parse_holdings_csv(CSV).holdings
    assert fund_breakdown(holdings, "location").to_dict() == pytest.approx(
        {"United States": 0.60, "Switzerland": 0.35, "Cash and/or Derivatives": 0.05}
    )
