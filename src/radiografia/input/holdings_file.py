"""Holdings files the user uploads ("sube tu fichero"): recognise, read and check them.

Pure: bytes in, result out. Nothing is written to disk or logged (CLAUDE.md, "Privacidad"); the
app keeps the bytes in the session's memory only.

Supported today: the iShares holdings CSV (`<TICKER>_holdings.csv`, "Detailed holdings and
analytics" on the UK site in English). It has one row per position with country, exchange and
market currency, the same file the local snapshots use, so the analysis is identical.

Recognised but not usable: the iShares product workbook (Excel). Its "Holdings" sheet has no
country or exchange per position, so the look-through could not tell where each company is or
match the same company across funds; the user is told to download the CSV instead.

Other issuers' files are reported as not recognised (more readers in later phases).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import pandas as pd

from radiografia.data.sources.ishares import IsharesFormatError
from radiografia.data.sources.ishares_holdings import parse_holdings_csv
from radiografia.domain.universe import UniverseIndex

MAX_FILE_BYTES = 10 * 1024 * 1024  # largest iShares CSV ~4 MB; = maxUploadSize in .streamlit
ISHARES = "iShares"
_TEXT_COLUMNS = ("ticker", "name", "sector", "asset_class", "location", "exchange")
_FILENAME_TICKER = re.compile(r"^([A-Za-z0-9]{2,8})_holdings", re.IGNORECASE)
_WORKBOOK_MARKERS = (b"urn:schemas-microsoft-com:office:spreadsheet", b"<Workbook")


class HoldingsFileError(StrEnum):
    EMPTY = "empty"
    TOO_LARGE = "too_large"
    ISHARES_WORKBOOK = "ishares_workbook"
    """The iShares Excel: recognised, but it lacks the country of each position."""
    SPREADSHEET = "spreadsheet"
    """Another Excel file: only the issuer's own CSV is read."""
    NOT_RECOGNISED = "not_recognised"
    BROKEN = "broken"
    """Looks like an iShares holdings CSV but cannot be read (detail in `detail`)."""
    NO_POSITIONS = "no_positions"


@dataclass(frozen=True)
class HoldingsUpload:
    """One uploaded file, read. `holdings` has the snapshot columns (without `isin`)."""

    filename: str
    error: HoldingsFileError | None = None
    detail: str | None = None
    issuer: str | None = None
    as_of: date | None = None
    holdings: pd.DataFrame | None = None
    suggested_isin: str | None = None
    """Fund guessed from the file name's ticker (e.g. SWDA_holdings.csv); the user confirms."""
    equity_share: float | None = None
    """Share of the market value in equity lines: checks the file against the chosen fund."""

    @property
    def ok(self) -> bool:
        return self.error is None


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def _suggested_isin(filename: str, index: UniverseIndex | None) -> str | None:
    match = _FILENAME_TICKER.match(filename.rsplit("/", 1)[-1])
    if not match or index is None:
        return None
    isins = index.tickers.get(match.group(1).upper(), frozenset())
    return next(iter(isins)) if len(isins) == 1 else None


def _normalise(holdings: pd.DataFrame) -> pd.DataFrame:
    """Same values as a stored snapshot read back (read_snapshot): empty text is missing."""
    holdings = holdings.copy()
    for column in _TEXT_COLUMNS:
        holdings[column] = holdings[column].mask(holdings[column] == "")
    return holdings


def read_holdings_file(
    filename: str, content: bytes, index: UniverseIndex | None = None
) -> HoldingsUpload:
    """Recognise and read one uploaded holdings file. Never raises for bad content."""
    if not content.strip():
        return HoldingsUpload(filename, HoldingsFileError.EMPTY)
    if len(content) > MAX_FILE_BYTES:
        return HoldingsUpload(filename, HoldingsFileError.TOO_LARGE)
    head = content[:4096]
    if any(marker in head for marker in _WORKBOOK_MARKERS):
        return HoldingsUpload(filename, HoldingsFileError.ISHARES_WORKBOOK, issuer=ISHARES)
    if head.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0")):  # .xlsx (zip) or old .xls
        return HoldingsUpload(filename, HoldingsFileError.SPREADSHEET)

    text = _decode(content)
    if not text.lstrip().startswith("Fund Holdings as of"):
        return HoldingsUpload(filename, HoldingsFileError.NOT_RECOGNISED)
    try:
        parsed = parse_holdings_csv(text.lstrip())
    except IsharesFormatError as exc:
        return HoldingsUpload(filename, HoldingsFileError.BROKEN, detail=str(exc), issuer=ISHARES)

    holdings = _normalise(parsed.holdings)
    value = holdings["market_value"].fillna(0)
    if value.sum() <= 0:
        return HoldingsUpload(filename, HoldingsFileError.NO_POSITIONS, issuer=ISHARES)
    equity = value[holdings["asset_class"] == "Equity"].sum() / value.sum()
    return HoldingsUpload(
        filename=filename,
        issuer=ISHARES,
        as_of=parsed.as_of,
        holdings=holdings,
        suggested_isin=_suggested_isin(filename, index),
        equity_share=float(equity),
    )
