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

from radiografia.analytics.costs import CostsResult, compute_costs, tracking_differences
from radiografia.analytics.lookthrough import LookThroughResult, ProxyNote, compute_lookthrough
from radiografia.analytics.returns import ReturnsResult, compute_returns, fund_index_eur
from radiografia.analytics.risk import RiskResult, compute_risk
from radiografia.data.datasets import DATASETS, Dataset, DatasetKey, current_dataset
from radiografia.data.snapshots import Snapshot, latest_snapshot_dir, read_snapshot
from radiografia.data.universe import Universe, load_universe
from radiografia.domain.fund import AssetClass
from radiografia.domain.portfolio import Portfolio, PortfolioInputResult, RawPosition
from radiografia.input import build_portfolio, portfolio_from_csv
from radiografia.reporting.summary import Summary, build_summary
from radiografia.reporting.texts import DATASET_TEXTS


class AnalysisReport(BaseModel):
    """Everything the UI shows. JSON-serialisable (FastAPI, PDF in phase 4)."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    costs: CostsResult
    lookthrough: LookThroughResult
    returns: ReturnsResult
    risk: RiskResult
    summary: Summary
    reference: LookThroughResult | None = None
    """Look-through of the reference index (world equity market), to compare exposures with."""
    dataset: DatasetKey = DatasetKey.REAL
    """Which data produced it: real (iShares + ECB) or the synthetic demo."""


class ExamplePortfolio(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    title: str
    description: str
    filename: str


EXAMPLES = (
    ExamplePortfolio(
        key="global",
        title="Global diversificada",
        description="MSCI World, emergentes y dos fondos de bonos (70 % acciones, 30 % bonos).",
        filename="cartera_global.csv",
    ),
    ExamplePortfolio(
        key="concentrada",
        title="Muy concentrada",
        description="Nasdaq 100 y S&P 500 Tecnología: un país y casi un solo sector.",
        filename="cartera_concentrada.csv",
    ),
    ExamplePortfolio(
        key="solapada",
        title="Con fondos solapados",
        description="MSCI World, S&P 500 y Nasdaq 100: las mismas empresas varias veces.",
        filename="cartera_solapada.csv",
    ),
)


DEMO_EXAMPLES = (
    ExamplePortfolio(
        key="global",
        title="Global diversificada",
        description="Fondos ficticios: acciones de países desarrollados y emergentes y dos de "
        "bonos (70 % acciones, 30 % bonos).",
        filename="cartera_global.csv",
    ),
    ExamplePortfolio(
        key="concentrada",
        title="Muy concentrada",
        description="Fondos ficticios: 100 grandes empresas de EE. UU. y tecnología de EE. UU.",
        filename="cartera_concentrada.csv",
    ),
    ExamplePortfolio(
        key="solapada",
        title="Con fondos solapados",
        description="Fondos ficticios: mundo desarrollado, 500 de EE. UU. y 100 grandes de "
        "EE. UU.: las mismas empresas varias veces.",
        filename="cartera_solapada.csv",
    ),
)


def dataset() -> Dataset:
    """Data the app runs on (real or demo), chosen with RADIOGRAFIA_DATA."""
    return current_dataset()


def examples() -> tuple[ExamplePortfolio, ...]:
    return DEMO_EXAMPLES if dataset().is_demo else EXAMPLES


def example_portfolio_csv(key: str = "global") -> bytes:
    """Example portfolio loadable with one click (Spanish Excel CSV format)."""
    example = next(e for e in examples() if e.key == key)
    return (dataset().examples_dir / example.filename).read_bytes()


def get_universe() -> Universe:
    """Reference universe of the current dataset (the same for every user)."""
    return _universe(dataset().key)


def get_snapshot() -> Snapshot | None:
    """Latest snapshot of the current dataset, or None (sections then show as not available)."""
    return _snapshot(dataset().key)


@lru_cache(maxsize=len(DATASETS))
def _universe(key: DatasetKey) -> Universe:
    return load_universe(DATASETS[key].reference_dir)


@lru_cache(maxsize=len(DATASETS))
def _snapshot(key: DatasetKey) -> Snapshot | None:
    directory = latest_snapshot_dir(DATASETS[key].snapshots_dir)
    return read_snapshot(directory) if directory is not None else None


def read_portfolio_csv(data: bytes | str, universe: Universe | None = None) -> PortfolioInputResult:
    return portfolio_from_csv(data, (universe or get_universe()).index())


def read_portfolio_rows(
    rows: Sequence[RawPosition], universe: Universe | None = None
) -> PortfolioInputResult:
    return build_portfolio(rows, (universe or get_universe()).index())


def proxy_notes(snapshot: Snapshot, universe: Universe) -> dict[str, ProxyNote]:
    """Public dataset: which US twin ETF stands in for each UCITS ETF (empty otherwise)."""
    if snapshot.proxies is None:
        return {}
    notes = {}
    for row in snapshot.proxies.itertuples():
        fund = universe.funds.get(row.isin)
        notes[row.isin] = ProxyNote(
            isin=row.isin,
            fund_name=fund.name if fund else row.isin,
            ucits_index=row.ucits_index,
            us_ticker=row.us_ticker,
            us_name=row.us_name,
            us_index=row.us_index,
            exact_index=row.match == "exact",
            note=row.note if isinstance(row.note, str) and row.note else None,
            holdings_as_of=row.report_date.date(),
        )
    return notes


_LATEST = object()


def analyze(
    portfolio: Portfolio,
    universe: Universe | None = None,
    snapshot: Snapshot | object | None = _LATEST,
) -> AnalysisReport:
    """Run every metric. `snapshot` defaults to the latest local one; pass None to analyse
    without holdings (look-through then reports not available)."""
    data = dataset()
    benchmark_isin = data.benchmark_isin
    universe = universe or get_universe()
    snapshot = get_snapshot() if snapshot is _LATEST else snapshot
    holdings, as_of, proxies = None, {}, {}
    navs = performance = distributions = fx = estr = None
    if snapshot is not None:
        holdings = snapshot.holdings
        as_of = {row.isin: row.holdings_as_of.date() for row in snapshot.manifest.itertuples()}
        proxies = proxy_notes(snapshot, universe)
        navs, performance = snapshot.navs, snapshot.performance
        distributions, fx = snapshot.distributions, snapshot.fx
        if snapshot.estr is not None:
            estr = snapshot.estr.set_index("date")["rate"]
    returns, series = compute_returns(portfolio, universe.funds, navs, distributions, fx)
    equity_share = (
        sum(
            w
            for isin, w in series.weights.items()
            if universe.funds[isin].asset_class is AssetClass.EQUITY
        )
        if series
        else 0.0
    )
    benchmark = universe.funds.get(benchmark_isin)
    risk = compute_risk(
        series,
        portfolio.total_eur,
        fund_index_eur(benchmark_isin, navs, distributions, fx),
        benchmark.name if benchmark else None,
        estr,
        equity_share,
    )
    costs = compute_costs(
        portfolio, universe.funds, tracking_differences(performance, universe.funds)
    )
    lookthrough = compute_lookthrough(portfolio, universe.funds, holdings, as_of, proxies)
    reference = None
    if holdings is not None and benchmark is not None:
        benchmark_portfolio = build_portfolio(
            [RawPosition(identifier=benchmark_isin, amount_eur=1.0)], universe.index()
        ).portfolio
        reference = compute_lookthrough(
            benchmark_portfolio, universe.funds, holdings, as_of, proxies
        )
    names = {isin: fund.name for isin, fund in universe.funds.items()}
    labels = DATASET_TEXTS[data.key]
    return AnalysisReport(
        portfolio=portfolio,
        costs=costs,
        lookthrough=lookthrough,
        returns=returns,
        risk=risk,
        summary=build_summary(
            portfolio,
            costs,
            lookthrough,
            returns,
            risk,
            names,
            reference,
            reference_name=labels.reference_in_summary,
            disclaimer=labels.disclaimer,
        ),
        reference=reference,
        dataset=data.key,
    )
