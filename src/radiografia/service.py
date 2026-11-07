"""Single entry point of the engine. The UI (and a future API) only call functions in this module.

    result = read_portfolio_csv(uploaded_bytes)      # or read_portfolio_rows(form_rows)
    if result.ok:
        report = analyze(result.portfolio)

Every function takes an optional `source` (the dataset chosen in the session); without it, the
default of `datasets.current_dataset()`. With the user's own holdings files (source UPLOAD):

    upload = read_holdings_file(name, content)               # per file
    uploaded = snapshot_from_uploads({isin: upload, ...})    # the user confirms each fund
    report = analyze(portfolio, snapshot=uploaded.snapshot, source=UPLOAD)

Nothing here stores or logs the user's portfolio or files (CLAUDE.md, "Privacidad").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache

import pandas as pd
from pydantic import BaseModel, ConfigDict

from radiografia.analytics.costs import CostsResult, compute_costs, tracking_differences
from radiografia.analytics.freshness import DataFreshness, data_freshness
from radiografia.analytics.lookthrough import LookThroughResult, ProxyNote, compute_lookthrough
from radiografia.analytics.returns import ReturnsResult, compute_returns, fund_index_eur
from radiografia.analytics.risk import RiskResult, compute_risk
from radiografia.data.datasets import DATASETS, Dataset, DatasetKey, current_dataset, selectable
from radiografia.data.snapshots import Snapshot, latest_snapshot_dir, read_snapshot
from radiografia.data.sources.ishares_holdings import BREAKDOWN_COLUMNS
from radiografia.data.universe import Universe, load_universe
from radiografia.domain.fund import AssetClass
from radiografia.domain.portfolio import Portfolio, PortfolioInputResult, RawPosition
from radiografia.input import build_portfolio, portfolio_from_csv
from radiografia.input.holdings_file import HoldingsUpload
from radiografia.input.holdings_file import read_holdings_file as _read_holdings_file
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
    freshness: DataFreshness | None = None
    """Age of the holdings (None for the demo or without holdings)."""


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


def dataset(source: Dataset | None = None) -> Dataset:
    """Data the app runs on: `source` if given, else RADIOGRAFIA_DATA or the automatic default
    (real with a local snapshot, the demo without one)."""
    return source or current_dataset()


def selectable_datasets() -> tuple[Dataset, ...]:
    """Datasets a session can pick, the default first (see datasets.selectable)."""
    return selectable(current_dataset())


def examples(source: Dataset | None = None) -> tuple[ExamplePortfolio, ...]:
    return DEMO_EXAMPLES if dataset(source).is_demo else EXAMPLES


def example_portfolio_csv(key: str = "global", source: Dataset | None = None) -> bytes:
    """Example portfolio loadable with one click (Spanish Excel CSV format)."""
    example = next(e for e in examples(source) if e.key == key)
    return (dataset(source).examples_dir / example.filename).read_bytes()


def get_universe(source: Dataset | None = None) -> Universe:
    """Reference universe of the dataset (the same for every user)."""
    return _universe(dataset(source).key)


def get_snapshot(source: Dataset | None = None) -> Snapshot | None:
    """Latest stored snapshot of the dataset, or None (sections then show as not available)."""
    return _snapshot(dataset(source).key)


@lru_cache(maxsize=len(DATASETS))
def _universe(key: DatasetKey) -> Universe:
    return load_universe(DATASETS[key].reference_dir)


@lru_cache(maxsize=len(DATASETS))
def _snapshot(key: DatasetKey) -> Snapshot | None:
    root = DATASETS[key].snapshots_dir
    directory = latest_snapshot_dir(root) if root is not None else None
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


# --- the user's own holdings files ("sube tu fichero") --------------------------------------


class UploadProblem(StrEnum):
    UNKNOWN_FUND = "unknown_fund"
    """The chosen ISIN is not in the universe (its TER and asset class are unknown)."""
    ASSET_CLASS_MISMATCH = "asset_class_mismatch"
    """Mostly equity lines for a bond fund or the other way round: probably the wrong fund."""


@dataclass(frozen=True)
class UploadedData:
    """Holdings of the user's files as an in-memory snapshot (never written anywhere)."""

    snapshot: Snapshot | None
    used: tuple[str, ...]
    """ISINs whose file is used."""
    problems: tuple[tuple[str, UploadProblem], ...]
    """(ISIN, problem) for each file left out."""


