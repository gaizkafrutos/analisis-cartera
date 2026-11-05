"""Single entry point of the engine. The UI (and a future API) only call functions in this module.

    result = read_portfolio_csv(uploaded_bytes)      # or read_portfolio_rows(form_rows)
    if result.ok:
        report = analyze(result.portfolio)

Nothing here stores or logs the user's portfolio (CLAUDE.md, "Privacidad").
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from radiografia.analytics.costs import CostsResult, compute_costs
from radiografia.data.universe import Universe, load_universe
from radiografia.domain.portfolio import Portfolio, PortfolioInputResult, RawPosition
from radiografia.input import build_portfolio, portfolio_from_csv


class AnalysisReport(BaseModel):
    """Everything the UI shows. JSON-serialisable (FastAPI, PDF in phase 4)."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    costs: CostsResult


@lru_cache(maxsize=1)
def get_universe() -> Universe:
    """Reference universe, loaded once per process (it is the same for every user)."""
    return load_universe()


def read_portfolio_csv(data: bytes | str, universe: Universe | None = None) -> PortfolioInputResult:
    return portfolio_from_csv(data, (universe or get_universe()).index())


def read_portfolio_rows(
    rows: Sequence[RawPosition], universe: Universe | None = None
) -> PortfolioInputResult:
    return build_portfolio(rows, (universe or get_universe()).index())


def analyze(portfolio: Portfolio, universe: Universe | None = None) -> AnalysisReport:
    universe = universe or get_universe()
    return AnalysisReport(portfolio=portfolio, costs=compute_costs(portfolio, universe.funds))
