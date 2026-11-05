"""Historical returns in EUR from the issuer's NAV and ECB reference rates.

Per ETF (in its NAV currency):
    total-return factor_t = (NAV_t + distribution with ex-date t) / NAV_(t-1)
    For accumulating classes there are no distributions and the NAV already is total return.
To EUR:
    NAV_EUR_t = NAV_t / rate_t   (rate = units of NAV currency per EUR, ECB)
    rate_t is the last ECB rate published on or before t (ECB and fund calendars differ).
Portfolio (current weights held constant, i.e. rebalanced every day):
    r_portfolio_t = sum(w_i x r_i,t), weights re-scaled to the covered part.
    Common window: from the launch of the youngest ETF; on a day an ETF has no NAV (holiday)
    its value is carried forward (0 % return that day).
Annualised return over the window:
    (final value / initial value) ^ (365.25 / calendar days) - 1

Assumptions and limitations (also in docs/METODOLOGIA.md):
    - It is a simulation of today's weights in the past, not the user's actual return.
    - NAV is not the exchange price (premium/discount); NAVs are struck after market close while
      the ECB fixes its rates at 14:15 CET, which adds day-to-day noise in EUR.
    - Distributions are assumed reinvested at the ex-date NAV (as the issuer does).
    - Past performance does not predict future returns.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from radiografia.domain.fund import Fund, IncomeTreatment
from radiografia.domain.metrics import Coverage, MetricResult, MetricStatus, Unit
from radiografia.domain.portfolio import CoverageStatus, Portfolio

ANNUALISED_RETURN = "annualised_return"

MIN_YEARS_FOR_ANNUALISED = 1.0
SHORT_HISTORY_YEARS = 3.0
DAYS_PER_YEAR = 365.25

WARNING_PAST_PERFORMANCE = "past_performance"
WARNING_CONSTANT_WEIGHTS = "constant_weights_simulation"
WARNING_FX_TIMING = "fx_reference_rate_timing"
WARNING_SHORT_HISTORY = "short_history"
WARNING_TOO_SHORT_TO_ANNUALISE = "too_short_to_annualise"


class ReturnsUncoveredReason(StrEnum):
    OUTSIDE_UNIVERSE = "outside_universe"
    NAV_NOT_AVAILABLE = "nav_not_available"
    DISTRIBUTIONS_NOT_AVAILABLE = "distributions_not_available"


class ReturnsUncovered(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    weight: float
    reason: ReturnsUncoveredReason


class ReturnsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    annualised_return: MetricResult
    limited_by: str | None
    """Name of the ETF with the shortest history, which sets the start of the window."""
    uncovered: tuple[ReturnsUncovered, ...]


@dataclass(frozen=True)
class PortfolioSeries:
    """Daily EUR returns of the covered part of the portfolio (input for the risk metrics)."""

    returns: pd.Series
    fund_returns: pd.DataFrame
    weights: Mapping[str, float]
    covered_weight: float
    window_start: date
    window_end: date
    limited_by: str | None
    nav_currencies: frozenset[str]


def total_return_index(nav: pd.Series, distributions: pd.Series | None = None) -> pd.Series:
    """Total-return index (first value 1) from NAVs and distributions by ex-date.

    A distribution whose ex-date is not a NAV date is added on the next NAV date.
    """
    nav = nav.sort_index()
    added = pd.Series(0.0, index=nav.index)
    if distributions is not None and not distributions.empty:
        positions = nav.index.searchsorted(distributions.index)
        for position, amount in zip(positions, distributions.to_numpy(), strict=True):
            if position < len(nav):
                added.iloc[position] += amount
    factors = (nav + added) / nav.shift(1)
    factors.iloc[0] = 1.0
    return factors.cumprod()


def to_eur(index: pd.Series, currency: str, rates: pd.Series | None) -> pd.Series:
    """Convert a series in `currency` to EUR with the last ECB rate on or before each date."""
    if currency == "EUR":
        return index
    if rates is None or rates.empty:
        raise ValueError(f"no ECB rates for {currency}")
    aligned = rates.sort_index().reindex(index.index, method="ffill")
    return (index / aligned).dropna()


def common_window_returns(indices: Mapping[str, pd.Series]) -> pd.DataFrame:
    """Daily simple returns of every series on a common calendar, from the latest start."""
    start = max(series.index.min() for series in indices.values())
    frame = pd.DataFrame(indices).sort_index().ffill()
    frame = frame.loc[frame.index >= start]
    return frame.pct_change().iloc[1:]


def annualised_return(returns: pd.Series, window_start: pd.Timestamp) -> float:
    growth = float((1 + returns).prod())
    years = (returns.index[-1] - window_start).days / DAYS_PER_YEAR
    return growth ** (1 / years) - 1


def build_portfolio_series(
    portfolio: Portfolio,
    funds: Mapping[str, Fund],
    navs: pd.DataFrame | None,
    distributions: pd.DataFrame | None,
    fx: pd.DataFrame | None,
) -> tuple[PortfolioSeries | None, list[ReturnsUncovered]]:
    """EUR total-return series of each covered ETF and of the portfolio."""
    uncovered: list[ReturnsUncovered] = []
    indices: dict[str, pd.Series] = {}
    weights: dict[str, float] = {}
    currencies: set[str] = set()
    navs_by_isin = dict(tuple(navs.groupby("isin"))) if navs is not None else {}
    dist_by_isin = dict(tuple(distributions.groupby("isin"))) if distributions is not None else {}
    rates_by_ccy = (
        {ccy: g.set_index("date")["rate"] for ccy, g in fx.groupby("currency")}
        if fx is not None
        else {}
    )

    for position in portfolio.positions:
        fund = funds.get(position.isin) if position.isin else None
        label = fund.name if fund else " / ".join(position.identifiers)
        if position.coverage is not CoverageStatus.COVERED or fund is None:
            reason = ReturnsUncoveredReason.OUTSIDE_UNIVERSE
        elif position.isin not in navs_by_isin:
            reason = ReturnsUncoveredReason.NAV_NOT_AVAILABLE
        elif (
            fund.income_treatment is IncomeTreatment.DISTRIBUTING
            and position.isin not in dist_by_isin
        ):
            reason = ReturnsUncoveredReason.DISTRIBUTIONS_NOT_AVAILABLE
        else:
            reason = None
        if reason is not None:
            uncovered.append(ReturnsUncovered(label=label, weight=position.weight, reason=reason))
            continue

        lines = navs_by_isin[position.isin]
        nav = lines.set_index("date")["nav"]
        currency = lines["currency"].iloc[0]
        dist = dist_by_isin.get(position.isin)
        dist_series = dist.set_index("ex_date")["amount"] if dist is not None else None
        try:
            index = to_eur(
                total_return_index(nav, dist_series), currency, rates_by_ccy.get(currency)
            )
        except ValueError:
            uncovered.append(
                ReturnsUncovered(
                    label=label,
                    weight=position.weight,
                    reason=ReturnsUncoveredReason.NAV_NOT_AVAILABLE,
                )
            )
            continue
        indices[position.isin] = index
        weights[position.isin] = position.weight
        currencies.add(currency)

    if not indices:
        return None, uncovered
    covered = sum(weights.values())
    fund_returns = common_window_returns(indices)
    scaled = {isin: w / covered for isin, w in weights.items()}
    portfolio_returns = (fund_returns * pd.Series(scaled)).sum(axis=1)
    first_dates = {isin: series.index.min() for isin, series in indices.items()}
    youngest = max(first_dates, key=first_dates.get)
    window_start = max(first_dates.values())
    return (
        PortfolioSeries(
            returns=portfolio_returns,
            fund_returns=fund_returns,
            weights=scaled,
            covered_weight=covered,
            window_start=window_start.date(),
            window_end=portfolio_returns.index[-1].date(),
            limited_by=funds[youngest].name if len(indices) > 1 else None,
            nav_currencies=frozenset(currencies),
        ),
        uncovered,
    )


def compute_returns(
    portfolio: Portfolio,
    funds: Mapping[str, Fund],
    navs: pd.DataFrame | None,
    distributions: pd.DataFrame | None,
    fx: pd.DataFrame | None,
) -> tuple[ReturnsResult, PortfolioSeries | None]:
    series, uncovered = build_portfolio_series(portfolio, funds, navs, distributions, fx)
    covered = series.covered_weight if series else 0.0
    coverage = Coverage(
        covered_weight=covered,
        covered_amount_eur=covered * portfolio.total_eur,
        not_covered_amount_eur=(1 - covered) * portfolio.total_eur,
    )
    if series is None or series.returns.empty:
        metric = MetricResult(
            key=ANNUALISED_RETURN,
            value=None,
            unit=Unit.FRACTION,
            status=MetricStatus.NOT_AVAILABLE,
            coverage=coverage,
        )
        return ReturnsResult(
            annualised_return=metric, limited_by=None, uncovered=tuple(uncovered)
        ), series

    start = pd.Timestamp(series.window_start)
    years = (series.returns.index[-1] - start).days / DAYS_PER_YEAR
    warnings = [WARNING_PAST_PERFORMANCE, WARNING_CONSTANT_WEIGHTS]
    if series.nav_currencies - {"EUR"}:
        warnings.append(WARNING_FX_TIMING)
    if years < SHORT_HISTORY_YEARS:
        warnings.append(WARNING_SHORT_HISTORY)
    value: float | None = annualised_return(series.returns, start)
    status = MetricStatus.AVAILABLE if covered >= 1 - 1e-12 else MetricStatus.PARTIAL
    if years < MIN_YEARS_FOR_ANNUALISED:
        value, status = None, MetricStatus.NOT_AVAILABLE
        warnings.append(WARNING_TOO_SHORT_TO_ANNUALISE)
    metric = MetricResult(
        key=ANNUALISED_RETURN,
        value=value,
        unit=Unit.FRACTION,
        status=status,
        coverage=coverage,
        window_start=series.window_start,
        window_end=series.window_end,
        observations=len(series.returns),
        warnings=tuple(warnings),
    )
    return (
        ReturnsResult(
            annualised_return=metric, limited_by=series.limited_by, uncovered=tuple(uncovered)
        ),
        series,
    )


def fund_index_eur(
    isin: str,
    navs: pd.DataFrame | None,
    distributions: pd.DataFrame | None,
    fx: pd.DataFrame | None,
) -> pd.Series | None:
    """EUR total-return index of one ETF (e.g. the benchmark ETF), or None without data."""
    if navs is None:
        return None
    lines = navs[navs["isin"] == isin]
    if lines.empty:
        return None
    currency = lines["currency"].iloc[0]
    dist = distributions[distributions["isin"] == isin] if distributions is not None else None
    dist_series = dist.set_index("ex_date")["amount"] if dist is not None and len(dist) else None
    rates = fx[fx["currency"] == currency].set_index("date")["rate"] if fx is not None else None
    try:
        return to_eur(
            total_return_index(lines.set_index("date")["nav"], dist_series), currency, rates
        )
    except ValueError:
        return None
