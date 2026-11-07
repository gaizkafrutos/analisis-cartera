"""iShares fund holdings and the issuer's own exposure breakdowns.

Two documents, both from the UK site in English (see docs/FUENTES_Y_LICENCIAS.md):
    - `latest-holdings.csv` (link on the product page): every position with sector, location
      (country), exchange and market currency. The workbook's "Holdings" sheet lacks location and
      exchange, so the CSV is the holdings source.
    - Workbook sheet "Exposure Breakdowns": the issuer's published sector and geography weights,
      used only to validate our own aggregation of the holdings.

Normalised holdings columns (HOLDINGS_COLUMNS): one row per line of the issuer file, cash and
derivatives included. Numbers are floats; '-' becomes NaN (not available), never 0.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from html import unescape

import pandas as pd

from radiografia.data.sources.holdings_source import HOLDINGS_COLUMNS as COMMON_COLUMNS
from radiografia.data.sources.holdings_source import (
    HoldingsFormatError,
    ParsedHoldings,
    UnusableHoldingsFile,
    normalise,
)
from radiografia.data.sources.ishares import SITE, IsharesFormatError, parse_issuer_date

HOLDINGS_COLUMNS = [column for column in COMMON_COLUMNS if column != "security_isin"]
_CSV_TO_COLUMN = {
    "Ticker": "ticker",
    "Name": "name",
    "Sector": "sector",
    "Asset Class": "asset_class",
    "Location": "location",
    "Exchange": "exchange",
    "Market Currency": "market_currency",
    "Market Value": "market_value",
    "Notional Value": "notional_value",
    "Weight (%)": "weight_published",
}
_NUMERIC = ("market_value", "notional_value", "weight_published")

BREAKDOWN_COLUMNS = ["section", "as_of", "label", "code", "weight"]


@dataclass(frozen=True)
class HoldingsFile:
    as_of: date
    holdings: pd.DataFrame


def holdings_csv_url(page_html: str) -> str:
    """The product page links its holdings CSV; the slug differs from the page's own slug."""
    match = re.search(r'href="([^"]*latest-holdings\.csv[^"]*)"', page_html)
    if not match:
        raise IsharesFormatError("holdings CSV link not found on the product page")
    href = unescape(match.group(1))
    return href if href.startswith("http") else SITE + href


def _number(text: str) -> float:
    text = text.strip()
    if text in ("", "-"):
        return float("nan")
    try:
        return float(text.replace(",", ""))
    except ValueError as exc:
        raise IsharesFormatError(f"unexpected number {text!r}") from exc


def parse_holdings_csv(text: str) -> HoldingsFile:
    """Parse `latest-holdings.csv`: an 'as of' line, a blank line, a header and the rows.

    Rows whose length differs from the header (trailing notes) are ignored. Weights are
    converted from percent to fraction.
    """
    rows = list(csv.reader(io.StringIO(text.removeprefix("﻿"))))
    if not rows or not rows[0] or not rows[0][0].startswith("Fund Holdings as of"):
        raise IsharesFormatError("holdings CSV does not start with 'Fund Holdings as of'")
    as_of = parse_issuer_date(rows[0][1])
    header_index = next((i for i, row in enumerate(rows) if row[:1] == ["Ticker"]), None)
    if header_index is None:
        raise IsharesFormatError("holdings CSV header not found")
    header = rows[header_index]
    missing = set(_CSV_TO_COLUMN) - set(header)
    if missing:
        raise IsharesFormatError(f"holdings CSV lacks columns {sorted(missing)}")

    records = []
    for row in rows[header_index + 1 :]:
        if len(row) != len(header):
            continue
        cells = dict(zip(header, row, strict=True))
        record = {column: cells[source].strip() for source, column in _CSV_TO_COLUMN.items()}
        for column in _NUMERIC:
            record[column] = _number(record[column])
        records.append(record)
    if not records:
        raise IsharesFormatError("holdings CSV has no rows")

    holdings = pd.DataFrame.from_records(records, columns=HOLDINGS_COLUMNS)
    holdings["weight_published"] = holdings["weight_published"] / 100
    return HoldingsFile(as_of=as_of, holdings=holdings)


def parse_exposure_breakdowns(rows: list[list[str]]) -> pd.DataFrame:
    """Parse the 'Exposure Breakdowns' sheet into long format.

    Each section is: [title], ['as of', date], ['Type', 'Fund', ...], then [label, weight, code?]
    rows until a blank row. Free-text notes after the sections are ignored.
    """
    records = []
    index = 0
    while index < len(rows):
        row = rows[index]
        is_section = (
            len(row) == 1
            and index + 2 < len(rows)
            and rows[index + 1][:1] == ["as of"]
            and rows[index + 2][:1] == ["Type"]
        )
        if not is_section:
            index += 1
            continue
        section = row[0]
        as_of = parse_issuer_date(rows[index + 1][1])
        index += 3
        while index < len(rows) and rows[index] and rows[index][0]:
            label, value, *rest = rows[index] + [""]
            records.append(
                {
                    "section": section,
                    "as_of": as_of,
                    "label": label,
                    "code": rest[0] or None,
                    "weight": _number(value) / 100,
                }
            )
            index += 1
    if not records:
        raise IsharesFormatError("no exposure breakdown sections found")
    return pd.DataFrame.from_records(records, columns=BREAKDOWN_COLUMNS)


# --- as a HoldingsSource (files the user uploads) ----------------------------------------------

_WORKBOOK_MARKERS = (b"urn:schemas-microsoft-com:office:spreadsheet", b"<Workbook")


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


class IsharesHoldingsCsv:
    """`<TICKER>_holdings.csv` ("Detailed Holdings and Analytics", UK site in English)."""

    issuer = "iShares"

    def recognises(self, filename: str, content: bytes) -> bool:
        return _decode(content[:256]).lstrip().startswith("Fund Holdings as of")

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        try:
            parsed = parse_holdings_csv(_decode(content).lstrip())
        except IsharesFormatError as exc:
            raise HoldingsFormatError(str(exc)) from exc
        return ParsedHoldings(self.issuer, parsed.as_of, normalise(parsed.holdings))


class IsharesWorkbook:
    """The product workbook (Excel 2003 XML): recognised, but its "Holdings" sheet has no country
    or exchange per position, so it cannot place companies or match them across funds."""

    issuer = "iShares"

    def recognises(self, filename: str, content: bytes) -> bool:
        return any(marker in content[:4096] for marker in _WORKBOOK_MARKERS)

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        raise UnusableHoldingsFile("ishares_workbook")
