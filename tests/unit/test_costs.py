"""Costs on synthetic funds whose result is known by hand."""

from datetime import date

import pytest

from radiografia.analytics import costs
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Replication
from radiografia.domain.metrics import MetricStatus, Unit
from radiografia.domain.portfolio import RawPosition
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio

WORLD, SP500, HEDGED, OUTSIDE = "IE00B4L5Y983", "IE00B5BMR087", "IE00B441G979", "IE00B3RBWM25"


def _fund(isin, ter, hedged=False, retrieved_on=date(2026, 11, 5)):
    return Fund(
        isin=isin,
        name=f"Fund {isin}",
        issuer="iShares",
        issuer_product_id="1",
        asset_class=AssetClass.EQUITY,
        asset_class_raw="Equity",
        benchmark="Index",
        ter=ter,
        share_class_currency=None,
        base_currency="USD",
        currency_hedged=hedged,
        income_treatment=IncomeTreatment.ACCUMULATING,
        replication=Replication.PHYSICAL,
        methodology="Optimised",
        domicile="Ireland",
        fund_launch_date=date(2010, 1, 1),
        share_class_launch_date=None,
        source_url="https://example.org",
        retrieved_on=retrieved_on,
    )


FUNDS = {
    WORLD: _fund(WORLD, 0.0020),
    SP500: _fund(SP500, 0.0007, retrieved_on=date(2026, 11, 4)),
    HEDGED: _fund(HEDGED, 0.0055, hedged=True),
}
INDEX = UniverseIndex(isins=frozenset(FUNDS))


def _costs(*rows):
    result = build_portfolio([RawPosition(identifier=i, amount_eur=a) for i, a in rows], INDEX)
    return costs.compute_costs(result.portfolio, FUNDS)


def test_worked_example_from_the_explanation():
    # 6000 x 0.20 % + 3000 x 0.07 % + 1000 x 0.55 % = 12 + 2.10 + 5.50 = 19.60 EUR
    result = _costs((WORLD, 6000), (SP500, 3000), (HEDGED, 1000))
    assert result.annual_cost.value == pytest.approx(19.60)
    assert result.weighted_ter.value == pytest.approx(0.00196)
    assert result.weighted_ter.status is MetricStatus.AVAILABLE
    assert result.weighted_ter.unit is Unit.FRACTION
    assert result.annual_cost.unit is Unit.EUR_PER_YEAR
    assert result.weighted_ter.coverage.covered_weight == pytest.approx(1.0)


def test_lines_sorted_by_cost_with_share_of_cost():
    result = _costs((WORLD, 6000), (SP500, 3000), (HEDGED, 1000))
    assert [line.isin for line in result.lines] == [WORLD, HEDGED, SP500]
    hedged = result.lines[1]
    # 10 % of the money, 28 % of the cost: 5.50 / 19.60
    assert hedged.weight == pytest.approx(0.10)
    assert hedged.share_of_cost == pytest.approx(5.50 / 19.60)
    assert sum(line.share_of_cost for line in result.lines) == pytest.approx(1.0)


def test_annual_cost_equals_weighted_ter_times_covered_amount():
    result = _costs((WORLD, 1234.56), (SP500, 789.01), (HEDGED, 50), (OUTSIDE, 999))
    coverage = result.weighted_ter.coverage
    assert result.annual_cost.value == pytest.approx(
        result.weighted_ter.value * coverage.covered_amount_eur
    )


def test_partial_coverage_never_assumes_zero_cost():
    result = _costs((WORLD, 6000), (SP500, 3000), (HEDGED, 1000), (OUTSIDE, 1000))
    ter = result.weighted_ter
    assert ter.status is MetricStatus.PARTIAL
    # The unknown fund does not dilute the average: still 19.60 / 10000
    assert ter.value == pytest.approx(0.00196)
    assert ter.coverage.covered_weight == pytest.approx(10000 / 11000)
    assert ter.coverage.not_covered_amount_eur == pytest.approx(1000)
    assert costs.WARNING_PARTIAL_COVERAGE in ter.warnings
    unknown = result.lines[-1]
    assert (unknown.isin, unknown.ter, unknown.annual_cost_eur) == (OUTSIDE, None, None)


def test_nothing_covered_means_not_available():
    result = _costs((OUTSIDE, 1000))
    for metric in (result.weighted_ter, result.annual_cost):
        assert metric.status is MetricStatus.NOT_AVAILABLE
        assert metric.value is None
        assert metric.data_as_of is None
    assert result.weighted_ter.coverage.covered_weight == 0


def test_warnings_and_data_date():
    plain = _costs((WORLD, 100))
    assert plain.weighted_ter.warnings == (costs.WARNING_TER_IS_NOT_TOTAL_COST,)
    hedged = _costs((WORLD, 100), (SP500, 100), (HEDGED, 100))
    assert costs.WARNING_HEDGING_COST_NOT_IN_TER in hedged.weighted_ter.warnings
    # the oldest TER retrieval date is reported
    assert hedged.weighted_ter.data_as_of == date(2026, 11, 4)


def test_result_is_json_serialisable():
    data = _costs((WORLD, 100), (OUTSIDE, 100)).model_dump(mode="json")
    assert data["weighted_ter"]["status"] == "partial"
    assert data["lines"][1]["ter"] is None
