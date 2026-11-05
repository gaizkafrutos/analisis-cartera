"""Costs: weighted TER and annual cost in euros.

    annual_cost_eur = sum(amount_i * TER_i)                 over positions with a known TER
    weighted_ter    = annual_cost_eur / covered_amount_eur  (a weighted mean of the TERs)

Assumptions and limitations (also in docs/METODOLOGIA.md and docs/GLOSARIO.md):
    - Uses the TER published by the issuer on the retrieval date; TERs change over time.
    - The TER is not the total cost: trading costs inside the fund, bid-ask spreads, broker and
      currency-conversion fees and the implicit cost of currency hedging are not included.
    - Positions without a known TER are left out and reported as not covered; their cost is
      never assumed to be zero.
    - The annual cost is today's cost on today's value. No projection: projecting would require
      assuming future returns.

Tracking difference (issuer data, not computed here):
    TD = fund annualised return - benchmark annualised return, 5 years, latest month-end the
    issuer publishes. Negative = the fund lagged its index (the real cost borne). Not available
    for currency-hedged classes: the issuer compares them with the unhedged index in another
    currency, so the difference is mostly currency, not cost.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pandas as pd
from pydantic import BaseModel, ConfigDict

from radiografia.domain.fund import Fund
from radiografia.domain.metrics import Coverage, MetricResult, MetricStatus, Unit
from radiografia.domain.portfolio import CoverageStatus, Portfolio, Position

WEIGHTED_TER = "weighted_ter"
ANNUAL_COST = "annual_cost"
TRACKING_DIFFERENCE = "tracking_difference"
TRACKING_PERIOD = "5y"

WARNING_TER_IS_NOT_TOTAL_COST = "ter_is_not_total_cost"
WARNING_HEDGING_COST_NOT_IN_TER = "hedging_cost_not_in_ter"
WARNING_PARTIAL_COVERAGE = "partial_coverage"
WARNING_TD_IS_PAST_AND_ISSUER_DATA = "tracking_difference_issuer_past_data"
WARNING_TD_NOT_FOR_HEDGED = "tracking_difference_not_for_hedged"


class TrackingDifference(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float
    as_of: date


def tracking_differences(
    performance: pd.DataFrame | None, funds: Mapping[str, Fund]
) -> dict[str, TrackingDifference]:
    """5-year annualised fund - benchmark return per ISIN, from the issuer's latest month-end."""
    if performance is None or performance.empty:
        return {}
    rows = performance[
        (performance["table"] == "Annualised") & (performance["period"] == TRACKING_PERIOD)
    ].dropna(subset=["fund", "benchmark"])
    result = {}
    for isin, group in rows.groupby("isin"):
        fund = funds.get(isin)
        if fund is None or fund.currency_hedged:
            continue
        latest = group.loc[group["as_of"].idxmax()]
        result[isin] = TrackingDifference(
            value=float(latest["fund"] - latest["benchmark"]),
            as_of=pd.Timestamp(latest["as_of"]).date(),
        )
    return result


class CostLine(BaseModel):
    """One position's cost. `ter` and `annual_cost_eur` are None when the TER is unknown."""

    model_config = ConfigDict(frozen=True)

    isin: str | None
    label: str
    amount_eur: float
    weight: float
    ter: float | None
    annual_cost_eur: float | None
    share_of_cost: float | None
    """Fraction of the portfolio's known annual cost that this position generates."""
    currency_hedged: bool | None
    tracking_difference: float | None = None
    """5-year annualised fund - benchmark return (issuer data); None if not available."""


class CostsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    weighted_ter: MetricResult
    annual_cost: MetricResult
    tracking_difference: MetricResult
    """Weighted tracking difference over the funds that have it."""
    lines: tuple[CostLine, ...]
    """Covered positions by annual cost (highest first), then positions without TER."""


