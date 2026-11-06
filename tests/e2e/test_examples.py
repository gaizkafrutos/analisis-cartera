"""End to end on the three example portfolios with real data (local snapshot needed).

The assertions are relationships each example is built to show, not exact numbers, so they hold
when the snapshot is refreshed:
    - global diversified: 70 % equity / 30 % bonds, World and emerging markets do not overlap,
      alpha is not shown (equity under 80 %), beta below 1;
    - concentrated: almost only US technology, few effective companies, high beta and a very
      wide alpha interval;
    - overlapping: World and S&P 500 share most of their content, more US than the World alone.
"""

import pytest

from radiografia import service
from radiografia.domain.metrics import MetricStatus
from radiografia.reporting.summary import Topic

pytestmark = pytest.mark.validation

WORLD, EM, SP500 = "IE00B4L5Y983", "IE00BKM4GZ66", "IE00B5BMR087"


def _report(key):
    if service.get_snapshot() is None:
        pytest.skip("no local snapshot")
    return service.analyze(service.read_portfolio_csv(service.example_portfolio_csv(key)).portfolio)


def _weights(breakdown):
    return {item.label: item.weight for item in breakdown.items}


def _overlap(report, a, b):
    pair = next(p for p in report.lookthrough.overlaps if {p.isin_a, p.isin_b} == {a, b})
    return pair.overlap


@pytest.mark.parametrize("key", [example.key for example in service.EXAMPLES])
def test_every_section_is_available(key):
    report = _report(key)
    assert report.portfolio.covered_weight == pytest.approx(1.0)
    for metric in (
        report.costs.weighted_ter,
        report.lookthrough.geography,
        report.lookthrough.currency,
        report.lookthrough.top10_weight,
        report.returns.annualised_return,
        report.risk.volatility,
        report.risk.max_drawdown,
        report.risk.var_95_1d,
        report.risk.beta,
    ):
        assert metric.status is not MetricStatus.NOT_AVAILABLE, metric.key
    topics = {point.topic for point in report.summary.points}
    assert {Topic.COSTS, Topic.GEOGRAPHY, Topic.CURRENCY, Topic.RISK, Topic.MARKET} <= topics
    assert report.model_dump_json()


def test_global_diversified():
    report = _report("global")
    lt = report.lookthrough
    assert lt.geography.coverage.covered_weight == pytest.approx(0.70)  # equity part
    assert lt.currency.coverage.covered_weight == pytest.approx(1.0)  # bonds count for currency
    assert _overlap(report, WORLD, EM) < 0.01  # developed vs emerging: no common companies
    assert report.risk.alpha.status is MetricStatus.NOT_AVAILABLE  # equity under 80 %
    assert report.risk.beta.value < 1
    assert Topic.ASSET_MIX in {point.topic for point in report.summary.points}


def test_concentrated():
    report = _report("concentrada")
    lt = report.lookthrough
    assert _weights(lt.geography)["United States"] > 0.95
    assert lt.top10_weight.value > 0.5
    assert lt.effective_companies.value < 30
    assert report.risk.beta.value > 1.2
    interval = report.risk.alpha.interval
    assert interval.high - interval.low > 0.10  # alpha is very uncertain
    assert interval.low < 0 < interval.high


def test_overlapping():
    report = _report("solapada")
    world_only = service.analyze(
        service.read_portfolio_csv("identificador;importe_eur\nEUNL;10000\n").portfolio
    )
    assert _overlap(report, WORLD, SP500) > 0.6
    assert report.lookthrough.shared_companies_weight.value > 0.5
    us = _weights(report.lookthrough.geography)["United States"]
    assert us > _weights(world_only.lookthrough.geography)["United States"]
