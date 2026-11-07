"""Holdings files the user uploads ("sube tu fichero"): recognise, read and check them.

Pure: bytes in, result out. Nothing is written to disk or logged (CLAUDE.md, "Privacidad"); the
app keeps the bytes in the session's memory only.

Each issuer's reader is a HoldingsSource (radiografia.data.sources.registry); the first one that
recognises the file reads it into the common columns. Today:
    - iShares holdings CSV (`<TICKER>_holdings.csv`, "Detailed Holdings and Analytics"): the
      same file the local snapshots use, so the analysis is identical.
    - iShares product workbook (Excel): recognised but not usable (no country per position).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import pandas as pd

from radiografia.data.sources.holdings_source import HoldingsFormatError, UnusableHoldingsFile
from radiografia.data.sources.registry import HOLDINGS_SOURCES
from radiografia.domain.universe import UniverseIndex

MAX_FILE_BYTES = 10 * 1024 * 1024  # largest iShares CSV ~4 MB; = maxUploadSize in .streamlit
_FILENAME_TICKER = re.compile(r"^([A-Za-z0-9]{2,8})_holdings", re.IGNORECASE)
_SPREADSHEET_MAGIC = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")  # .xlsx (zip) or old binary .xls


class HoldingsFileError(StrEnum):
    EMPTY = "empty"
    TOO_LARGE = "too_large"
    ISHARES_WORKBOOK = "ishares_workbook"
    """The iShares Excel: recognised, but it lacks the country of each position."""
    SPREADSHEET = "spreadsheet"
    """A spreadsheet no reader recognises."""
    NOT_RECOGNISED = "not_recognised"
    BROKEN = "broken"
    """Recognised as an issuer's holdings file but cannot be read (detail in `detail`)."""
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


def _suggested_isin(filename: str, index: UniverseIndex | None) -> str | None:
    match = _FILENAME_TICKER.match(filename.rsplit("/", 1)[-1])
    if not match or index is None:
        return None
    isins = index.tickers.get(match.group(1).upper(), frozenset())
    return next(iter(isins)) if len(isins) == 1 else None


def read_holdings_file(
    filename: str, content: bytes, index: UniverseIndex | None = None
) -> HoldingsUpload:
    """Recognise and read one uploaded holdings file. Never raises for bad content."""
    if not content.strip():
        return HoldingsUpload(filename, HoldingsFileError.EMPTY)
    if len(content) > MAX_FILE_BYTES:
        return HoldingsUpload(filename, HoldingsFileError.TOO_LARGE)
    source = next((s for s in HOLDINGS_SOURCES if s.recognises(filename, content)), None)
    if source is None:
        spreadsheet = content.startswith(_SPREADSHEET_MAGIC)
        error = HoldingsFileError.SPREADSHEET if spreadsheet else HoldingsFileError.NOT_RECOGNISED
        return HoldingsUpload(filename, error)
    try:
        parsed = source.parse(filename, content)
    except UnusableHoldingsFile as exc:
        return HoldingsUpload(filename, HoldingsFileError(str(exc)), issuer=source.issuer)
    except HoldingsFormatError as exc:
        return HoldingsUpload(
            filename, HoldingsFileError.BROKEN, detail=str(exc), issuer=source.issuer
        )

    holdings = parsed.holdings
    value = holdings["market_value"].fillna(0)
    if value.sum() <= 0:
        return HoldingsUpload(filename, HoldingsFileError.NO_POSITIONS, issuer=source.issuer)
    equity = value[holdings["asset_class"] == "Equity"].sum() / value.sum()
    suggested = parsed.fund_isin
    if suggested is None or (index is not None and suggested not in index.isins):
        suggested = _suggested_isin(filename, index)
    return HoldingsUpload(
        filename=filename,
        issuer=source.issuer,
        as_of=parsed.as_of,
        holdings=holdings,
        suggested_isin=suggested,
        equity_share=float(equity),
    )
