"""Single entry point of the engine. The UI (and a future API) only call functions in this module.

    result = read_portfolio_csv(uploaded_bytes)      # or read_portfolio_rows(form_rows)
    if result.ok:
        report = analyze(result.portfolio)

Nothing here stores or logs the user's portfolio (CLAUDE.md, "Privacidad").
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from radiografia.analytics.costs import CostsResult, compute_costs
from radiografia.analytics.lookthrough import LookThroughResult, compute_lookthrough
from radiografia.data.snapshots import Snapshot, latest_snapshot_dir, read_snapshot
from radiografia.data.universe import Universe, load_universe
from radiografia.domain.portfolio import Portfolio, PortfolioInputResult, RawPosition
from radiografia.input import build_portfolio, portfolio_from_csv


class AnalysisReport(BaseModel):
    """Everything the UI shows. JSON-serialisable (FastAPI, PDF in phase 4)."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    costs: CostsResult
    lookthrough: LookThroughResult


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
EXAMPLE_PORTFOLIO = EXAMPLES_DIR / "cartera_ejemplo.csv"


def example_portfolio_csv() -> bytes:
    """Example portfolio loadable with one click (Spanish Excel CSV format)."""
    return EXAMPLE_PORTFOLIO.read_bytes()


@lru_cache(maxsize=1)
def get_universe() -> Universe:
    """Reference universe, loaded once per process (it is the same for every user)."""
    return load_universe()


@lru_cache(maxsize=1)
def get_snapshot() -> Snapshot | None:
    """Latest local holdings snapshot, or None (look-through then shows as not available)."""
    directory = latest_snapshot_dir()
    return read_snapshot(directory) if directory is not None else None


def read_portfolio_csv(data: bytes | str, universe: Universe | None = None) -> PortfolioInputResult:
    return portfolio_from_csv(data, (universe or get_universe()).index())


def read_portfolio_rows(
    rows: Sequence[RawPosition], universe: Universe | None = None
) -> PortfolioInputResult:
    return build_portfolio(rows, (universe or get_universe()).index())


_LATEST = object()


def analyze(
    portfolio: Portfolio,
    universe: Universe | None = None,
    snapshot: Snapshot | object | None = _LATEST,
) -> AnalysisReport:
    """Run every metric. `snapshot` defaults to the latest local one; pass None to analyse
    without holdings (look-through then reports not available)."""
    universe = universe or get_universe()
    snapshot = get_snapshot() if snapshot is _LATEST else snapshot
    holdings, as_of = None, {}
    if snapshot is not None:
        holdings = snapshot.holdings
        as_of = {row.isin: row.holdings_as_of.date() for row in snapshot.manifest.itertuples()}
    return AnalysisReport(
        portfolio=portfolio,
        costs=compute_costs(portfolio, universe.funds),
        lookthrough=compute_lookthrough(portfolio, universe.funds, holdings, as_of),
    )
