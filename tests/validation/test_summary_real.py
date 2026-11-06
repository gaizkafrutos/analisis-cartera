"""Summaries of real portfolios: complete, consistent with the metrics, never recommending."""

import pytest

from radiografia import service
from radiografia.domain.portfolio import RawPosition
from radiografia.reporting.formatting import format_eur
from radiografia.reporting.summary import Topic

pytestmark = pytest.mark.validation

FORBIDDEN = ("deberías", "debes", "recomend", "te conviene", "compra ", "vende ", "cámbiate")

PORTFOLIOS = {
    "example": [("EUNL", 6000), ("SXR8", 3000), ("IE00B441G979", 1000)],
    "concentrated": [("SXRV", 6000), ("QDVE", 4000)],
    "overlapping": [("EUNL", 5000), ("SXR8", 3000), ("SXRV", 2000)],
    "bonds_and_outside": [("EUNL", 4000), ("IE00B4WXJJ64", 3000), ("AGGH", 2000),
                          ("IE00BK5BQT80", 1000)],
}  # fmt: skip


@pytest.fixture(scope="module", params=sorted(PORTFOLIOS))
def report(request):
    if service.get_snapshot() is None:
        pytest.skip("no local snapshot")
    rows = [RawPosition(identifier=i, amount_eur=a) for i, a in PORTFOLIOS[request.param]]
    return request.param, service.analyze(service.read_portfolio_rows(rows).portfolio)


def test_summary_is_complete_and_consistent(report):
    name, result = report
    texts = {p.topic: p.text for p in result.summary.points}
    expected = {
        Topic.COSTS,
        Topic.GEOGRAPHY,
        Topic.CURRENCY,
        Topic.CONCENTRATION,
        Topic.RISK,
        Topic.MARKET,
    }
    assert expected <= set(texts)
    assert format_eur(result.costs.annual_cost.value) in texts[Topic.COSTS]
    if name == "bonds_and_outside":
        assert {Topic.COVERAGE, Topic.ASSET_MIX} <= set(texts)
        assert "dice poco" in texts[Topic.MARKET]  # beta caution with mostly bonds
    assert "mercado mundial" in texts[Topic.RISK]  # episodes compared with the ACWI
    assert "1 de cada 20" not in texts[Topic.RISK]  # VaR left out after the audit


def test_summary_never_recommends(report):
    _, result = report
    for point in result.summary.points:
        assert not [w for w in FORBIDDEN if w in point.text.lower()], point.text
