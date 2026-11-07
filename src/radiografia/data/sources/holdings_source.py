"""One interface for every issuer's holdings file (CLAUDE.md: created with the second real source).

Each issuer publishes its holdings in its own format. A `HoldingsSource` recognises its issuer's
file and turns it into the common columns the engine reads (`HOLDINGS_COLUMNS`), the same ones
the stored snapshots use. Pure: bytes in, table out; downloading is not part of it, because
most issuers only allow a person to download their files for personal use (see
docs/FUENTES_Y_LICENCIAS.md): the user uploads them.

Common columns, one row per line of the issuer's file:
    ticker, name, sector, asset_class, location, exchange, market_currency,
    market_value, notional_value, weight_published, security_isin

- `asset_class` uses the iShares labels ("Equity", "Fixed Income", "Cash", "Futures"...), the
  ones fund_breakdown.is_cash_like knows; `location` is the country name in English as iShares
  writes it ("United States"), so the same company is grouped across issuers.
- `market_value` drives the weights; when a file only has weights, the weight (as a fraction)
  is the market value: the engine only uses its proportions.
- A column the issuer does not publish is missing (NaN), never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

HOLDINGS_COLUMNS = [
    "ticker",
    "name",
    "sector",
    "asset_class",
    "location",
    "exchange",
    "market_currency",
    "market_value",
    "notional_value",
    "weight_published",
    "security_isin",
]
TEXT_COLUMNS = ("ticker", "name", "sector", "asset_class", "location", "exchange", "security_isin")


class HoldingsFormatError(ValueError):
    """The file looks like this issuer's holdings file but cannot be read."""


class UnusableHoldingsFile(ValueError):
    """The issuer's file is recognised but lacks what the analysis needs (e.g. countries)."""


@dataclass(frozen=True)
class ParsedHoldings:
    issuer: str
    as_of: date
    holdings: pd.DataFrame
    """HOLDINGS_COLUMNS, weights as fractions."""
    fund_isin: str | None = None
    """When the file itself says which fund it is."""


class HoldingsSource(Protocol):
    issuer: str
    """Display name, e.g. "iShares"."""

    def recognises(self, filename: str, content: bytes) -> bool:
        """Cheap check on the name and the first bytes: is this the issuer's holdings file?"""
        ...

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        """Read the whole file. Raises HoldingsFormatError or UnusableHoldingsFile."""
        ...


def normalise(holdings: pd.DataFrame) -> pd.DataFrame:
    """All common columns present, empty text as missing, numbers as floats."""
    holdings = holdings.reindex(columns=HOLDINGS_COLUMNS).copy()
    for column in TEXT_COLUMNS:
        values = holdings[column].astype("object")
        holdings[column] = values.mask(values.isna() | (values == ""))
    for column in ("market_value", "notional_value", "weight_published"):
        holdings[column] = pd.to_numeric(holdings[column], errors="coerce").astype(float)
    return holdings
