from datetime import date

import pandas as pd
import pytest

from radiografia.analytics import costs
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Replication
from radiografia.domain.metrics import MetricStatus
from radiografia.domain.portfolio import RawPosition
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio

WORLD, SP500, HEDGED = "IE00B4L5Y983", "IE00B5BMR087", "IE00B441G979"


def _fund(isin, ter, hedged=False):
    return Fund(
        isin=isin,
        name=isin,
        issuer="iShares",
        issuer_product_id="1",
        asset_class=AssetClass.EQUITY,
        asset_class_raw="Equity",
        benchmark="Index",
        ter=ter,
        share_class_currency="EUR" if hedged else "USD",
        base_currency="USD",
        currency_hedged=hedged,
        income_treatment=IncomeTreatment.ACCUMULATING,
        replication=Replication.PHYSICAL,
        methodology="Optimised",
        domicile="Ireland",
        fund_launch_date=date(2010, 1, 1),
        share_class_launch_date=None,
        source_url="https://example.org",
        retrieved_on=date(2026, 11, 5),
    )


FUNDS = {
    WORLD: _fund(WORLD, 0.002),
    SP500: _fund(SP500, 0.0007),
    HEDGED: _fund(HEDGED, 0.0055, True),
}

PERFORMANCE = pd.DataFrame(
    [
        (WORLD, "Annualised", date(2026, 9, 30), "5y", 0.1195, 0.1189),
        (WORLD, "Annualised", date(2026, 10, 31), "5y", 0.1056, 0.1049),  # latest -> +0.07 %
        (WORLD, "Annualised", date(2026, 10, 31), "1y", 0.1213, 0.1211),
        (SP500, "Annualised", date(2026, 10, 31), "5y", 0.1500, 0.1483),  # +0.17 %
        (HEDGED, "Annualised", date(2026, 10, 31), "5y", 0.0900, 0.1200),  # other currency
    ],
    columns=["isin", "table", "as_of", "period", "fund", "benchmark"],
)


def test_tracking_difference_uses_latest_five_year_figure_and_skips_hedged():
    td = costs.tracking_differences(PERFORMANCE, FUNDS)
    assert set(td) == {WORLD, SP500}
    assert td[WORLD].value == pytest.approx(0.0007)
    assert td[WORLD].as_of == date(2026, 10, 31)
    assert td[SP500].value == pytest.approx(0.0017)


def test_weighted_tracking_difference_on_funds_that_have_it():
    index = UniverseIndex(isins=frozenset(FUNDS))
    rows = [(WORLD, 6000), (SP500, 3000), (HEDGED, 1000)]
    portfolio = build_portfolio(
        [RawPosition(identifier=i, amount_eur=a) for i, a in rows], index
    ).portfolio
    result = costs.compute_costs(portfolio, FUNDS, costs.tracking_differences(PERFORMANCE, FUNDS))
    metric = result.tracking_difference
    # (0.6 x 0.07 % + 0.3 x 0.17 %) / 0.9
    assert metric.value == pytest.approx((0.6 * 0.0007 + 0.3 * 0.0017) / 0.9)
    assert metric.status is MetricStatus.PARTIAL
    assert metric.coverage.covered_weight == pytest.approx(0.9)
    assert costs.WARNING_TD_NOT_FOR_HEDGED in metric.warnings
    by_isin = {line.isin: line.tracking_difference for line in result.lines}
    assert by_isin[HEDGED] is None


def test_without_issuer_data_tracking_difference_is_not_available():
    assert costs.tracking_differences(None, FUNDS) == {}
