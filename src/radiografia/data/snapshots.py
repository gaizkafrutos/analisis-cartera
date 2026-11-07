"""Local snapshots of issuer data (git-ignored, see CLAUDE.md "Qué va al repositorio").

Layout: data/snapshots/<retrieval date>/
    holdings.csv.gz    one row per holding line, all funds (column `isin` = the ETF)
    breakdowns.csv     issuer-published exposure breakdowns, all funds
    manifest.csv       per fund: holdings as-of date and number of lines

The app and the analytics read snapshots only; nothing is downloaded while a user is analysing a
portfolio. If no snapshot exists, metrics that need holdings are reported as not available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SNAPSHOTS_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"
HOLDINGS_FILE = "holdings.csv.gz"
BREAKDOWNS_FILE = "breakdowns.csv"
MANIFEST_FILE = "manifest.csv"
NAVS_FILE = "navs.csv.gz"
PERFORMANCE_FILE = "performance.csv"
DISTRIBUTIONS_FILE = "distributions.csv"
FX_FILE = "fx.csv"
CHARACTERISTICS_FILE = "characteristics.csv"
ESTR_FILE = "estr.csv"
PROXIES_FILE = "proxies.csv"


@dataclass(frozen=True)
class Snapshot:
    directory: Path
    holdings: pd.DataFrame
    breakdowns: pd.DataFrame
    manifest: pd.DataFrame
    navs: pd.DataFrame | None = None
    """isin, date, nav, currency (NAV currency of the share class)."""
    performance: pd.DataFrame | None = None
    """Issuer-published returns: isin, table, as_of, period, start, end, fund, benchmark."""
    distributions: pd.DataFrame | None = None
    """isin, ex_date, amount, currency."""
    fx: pd.DataFrame | None = None
    """ECB reference rates: date, currency, rate (units of currency per EUR)."""
    characteristics: pd.DataFrame | None = None
    """Issuer 'Portfolio Characteristics': isin, label, value (text), as_of."""
    estr: pd.DataFrame | None = None
    """ECB euro short-term rate: date, rate (% per year)."""
    proxies: pd.DataFrame | None = None
    """Public dataset only: per UCITS ISIN, the US twin ETF whose SEC holdings stand in for it."""


def write_snapshot(
    directory: Path, holdings: pd.DataFrame, breakdowns: pd.DataFrame, manifest: pd.DataFrame
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    holdings.to_csv(directory / HOLDINGS_FILE, index=False)
    breakdowns.to_csv(directory / BREAKDOWNS_FILE, index=False)
    manifest.to_csv(directory / MANIFEST_FILE, index=False)


def write_prices(
    directory: Path,
    navs: pd.DataFrame,
    performance: pd.DataFrame,
    distributions: pd.DataFrame,
    fx: pd.DataFrame,
    characteristics: pd.DataFrame,
    estr: pd.DataFrame,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    characteristics.to_csv(directory / CHARACTERISTICS_FILE, index=False)
    estr.to_csv(directory / ESTR_FILE, index=False)
    navs.to_csv(directory / NAVS_FILE, index=False)
    performance.to_csv(directory / PERFORMANCE_FILE, index=False)
    distributions.to_csv(directory / DISTRIBUTIONS_FILE, index=False)
    fx.to_csv(directory / FX_FILE, index=False)


def _optional_csv(path: Path, dates: list[str]) -> pd.DataFrame | None:
    return pd.read_csv(path, parse_dates=dates) if path.exists() else None


def latest_snapshot_dir(root: Path = SNAPSHOTS_DIR) -> Path | None:
    candidates = sorted(p for p in root.glob("*") if (p / MANIFEST_FILE).exists())
    return candidates[-1] if candidates else None


def read_snapshot(directory: Path) -> Snapshot:
    # keep_default_na=False + na_values: '-' and '' are NaN, but text like 'NA' (Namibia) is not.
    text_columns = {"ticker": str, "name": str, "location": str, "exchange": str}
    return Snapshot(
        directory=directory,
        holdings=pd.read_csv(
            directory / HOLDINGS_FILE, dtype=text_columns, keep_default_na=False, na_values=[""]
        ),
        breakdowns=pd.read_csv(
            directory / BREAKDOWNS_FILE,
            parse_dates=["as_of"],
            keep_default_na=False,
            na_values=[""],
        ),
        manifest=pd.read_csv(directory / MANIFEST_FILE, parse_dates=["holdings_as_of"]),
        navs=_optional_csv(directory / NAVS_FILE, ["date"]),
        performance=_optional_csv(directory / PERFORMANCE_FILE, ["as_of", "start", "end"]),
        distributions=_optional_csv(directory / DISTRIBUTIONS_FILE, ["ex_date"]),
        fx=_optional_csv(directory / FX_FILE, ["date"]),
        characteristics=_optional_csv(directory / CHARACTERISTICS_FILE, ["as_of"]),
        estr=_optional_csv(directory / ESTR_FILE, ["date"]),
        proxies=_optional_csv(directory / PROXIES_FILE, ["report_date"]),
    )
