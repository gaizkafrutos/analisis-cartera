"""iShares price data: NAV history, published returns and distributions.

From the product workbook:
    - "Fund Header": NAV currency ("USD 146.38").
    - "Historical NAVs": daily NAV per share, in the NAV currency, since launch.
    - "Performance Returns": the issuer's total returns (gross income reinvested) and its
      benchmark's, used to validate our calculations and for the tracking difference.
    - "Portfolio Characteristics": e.g. 3-year standard deviation, used to validate volatility.
From the product page:
    - Distributions of distributing share classes (ex-date and amount), embedded as JSON. Needed
      for total return: the NAV of a distributing class drops on each ex-date.
"""

from __future__ import annotations

import itertools
import json
import re
from datetime import date
from html import unescape

import pandas as pd

from radiografia.data.sources.ishares import IsharesFormatError, parse_issuer_date

PERFORMANCE_COLUMNS = ["table", "as_of", "period", "start", "end", "fund", "benchmark"]
_DISCRETE_PERIOD = re.compile(
    r"From\s+(\d{1,2}-[A-Za-z]{3,4}-\d{4})\s+To\s+(\d{1,2}-[A-Za-z]{3,4}-\d{4})"
)


def nav_currency(fund_header_rows: list[list[str]]) -> str:
    """'USD 146.38' on the row after 'NAV as of ...' -> 'USD'."""
    cells = [row[0].strip() for row in fund_header_rows if row and row[0].strip()]
    for label, value in itertools.pairwise(cells):
        if label.startswith("NAV as of"):
            match = re.fullmatch(r"([A-Z]{3})\s+[\d,.]+", value)
            if match:
                return match.group(1)
    raise IsharesFormatError("NAV currency not found in 'Fund Header'")


def parse_historical_navs(rows: list[list[str]]) -> pd.Series:
    """'Historical NAVs' rows [date, nav] -> Series indexed by date, oldest first."""
    values = {}
    for row in rows:
        if len(row) != 2 or not row[1]:
            continue
        try:
            day = parse_issuer_date(row[0])
        except IsharesFormatError:
            continue
        values[day] = float(row[1].replace(",", ""))
    if not values:
        raise IsharesFormatError("no NAVs found in 'Historical NAVs'")
    series = pd.Series(values, name="nav").sort_index()
    series.index = pd.to_datetime(series.index)
    return series


def _dash_date(text: str) -> date:
    return parse_issuer_date(text.replace("-", "/"))


def _percent(text: str) -> float | None:
    """'15.25' -> 0.1525; '1,616.72' (cumulative since launch) -> 16.1672."""
    text = text.strip()
    return None if text in ("", "-") else float(text.replace(",", "")) / 100


def parse_performance_returns(rows: list[list[str]]) -> pd.DataFrame:
    """'Performance Returns' -> long table (fractions, not percent).

    Tables: 'Discrete' (yearly windows with explicit start/end dates), 'Annualised' and
    'Cumulative' (periods such as '1y', '5y', 'Incept.'), each possibly at several as-of dates.
    """
    records = []
    table: str | None = None
    as_of: date | None = None
    headers: list[str] = []
    fund_row: list[str] | None = None
    for row in rows:
        if not row:
            continue
        first = row[0]
        if first in ("Discrete", "Annualised", "Cumulative"):
            table = first
            if len(row) >= 3 and row[1] == "as of":
                as_of = parse_issuer_date(row[2])
            continue
        if first == "as of" and len(row) > 1:
            as_of = parse_issuer_date(row[1])
            continue
        if first == "Total Return (%)":
            fund_row = row
            continue
        if first == "Benchmark (%)" and fund_row is not None and table and as_of:
            for period, fund, bench in zip(headers, fund_row[1:], row[1:], strict=False):
                start = end = None
                match = _DISCRETE_PERIOD.search(period.replace("\n", " "))
                if match:
                    start, end = _dash_date(match.group(1)), _dash_date(match.group(2))
                records.append(
                    {
                        "table": table,
                        "as_of": as_of,
                        "period": " ".join(period.split()),
                        "start": start,
                        "end": end,
                        "fund": _percent(fund),
                        "benchmark": _percent(bench),
                    }
                )
            fund_row = None
            continue
        if table is not None and fund_row is None:
            headers = row  # period labels of the next 'Total Return' / 'Benchmark' rows
    if not records:
        raise IsharesFormatError("no returns found in 'Performance Returns'")
    return pd.DataFrame.from_records(records, columns=PERFORMANCE_COLUMNS)


def _enclosing_json_object(text: str, index: int) -> dict:
    depth, start = 0, index
    while start > 0:
        char = text[start]
        if char == "}":
            depth += 1
        elif char == "{":
            if depth == 0:
                break
            depth -= 1
        start -= 1
    depth = 0
    for end in range(start, len(text)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : end + 1])
    raise IsharesFormatError("unbalanced JSON on the product page")


def _field(text: str, label: str) -> dict | None:
    index = text.find(f'"label":"{label}"')
    return _enclosing_json_object(text, index) if index >= 0 else None


def parse_distributions(page_html: str) -> pd.DataFrame:
    """Distributions (ex_date, amount, currency) from the product page. Empty if none."""
    text = unescape(page_html)
    ex_dates = _field(text, "Ex-Date")
    amounts = _field(text, "Total Distribution")
    columns = ["ex_date", "amount", "currency"]
    if ex_dates is None or amounts is None or not ex_dates.get("value"):
        return pd.DataFrame(columns=columns)
    dates = [pd.Timestamp(str(value)) for value in ex_dates["value"]]
    values = [float(value) for value in amounts["value"]]
    prefixes = amounts.get("prefix") or [None] * len(values)
    if not len(dates) == len(values) == len(prefixes):
        raise IsharesFormatError("distribution dates and amounts have different lengths")
    currencies = [(p or "").strip() or None for p in prefixes]
    return (
        pd.DataFrame({"ex_date": dates, "amount": values, "currency": currencies})
        .sort_values("ex_date")
        .reset_index(drop=True)
    )


CHARACTERISTICS_COLUMNS = ["label", "value", "as_of"]


def parse_characteristics(rows: list[list[str]]) -> pd.DataFrame:
    """'Portfolio Characteristics' rows [label, value, 'as of dd/Mon/yyyy'?] -> table.

    Values are kept as published text ('11.62%', 'EUR 243.63', '1.001'); callers parse what
    they need.
    """
    records = []
    for row in rows:
        if len(row) < 2 or not row[0]:
            continue
        as_of = None
        if len(row) > 2 and row[2].startswith("as of "):
            as_of = parse_issuer_date(row[2].removeprefix("as of "))
        records.append({"label": row[0], "value": row[1], "as_of": as_of})
    return pd.DataFrame.from_records(records, columns=CHARACTERISTICS_COLUMNS)
