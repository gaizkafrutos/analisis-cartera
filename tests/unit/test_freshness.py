"""Age of the holdings and the one-month warning."""

from datetime import date

from radiografia import service
from radiografia.analytics.freshness import STALE_AFTER_DAYS, data_freshness
from radiografia.data.datasets import DEMO, PUBLIC


def test_age_and_threshold():
    as_of = date(2026, 10, 1)
    assert data_freshness(None, date(2026, 11, 7)) is None
    fresh = data_freshness(as_of, date(2026, 11, 1))
    assert (fresh.age_days, fresh.stale) == (31, False)  # a month is still fine
    old = data_freshness(as_of, date(2026, 11, 2))
    assert (old.age_days, old.stale) == (32, True)
    assert STALE_AFTER_DAYS == 31


def test_report_carries_the_age_except_in_the_demo():
    csv = service.example_portfolio_csv("global", DEMO)
    demo = service.analyze(service.read_portfolio_csv(csv, service.get_universe(DEMO)).portfolio,
                           source=DEMO, today=date(2030, 1, 1))  # fmt: skip
    assert demo.freshness is None  # invented dates are never flagged
    csv = service.example_portfolio_csv("solapada", PUBLIC)
    portfolio = service.read_portfolio_csv(csv, service.get_universe(PUBLIC)).portfolio
    report = service.analyze(portfolio, source=PUBLIC, today=date(2026, 11, 7))
    assert report.freshness.holdings_as_of == report.lookthrough.geography.data_as_of
    assert report.freshness.stale  # SEC filings are published about two months late
