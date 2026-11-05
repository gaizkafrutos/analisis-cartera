"""The fund universe: reading and writing `data/reference/universe.csv` and `listings.csv`.

Both files are committed: they hold reference metadata transcribed from official issuer
documents (ISIN, TER, currencies, listings...), each fund row with its source URL and date.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from radiografia.domain.fund import Fund, Listing
from radiografia.domain.universe import UniverseIndex

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"
FUNDS_FILE = "universe.csv"
LISTINGS_FILE = "listings.csv"

FUND_COLUMNS = list(Fund.model_fields)
LISTING_COLUMNS = list(Listing.model_fields)


@dataclass(frozen=True)
class Universe:
    funds: Mapping[str, Fund]
    listings: tuple[Listing, ...]

    def index(self) -> UniverseIndex:
        """Lookup used to resolve user input: ISINs plus every exchange ticker of each fund."""
        tickers: dict[str, set[str]] = defaultdict(set)
        for listing in self.listings:
            tickers[listing.ticker.upper()].add(listing.isin)
        return UniverseIndex(
            isins=frozenset(self.funds),
            tickers={ticker: frozenset(isins) for ticker, isins in tickers.items()},
        )


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _write(path: Path, columns: list[str], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _cell(row[column]) for column in columns})


def write_universe(funds: Iterable[Fund], listings: Iterable[Listing], directory: Path) -> None:
    funds = sorted(funds, key=lambda f: f.isin)
    listings = sorted(listings, key=lambda li: (li.isin, li.exchange, li.ticker, li.currency))
    _write(directory / FUNDS_FILE, FUND_COLUMNS, (f.model_dump() for f in funds))
    _write(directory / LISTINGS_FILE, LISTING_COLUMNS, (li.model_dump() for li in listings))


def _read_rows(path: Path) -> list[dict[str, str | None]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {k: (v if v != "" else None) for k, v in row.items()} for row in csv.DictReader(handle)
        ]


def load_universe(directory: Path = REFERENCE_DIR) -> Universe:
    """Load and validate the universe (pydantic validates ISINs, TER range and enums)."""
    funds = [Fund.model_validate(row) for row in _read_rows(directory / FUNDS_FILE)]
    by_isin = {fund.isin: fund for fund in funds}
    if len(by_isin) != len(funds):
        raise ValueError("duplicate ISIN in universe.csv")
    listings = tuple(Listing.model_validate(row) for row in _read_rows(directory / LISTINGS_FILE))
    orphan = {li.isin for li in listings} - set(by_isin)
    if orphan:
        raise ValueError(f"listings for ISINs not in universe.csv: {sorted(orphan)}")
    return Universe(funds=by_isin, listings=listings)
