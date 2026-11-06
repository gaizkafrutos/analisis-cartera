"""Plain-language summary of an analysis, built with fixed templates (no language model).

Rules (CLAUDE.md, "Regulación y lenguaje"):
    - Only facts already computed by the engine; every number comes from a MetricResult.
    - A point is left out when its metric is not available: nothing is estimated to fill a gap.
    - Describe, never recommend: no "deberías", no buy/sell/switch, no alternative products.
    - Comparisons are only with the reference index (iShares MSCI ACWI), as a neutral benchmark.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from radiografia.analytics.costs import CostsResult
from radiografia.analytics.lookthrough import LookThroughResult, UncoveredReason
from radiografia.analytics.returns import ReturnsResult
from radiografia.analytics.risk import WARNING_LOW_EQUITY_SHARE_FOR_BETA, RiskResult
from radiografia.domain.metrics import BreakdownResult, MetricResult, MetricStatus
from radiografia.domain.portfolio import CoverageStatus, Portfolio
from radiografia.reporting.formatting import (
    format_date,
    format_eur,
    format_number,
    format_percent,
    short_fund_name,
)
from radiografia.reporting.presentation import country_name, currency_name
from radiografia.reporting.texts import DISCLAIMER

SAME_INDEX_OVERLAP = 0.90
NOTABLE_OVERLAP = 0.30
NOTABLE_COST_GAP = 0.10  # share of cost minus share of money, to mention the costliest ETF
NEGLIGIBLE = 0.005  # below 0.5 % a share is described as "practically nothing"


class Topic(StrEnum):
    COVERAGE = "coverage"
    ASSET_MIX = "asset_mix"
    COSTS = "costs"
    GEOGRAPHY = "geography"
    CURRENCY = "currency"
    CONCENTRATION = "concentration"
    OVERLAP = "overlap"
    RISK = "risk"
    MARKET = "market"
    RETURNS = "returns"


class SummaryPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: Topic
    text: str


class Summary(BaseModel):
    model_config = ConfigDict(frozen=True)

    points: tuple[SummaryPoint, ...]
    disclaimer: str = DISCLAIMER


def _ok(metric: MetricResult) -> bool:
    return metric.value is not None and metric.status is not MetricStatus.NOT_AVAILABLE


def _pct(value: float, decimals: int = 0) -> str:
    return format_percent(value, decimals)


def _country(name: str) -> str:
    return country_name(name)


def _currency(code: str) -> str:
    return currency_name(code)


def _weight(breakdown: BreakdownResult, label: str) -> float | None:
    return next((item.weight for item in breakdown.items if item.label == label), None)


def _months_between(start: date, end: date) -> int:
    return max(1, round((end - start).days / 30.44))


# --- one function per topic -------------------------------------------------------------------


def coverage_point(portfolio: Portfolio) -> SummaryPoint | None:
    uncovered = [p for p in portfolio.positions if p.coverage is CoverageStatus.NOT_COVERED]
    if not uncovered:
        return None
    names = ", ".join(" / ".join(p.identifiers) for p in uncovered)
    return SummaryPoint(
        topic=Topic.COVERAGE,
        text=(
            f"Se ha analizado el {_pct(portfolio.covered_weight, 1)} de tu cartera. "
            f"{format_eur(portfolio.not_covered_weight * portfolio.total_eur)} no están en el "
            f"universo analizado ({names}) y no se incluyen en las cifras."
        ),
    )


def asset_mix_point(lookthrough: LookThroughResult) -> SummaryPoint | None:
    """Equity vs fixed income, only when there is fixed income (otherwise it is all equity)."""
    bonds = sum(
        u.weight
        for u in lookthrough.uncovered
        if u.reason is UncoveredReason.FIXED_INCOME_NOT_LOOKED_THROUGH
    )
    if bonds <= 0 or not lookthrough.geography.items:
        return None
    equity = lookthrough.geography.coverage.covered_weight
    analysed = equity + bonds
    return SummaryPoint(
        topic=Topic.ASSET_MIX,
        text=(
            f"De lo analizado, un {_pct(equity / analysed)} es renta variable (acciones) y un "
            f"{_pct(bonds / analysed)} renta fija (bonos). Las cifras de países, sectores y "
            f"empresas se refieren solo a la parte de acciones."
        ),
    )


def costs_point(costs: CostsResult) -> SummaryPoint | None:
    if not _ok(costs.annual_cost):
        return None
    text = (
        f"Tus ETFs te cuestan unos {format_eur(costs.annual_cost.value)} al año en comisiones "
        f"de gestión, un {format_percent(costs.weighted_ter.value, 2)} de media."
    )
    priced = [line for line in costs.lines if line.share_of_cost is not None]
    if len(priced) > 1:
        top = priced[0]
        if top.share_of_cost - top.weight >= NOTABLE_COST_GAP:
            text += (
                f" {short_fund_name(top.label)} genera el {_pct(top.share_of_cost)} de ese coste "
                f"con el {_pct(top.weight)} de tu dinero."
            )
    td = costs.tracking_difference
    if _ok(td):
        relation = "por encima" if td.value >= 0 else "por debajo"
        text += (
            f" En los últimos 5 años, tus ETFs rindieron de media un "
            f"{format_percent(abs(td.value), 2)} al año {relation} de los índices que copian "
            f"(dato de la gestora, ya con sus comisiones)."
        )
    return SummaryPoint(topic=Topic.COSTS, text=text)


def geography_point(
    lookthrough: LookThroughResult, reference: LookThroughResult | None
) -> SummaryPoint | None:
    geography = lookthrough.geography
    if not geography.items:
        return None
    top = geography.items[0]
    text = f"El {_pct(top.weight)} de tu renta variable está en empresas de {_country(top.label)}"
    if reference is not None and reference.geography.items:
        ref = _weight(reference.geography, top.label)
        if ref is not None:
            text += f" (en el índice mundial MSCI ACWI, el {_pct(ref)})"
    text += "."
    if len(geography.items) > 1:
        second = geography.items[1]
        text += f" Le sigue {_country(second.label)} con el {_pct(second.weight)}."
    return SummaryPoint(topic=Topic.GEOGRAPHY, text=text)


def currency_point(lookthrough: LookThroughResult) -> SummaryPoint | None:
    currency = lookthrough.currency
    if not currency.items:
        return None
    foreign = [item for item in currency.items if item.label != "EUR"]
    eur = _weight(currency, "EUR") or 0.0
    if not foreign:
        return SummaryPoint(
            topic=Topic.CURRENCY,
            text="Prácticamente toda tu cartera analizada está en euros.",
        )
    top = foreign[0]
    text = (
        f"Aunque compres en euros, el {_pct(top.weight)} de tu cartera depende del "
        f"{_currency(top.label)}: si el {_currency(top.label)} baja frente al euro, esa parte "
        f"vale menos en euros."
    )
    if eur < NEGLIGIBLE:
        text += " Prácticamente nada está en euros."
    else:
        text += f" En euros está el {_pct(eur)}."
    return SummaryPoint(topic=Topic.CURRENCY, text=text)


def concentration_point(lookthrough: LookThroughResult) -> SummaryPoint | None:
    if not (_ok(lookthrough.top10_weight) and lookthrough.top_companies):
        return None
    top = lookthrough.top_companies[0]
    text = (
        f"Las 10 empresas en las que más tienes suman el {_pct(lookthrough.top10_weight.value)} "
        f"de tu renta variable; la mayor es {top.company.title()}, con el "
        f"{format_percent(top.weight, 1)}."
    )
    if _ok(lookthrough.effective_companies) and lookthrough.companies_count:
        text += (
            f" Tienes {format_number(lookthrough.companies_count, 0)} empresas, pero tu "
            f"concentración equivale a tener "
            f"{format_number(lookthrough.effective_companies.value, 0)} a partes iguales."
        )
    return SummaryPoint(topic=Topic.CONCENTRATION, text=text)


def overlap_point(lookthrough: LookThroughResult, names: dict[str, str]) -> SummaryPoint | None:
    if not lookthrough.overlaps:
        return None
    pair = lookthrough.overlaps[0]
    a, b = short_fund_name(names[pair.isin_a]), short_fund_name(names[pair.isin_b])
    if pair.overlap >= SAME_INDEX_OVERLAP:
        text = (
            f"{a} y {b} coinciden en un {_pct(pair.overlap)}: son prácticamente las mismas "
            f"empresas."
        )
    elif pair.overlap >= NOTABLE_OVERLAP:
        text = f"El {_pct(pair.overlap)} del contenido de {a} y {b} es el mismo."
    else:
        return None
    if _ok(lookthrough.shared_companies_weight):
        text += (
            f" En total, el {_pct(lookthrough.shared_companies_weight.value)} de tu renta "
            f"variable está en empresas que aparecen en más de uno de tus ETFs."
        )
    return SummaryPoint(topic=Topic.OVERLAP, text=text)


def risk_point(risk: RiskResult) -> SummaryPoint | None:
    if not (_ok(risk.max_drawdown) and risk.drawdown):
        return None
    dd = risk.drawdown
    text = (
        f"Desde el {format_date(risk.max_drawdown.window_start)} (no hay datos anteriores de "
        f"todos tus ETFs), la peor caída de tu cartera fue del "
        f"{format_percent(abs(risk.max_drawdown.value), 1)}, del {format_date(dd.peak)} al "
        f"{format_date(dd.trough)}"
    )
    if dd.recovered:
        text += f", y tardó unos {_months_between(dd.trough, dd.recovered)} meses en recuperarse."
    else:
        text += ", y a la fecha de los datos aún no se había recuperado."
    if risk.var_95_1d_eur is not None:
        text += (
            f" En 1 de cada 20 días de los últimos 5 años perdió al menos "
            f"{format_eur(risk.var_95_1d_eur, 0)}."
        )
    return SummaryPoint(topic=Topic.RISK, text=text)


def market_point(risk: RiskResult) -> SummaryPoint | None:
    if not _ok(risk.beta):
        return None
    move = format_number(risk.beta.value * 10, 1)
    text = (
        f"Cuando el mercado mundial de acciones sube o baja un 10 %, tu cartera ha tendido a "
        f"moverse en torno a un {move} %."
    )
    if WARNING_LOW_EQUITY_SHARE_FOR_BETA in risk.beta.warnings:
        text += (
            " Con tanta renta fija, compararla con un índice de acciones dice poco: tómalo como "
            "orientación."
        )
    alpha = risk.alpha
    if _ok(alpha) and alpha.interval is not None:
        low, high = alpha.interval.low, alpha.interval.high
        if low <= 0 <= high:
            text += (
                " Descontado eso, la diferencia con el mercado no se distingue de cero "
                f"(entre {format_percent(low, 1)} y {format_percent(high, 1)} al año)."
            )
        else:
            text += (
                " Descontado eso, la diferencia con el mercado está entre "
                f"{format_percent(low, 1)} y {format_percent(high, 1)} al año, con incertidumbre."
            )
    return SummaryPoint(topic=Topic.MARKET, text=text)


def returns_point(returns: ReturnsResult) -> SummaryPoint | None:
    metric = returns.annualised_return
    if not _ok(metric):
        return None
    return SummaryPoint(
        topic=Topic.RETURNS,
        text=(
            f"Con tu reparto actual, desde el {format_date(metric.window_start)} habría rendido "
            f"de media un {format_percent(metric.value, 1)} al año en euros. Es una simulación "
            f"del pasado, no tu rentabilidad ni una previsión."
        ),
    )


def build_summary(
    portfolio: Portfolio,
    costs: CostsResult,
    lookthrough: LookThroughResult,
    returns: ReturnsResult,
    risk: RiskResult,
    fund_names: dict[str, str],
    reference: LookThroughResult | None = None,
) -> Summary:
    candidates = [
        coverage_point(portfolio),
        asset_mix_point(lookthrough),
        costs_point(costs),
        geography_point(lookthrough, reference),
        currency_point(lookthrough),
        concentration_point(lookthrough),
        overlap_point(lookthrough, fund_names),
        risk_point(risk),
        market_point(risk),
        returns_point(returns),
    ]
    return Summary(points=tuple(point for point in candidates if point is not None))
