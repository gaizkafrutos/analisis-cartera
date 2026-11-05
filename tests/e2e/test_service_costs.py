"""End to end through the service with the committed universe (no network)."""

import pytest

from radiografia import service
from radiografia.domain.metrics import MetricStatus


def test_csv_to_costs_with_real_universe():
    # Spanish Excel CSV using Xetra tickers and an ISIN; TERs from data/reference (5-nov-2026):
    # World 0.20 %, S&P 500 0.07 %, World EUR Hedged 0.55 %
    csv_text = "identificador;importe_eur\nEUNL;6.000\nSXR8;3.000,00\nIE00B441G979;1000\n"
    result = service.read_portfolio_csv(csv_text)
    assert result.ok, result.errors
    report = service.analyze(result.portfolio)
    assert report.costs.annual_cost.value == pytest.approx(19.60)
    assert report.costs.weighted_ter.value == pytest.approx(0.00196)
    assert report.costs.weighted_ter.status is MetricStatus.AVAILABLE
    assert report.costs.lines[0].label == "iShares Core MSCI World UCITS ETF"
    assert report.model_dump_json()  # serialisable for a future API / PDF


def test_form_rows_with_a_fund_outside_the_universe():
    from radiografia.domain.portfolio import RawPosition

    rows = [
        RawPosition(identifier="IWDA", amount_eur=9000),
        RawPosition(identifier="IE00BK5BQT80", amount_eur=1000),  # Vanguard, not in universe
    ]
    report = service.analyze(service.read_portfolio_rows(rows).portfolio)
    assert report.costs.weighted_ter.status is MetricStatus.PARTIAL
    assert report.costs.weighted_ter.value == pytest.approx(0.0020)
    assert report.costs.annual_cost.value == pytest.approx(18.0)
    assert report.costs.weighted_ter.coverage.covered_weight == pytest.approx(0.9)


def test_without_snapshot_lookthrough_is_not_available_but_costs_work():
    # This is what CI sees: no local holdings snapshot (it is git-ignored).
    from radiografia.domain.portfolio import RawPosition

    rows = [RawPosition(identifier="EUNL", amount_eur=1000)]
    report = service.analyze(service.read_portfolio_rows(rows).portfolio, snapshot=None)
    assert report.costs.weighted_ter.status is MetricStatus.AVAILABLE
    assert report.lookthrough.geography.status is MetricStatus.NOT_AVAILABLE
    assert report.lookthrough.currency.items == ()
    assert report.model_dump_json()
