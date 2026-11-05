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
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from radiografia.domain.fund import Fund
from radiografia.domain.metrics import Coverage, MetricResult, MetricStatus, Unit
from radiografia.domain.portfolio import CoverageStatus, Portfolio, Position

WEIGHTED_TER = "weighted_ter"
ANNUAL_COST = "annual_cost"

WARNING_TER_IS_NOT_TOTAL_COST = "ter_is_not_total_cost"
WARNING_HEDGING_COST_NOT_IN_TER = "hedging_cost_not_in_ter"
WARNING_PARTIAL_COVERAGE = "partial_coverage"


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


class CostsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    weighted_ter: MetricResult
    annual_cost: MetricResult
    lines: tuple[CostLine, ...]
    """Covered positions by annual cost (highest first), then positions without TER."""


def compute_costs(portfolio: Portfolio, funds: Mapping[str, Fund]) -> CostsResult:
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
        lines=tuple(lines),
    )
