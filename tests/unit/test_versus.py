"""The side-by-side block reads values already computed (presentation only)."""

from radiografia import service
from radiografia.data.datasets import DEMO
from radiografia.reporting.presentation import versus_rows


def test_rows_come_from_both_lookthroughs():
    csv = service.example_portfolio_csv("concentrada", DEMO)
    portfolio = service.read_portfolio_csv(csv, service.get_universe(DEMO)).portfolio
    report = service.analyze(portfolio, source=DEMO)
    rows = {key: (mine, world) for key, mine, world in versus_rows(report.lookthrough,
                                                                    report.reference)}  # fmt: skip
    assert set(rows) == {"us", "usd", "top10", "effective"}
    us = next(i.weight for i in report.lookthrough.geography.items if i.label == "United States")
    assert rows["us"][0] == us
    assert rows["effective"] == (
        report.lookthrough.effective_companies.value,
        report.reference.effective_companies.value,
    )
    assert rows["us"][0] > rows["us"][1]  # the concentrated example is more US than the world
    assert versus_rows(report.lookthrough, None) == []
