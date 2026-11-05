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


@dataclass(frozen=True)
class Snapshot:
    directory: Path
    holdings: pd.DataFrame
    breakdowns: pd.DataFrame
    manifest: pd.DataFrame


def write_snapshot(
    directory: Path, holdings: pd.DataFrame, breakdowns: pd.DataFrame, manifest: pd.DataFrame
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    holdings.to_csv(directory / HOLDINGS_FILE, index=False)
    breakdowns.to_csv(directory / BREAKDOWNS_FILE, index=False)
    manifest.to_csv(directory / MANIFEST_FILE, index=False)


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
    )