def _upload_universe(universe: Universe | None) -> Universe:
    return universe or get_universe(DATASETS[DatasetKey.UPLOAD])


def read_holdings_file(
    filename: str, content: bytes, universe: Universe | None = None
) -> HoldingsUpload:
    """Read one uploaded holdings file (only iShares holdings CSVs today). Never raises."""
    return _read_holdings_file(filename, content, _upload_universe(universe).index())


def snapshot_from_uploads(
    files: Mapping[str, HoldingsUpload], universe: Universe | None = None
) -> UploadedData:
    """`files`: per fund ISIN (confirmed by the user), its uploaded file. Files that are not
    usable for that fund are left out and reported, never guessed around."""
    universe = _upload_universe(universe)
    lines, manifest, used, problems = [], [], [], []
    for isin, upload in files.items():
        if not upload.ok:
            continue
        fund = universe.funds.get(isin)
        if fund is None:
            problems.append((isin, UploadProblem.UNKNOWN_FUND))
            continue
        equity_fund = fund.asset_class is AssetClass.EQUITY
        if upload.equity_share is not None and (upload.equity_share >= 0.5) != equity_fund:
            problems.append((isin, UploadProblem.ASSET_CLASS_MISMATCH))
            continue
        lines.append(upload.holdings.assign(isin=isin))
        manifest.append(
            {
                "isin": isin,
                "holdings_as_of": pd.Timestamp(upload.as_of),
                "lines": len(upload.holdings),
            }
        )
        used.append(isin)
    snapshot = None
    if lines:
        snapshot = Snapshot(
            directory=None,
            holdings=pd.concat(lines, ignore_index=True),
            breakdowns=pd.DataFrame(columns=[*BREAKDOWN_COLUMNS, "isin"]),
            manifest=pd.DataFrame(manifest),
        )
    return UploadedData(snapshot=snapshot, used=tuple(used), problems=tuple(problems))


def missing_holdings(
    portfolio: Portfolio, uploaded: UploadedData, universe: Universe | None = None
) -> tuple[str, ...]:
    """Covered equity funds of the portfolio without a usable uploaded file (their ISINs)."""
    funds = _upload_universe(universe).funds
    return tuple(
        p.isin
        for p in portfolio.positions
        if p.isin in funds
        and funds[p.isin].asset_class is AssetClass.EQUITY
        and p.isin not in uploaded.used
    )


_LATEST = object()


def _with_episode_labels(risk: RiskResult, labels: Mapping[str, str] | None) -> RiskResult:
    """The demo's crises are scripted: name them as such instead of after the real ones."""
    if not labels:
        return risk
    episodes = tuple(
        e.model_copy(update={"label": labels.get(e.key, e.label)}) for e in risk.episodes
    )
    return risk.model_copy(update={"episodes": episodes})


def analyze(
    portfolio: Portfolio,
    universe: Universe | None = None,
    snapshot: Snapshot | object | None = _LATEST,
    source: Dataset | None = None,
    today: date | None = None,
) -> AnalysisReport:
    """Run every metric. `snapshot` defaults to the latest stored one of the dataset; pass None
    to analyse without holdings (look-through then reports not available)."""
    data = dataset(source)
    benchmark_isin = data.benchmark_isin
    universe = universe or get_universe(data)
    snapshot = get_snapshot(data) if snapshot is _LATEST else snapshot
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
    risk = _with_episode_labels(risk, DATASET_TEXTS[data.key].episode_labels)
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
        freshness=None
        if data.is_demo
        else data_freshness(lookthrough.geography.data_as_of, today or date.today()),
    )