def compute_costs(
    portfolio: Portfolio,
    funds: Mapping[str, Fund],
    tracking: Mapping[str, TrackingDifference] | None = None,
) -> CostsResult:
    tracking = tracking or {}
    known: list[tuple[float, Fund, Position]] = []
    unknown: list[Position] = []
    for position in portfolio.positions:
        fund = funds.get(position.isin) if position.isin else None
        if position.coverage is CoverageStatus.COVERED and fund is not None:
            known.append((position.amount_eur * fund.ter, fund, position))
        else:
            unknown.append(position)

    covered_amount = sum(position.amount_eur for _, _, position in known)
    annual_cost = sum(cost for cost, _, _ in known)
    coverage = Coverage(
        covered_weight=covered_amount / portfolio.total_eur,
        covered_amount_eur=covered_amount,
        not_covered_amount_eur=portfolio.total_eur - covered_amount,
    )

    if not known:
        status = MetricStatus.NOT_AVAILABLE
    elif unknown:
        status = MetricStatus.PARTIAL
    else:
        status = MetricStatus.AVAILABLE

    warnings = [WARNING_TER_IS_NOT_TOTAL_COST]
    if any(fund.currency_hedged for _, fund, _ in known):
        warnings.append(WARNING_HEDGING_COST_NOT_IN_TER)
    if status is MetricStatus.PARTIAL:
        warnings.append(WARNING_PARTIAL_COVERAGE)

    data_as_of = min((fund.retrieved_on for _, fund, _ in known), default=None)
    common = {
        "status": status,
        "coverage": coverage,
        "data_as_of": data_as_of,
        "warnings": tuple(warnings),
    }
    available = status is not MetricStatus.NOT_AVAILABLE

    lines = [
        CostLine(
            isin=fund.isin,
            label=fund.name,
            amount_eur=position.amount_eur,
            weight=position.weight,
            ter=fund.ter,
            annual_cost_eur=cost,
            share_of_cost=cost / annual_cost if annual_cost > 0 else None,
            currency_hedged=fund.currency_hedged,
            tracking_difference=tracking[fund.isin].value if fund.isin in tracking else None,
        )
        for cost, fund, position in sorted(known, key=lambda item: -item[0])
    ]
    lines += [
        CostLine(
            isin=position.isin,
            label=" / ".join(position.identifiers),
            amount_eur=position.amount_eur,
            weight=position.weight,
            ter=None,
            annual_cost_eur=None,
            share_of_cost=None,
            currency_hedged=None,
        )
        for position in unknown
    ]

    return CostsResult(
        weighted_ter=MetricResult(
            key=WEIGHTED_TER,
            value=annual_cost / covered_amount if available else None,
            unit=Unit.FRACTION,
            **common,
        ),
        annual_cost=MetricResult(
            key=ANNUAL_COST,
            value=annual_cost if available else None,
            unit=Unit.EUR_PER_YEAR,
            **common,
        ),
        tracking_difference=_weighted_tracking(portfolio, known, tracking),
        lines=tuple(lines),
    )


def _weighted_tracking(
    portfolio: Portfolio,
    known: list[tuple[float, Fund, Position]],
    tracking: Mapping[str, TrackingDifference],
) -> MetricResult:
    with_td = [(fund, position) for _, fund, position in known if fund.isin in tracking]
    covered = sum(position.weight for _, position in with_td)
    coverage = Coverage(
        covered_weight=covered,
        covered_amount_eur=covered * portfolio.total_eur,
        not_covered_amount_eur=(1 - covered) * portfolio.total_eur,
    )
    if not with_td:
        return MetricResult(
            key=TRACKING_DIFFERENCE,
            value=None,
            unit=Unit.FRACTION,
            status=MetricStatus.NOT_AVAILABLE,
            coverage=coverage,
        )
    value = sum(tracking[f.isin].value * p.weight for f, p in with_td) / covered
    warnings = [WARNING_TD_IS_PAST_AND_ISSUER_DATA]
    if any(fund.currency_hedged for _, fund, _ in known):
        warnings.append(WARNING_TD_NOT_FOR_HEDGED)
    return MetricResult(
        key=TRACKING_DIFFERENCE,
        value=value,
        unit=Unit.FRACTION,
        status=MetricStatus.AVAILABLE if covered >= 1 - 1e-12 else MetricStatus.PARTIAL,
        coverage=coverage,
        data_as_of=min(tracking[f.isin].as_of for f, _ in with_td),
        warnings=tuple(warnings),
    )
