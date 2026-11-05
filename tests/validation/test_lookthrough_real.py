"""Look-through on real holdings (local snapshot needed; `pytest -m validation`).

1. A portfolio that is 100 % one ETF must reproduce the issuer's own breakdown for that ETF,
   which the issuer publishes (validated fund by fund in test_issuer_breakdowns.py).
2. A multi-ETF portfolio must equal the hand formula sum(ETF weight x weight inside the ETF).
"""

import pytest

from radiografia import service
from radiografia.analytics.fund_breakdown import holding_weights
from radiografia.domain.metrics import MetricStatus
from radiografia.domain.portfolio import RawPosition

pytestmark = pytest.mark.validation

WORLD, SP500, WORLD_HEDGED = "IE00B4L5Y983", "IE00B5BMR087", "IE00B441G979"
TOLERANCE = 0.0001  # same as the issuer-breakdown validation (0.01 pp)


@pytest.fixture(scope="module")
def snapshot():
    snap = service.get_snapshot()
    if snap is None:
        pytest.skip("no local snapshot: run scripts/build_holdings.py")
    return snap


def _report(snapshot, *rows):
    result = service.read_portfolio_rows([RawPosition(identifier=i, amount_eur=a) for i, a in rows])
    return service.analyze(result.portfolio, snapshot=snapshot)


def test_single_etf_portfolio_reproduces_issuer_geography(snapshot):
    report = _report(snapshot, (WORLD, 10000))
    computed = {item.label: item.weight for item in report.lookthrough.geography.items}
    published = snapshot.breakdowns[
        (snapshot.breakdowns["isin"] == WORLD)
        & (snapshot.breakdowns["section"] == "Geography/Locations")
        & (snapshot.breakdowns["label"] != "Other")
    ]
    assert report.lookthrough.geography.status is MetricStatus.AVAILABLE
    for label, weight in zip(published["label"], published["weight"], strict=True):
        assert computed.get(label, 0.0) == pytest.approx(weight, abs=TOLERANCE), label


def test_apple_weight_matches_hand_formula(snapshot):
    weights = {WORLD: 0.6, SP500: 0.3, WORLD_HEDGED: 0.1}
    report = _report(snapshot, *[(isin, w * 10000) for isin, w in weights.items()])
    expected = 0.0
    for isin, fund_weight in weights.items():
        lines = snapshot.holdings[snapshot.holdings["isin"] == isin]
        inside = holding_weights(lines)[lines["name"] == "APPLE"].sum()
        expected += fund_weight * inside
    apple = next(c for c in report.lookthrough.top_companies if c.company == "APPLE")
    assert apple.weight == pytest.approx(expected, rel=1e-9)  # whole portfolio is equity
    assert apple.fund_isins == tuple(sorted(weights))


def test_hedged_class_moves_its_weight_to_eur(snapshot):
    unhedged = _report(snapshot, (WORLD, 10000)).lookthrough.currency
    hedged = _report(snapshot, (WORLD, 9000), (WORLD_HEDGED, 1000)).lookthrough.currency
    usd = {i.label: i.weight for i in unhedged.items}["USD"]
    usd_hedged = {i.label: i.weight for i in hedged.items}["USD"]
    assert usd_hedged == pytest.approx(0.9 * usd, abs=1e-9)
    assert {i.label: i.weight for i in hedged.items}["EUR"] >= 0.1
