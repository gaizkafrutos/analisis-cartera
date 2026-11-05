"""Look-through on a synthetic portfolio computed by hand.

Funds (holdings as market values):
    A  equity:          APPLE US 50 (USD), ALPHABET CLASS A US 10, ALPHABET CLASS C US 10,
                        NESTLE CH 20 (CHF), USD cash 10
    B  equity, hedged:  APPLE US 60, SAP DE 40 (EUR)  -> counts 100 % EUR for currency
    C  fixed income:    BUND DE 70 (EUR), TREASURY US 30 (USD)
Portfolio: A 5000, B 2500, C 2000, a valid ISIN outside the universe 500 (total 10000).

Equity covered = A + B = 75 %. Currency covered = A + B + C = 95 %.
"""

from datetime import date

import pandas as pd
import pytest

from radiografia.analytics import lookthrough as lt
from radiografia.analytics.fund_breakdown import CASH_LABEL
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Replication
from radiografia.domain.metrics import MetricStatus
from radiografia.domain.portfolio import RawPosition
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio

A, B, C, D, OUTSIDE = (
    "IE00B4L5Y983",
    "IE00B441G979",
    "IE00B4WXJJ64",
    "IE00B5BMR087",
    "IE00B3RBWM25",
)
AS_OF = date(2026, 11, 4)


def _fund(isin, asset_class=AssetClass.EQUITY, hedged=False, replication=Replication.PHYSICAL):
    return Fund(
        isin=isin,
        name=f"Fund {isin}",
        issuer="iShares",
        issuer_product_id="1",
        asset_class=asset_class,
        asset_class_raw=asset_class.value,
        benchmark="Index",
        ter=0.002,
        share_class_currency=None,
        base_currency="EUR" if hedged else "USD",
        currency_hedged=hedged,
        income_treatment=IncomeTreatment.ACCUMULATING,
        replication=replication,
        methodology="Optimised",
        domicile="Ireland",
        fund_launch_date=date(2010, 1, 1),
        share_class_launch_date=None,
        source_url="https://example.org",
        retrieved_on=date(2026, 11, 5),
    )


FUNDS = {
    A: _fund(A),
    B: _fund(B, hedged=True),
    C: _fund(C, AssetClass.FIXED_INCOME),
    D: _fund(D),
}

COLUMNS = ["isin", "name", "sector", "asset_class", "location", "market_currency", "market_value"]
HOLDINGS = pd.DataFrame(
    [
        (A, "APPLE", "Information Technology", "Equity", "United States", "USD", 50.0),
        (A, "ALPHABET CLASS A", "Communication", "Equity", "United States", "USD", 10.0),
        (A, "ALPHABET CLASS C", "Communication", "Equity", "United States", "USD", 10.0),
        (A, "NESTLE SA", "Consumer Staples", "Equity", "Switzerland", "CHF", 20.0),
        (A, "USD CASH", CASH_LABEL, "Cash", "United States", "USD", 10.0),
        (B, "APPLE", "Information Technology", "Equity", "United States", "USD", 60.0),
        (B, "SAP", "Information Technology", "Equity", "Germany", "EUR", 40.0),
        (C, "BUND", "Treasuries", "Fixed Income", "Germany", "EUR", 70.0),
        (C, "TREASURY", "Treasuries", "Fixed Income", "United States", "USD", 30.0),
    ],
    columns=COLUMNS,
)
AS_OF_BY_FUND = {A: AS_OF, B: AS_OF, C: date(2026, 11, 3)}


def _portfolio(*rows):
    index = UniverseIndex(isins=frozenset(FUNDS))
    return build_portfolio([RawPosition(identifier=i, amount_eur=a) for i, a in rows], index)


@pytest.fixture
def result():
    portfolio = _portfolio((A, 5000), (B, 2500), (C, 2000), (OUTSIDE, 500)).portfolio
    return lt.compute_lookthrough(portfolio, FUNDS, HOLDINGS, AS_OF_BY_FUND)


def _items(breakdown):
    return {item.label: item.weight for item in breakdown.items}


def test_geography(result):
    # US: 0.5 x 0.70 + 0.25 x 0.60 = 0.50 of 0.75; CH 0.10; DE 0.10; cash 0.05
    assert _items(result.geography) == pytest.approx(
        {"United States": 0.50 / 0.75, "Switzerland": 0.10 / 0.75, "Germany": 0.10 / 0.75,
         CASH_LABEL: 0.05 / 0.75}
    )  # fmt: skip
    assert result.geography.status is MetricStatus.PARTIAL
    assert result.geography.coverage.covered_weight == pytest.approx(0.75)
    assert lt.WARNING_LOOKTHROUGH_PARTIAL in result.geography.warnings
    assert lt.WARNING_COUNTRY_IS_DOMICILE in result.geography.warnings


def test_sector(result):
    # IT: A 0.25 + B 0.25 = 0.50; Communication 0.10; Staples 0.10; cash 0.05
    assert _items(result.sector) == pytest.approx(
        {"Information Technology": 0.50 / 0.75, "Communication": 0.10 / 0.75,
         "Consumer Staples": 0.10 / 0.75, CASH_LABEL: 0.05 / 0.75}
    )  # fmt: skip


def test_currency_with_hedged_class_and_bonds(result):
    # USD: A 0.40 (cash included) + C 0.06; CHF: A 0.10; EUR: B hedged 0.25 + C 0.14
    assert _items(result.currency) == pytest.approx(
        {"USD": 0.46 / 0.95, "EUR": 0.39 / 0.95, "CHF": 0.10 / 0.95}
    )
    assert result.currency.coverage.covered_weight == pytest.approx(0.95)
    assert lt.WARNING_HEDGED_CLASSES_ASSUMED in result.currency.warnings
    # oldest holdings date among the funds used (C is a day older)
    assert result.currency.data_as_of == date(2026, 11, 3)
    assert result.geography.data_as_of == date(2026, 11, 3)


def test_breakdowns_sum_to_one(result):
    for breakdown in (result.geography, result.sector, result.currency):
        assert sum(item.weight for item in breakdown.items) == pytest.approx(1.0)


def test_top_companies_merge_share_classes(result):
    top = {c.company: c.weight for c in result.top_companies}
    # APPLE 0.25 + 0.15 = 0.40; ALPHABET A + C = 0.10; NESTLE 0.10; SAP 0.10 (of 0.75)
    assert top == pytest.approx(
        {"APPLE": 0.40 / 0.75, "ALPHABET": 0.10 / 0.75, "NESTLE SA": 0.10 / 0.75,
         "SAP": 0.10 / 0.75}
    )  # fmt: skip
    assert result.top_companies[0].fund_isins == tuple(sorted((A, B)))


def test_concentration(result):
    assert result.top10_weight.value == pytest.approx(0.70 / 0.75)  # cash excluded
    # shares among companies: 4/7, 1/7, 1/7, 1/7 -> 1 / (16/49 + 3/49) = 49/19
    assert result.effective_companies.value == pytest.approx(49 / 19)


def test_overlap_and_shared_companies(result):
    (pair,) = result.overlaps
    # A: APPLE .5, ALPHABET .2, NESTLE .2; B: APPLE .6, SAP .4 -> min only on APPLE = .5
    assert (pair.isin_a, pair.isin_b) == tuple(sorted((A, B)))
    assert pair.overlap == pytest.approx(0.5)
    assert result.shared_companies_count == 1
    assert result.shared_companies_weight.value == pytest.approx(0.40 / 0.75)


def test_uncovered_positions_have_reasons(result):
    uncovered = {u.reason: u for u in result.uncovered}
    bonds = uncovered[lt.UncoveredReason.FIXED_INCOME_NOT_LOOKED_THROUGH]
    assert bonds.weight == pytest.approx(0.20)
    assert bonds.in_currency_breakdown is True
    outside = uncovered[lt.UncoveredReason.OUTSIDE_UNIVERSE]
    assert outside.weight == pytest.approx(0.05)
    assert outside.in_currency_breakdown is False


def test_fund_without_holdings_is_not_covered():
    portfolio = _portfolio((A, 1000), (D, 1000)).portfolio
    result = lt.compute_lookthrough(portfolio, FUNDS, HOLDINGS, AS_OF_BY_FUND)
    assert result.geography.coverage.covered_weight == pytest.approx(0.5)
    assert [u.reason for u in result.uncovered] == [lt.UncoveredReason.HOLDINGS_NOT_AVAILABLE]


def test_synthetic_etf_is_never_opened():
    funds = {**FUNDS, A: _fund(A, replication=Replication.SYNTHETIC)}
    portfolio = _portfolio((A, 1000)).portfolio
    result = lt.compute_lookthrough(portfolio, funds, HOLDINGS, AS_OF_BY_FUND)
    assert result.geography.status is MetricStatus.NOT_AVAILABLE
    assert result.uncovered[0].reason is lt.UncoveredReason.SYNTHETIC_REPLICATION


def test_no_snapshot_means_not_available_not_invented():
    portfolio = _portfolio((A, 1000), (B, 1000)).portfolio
    result = lt.compute_lookthrough(portfolio, FUNDS, None, {})
    for breakdown in (result.geography, result.sector, result.currency):
        assert breakdown.status is MetricStatus.NOT_AVAILABLE
        assert breakdown.items == ()
    assert result.top10_weight.value is None
    assert result.top_companies == ()
    assert result.overlaps == ()
    assert {u.reason for u in result.uncovered} == {lt.UncoveredReason.HOLDINGS_NOT_AVAILABLE}


def test_full_coverage_is_available():
    portfolio = _portfolio((A, 1000)).portfolio
    result = lt.compute_lookthrough(portfolio, FUNDS, HOLDINGS, AS_OF_BY_FUND)
    assert result.geography.status is MetricStatus.AVAILABLE
    assert lt.WARNING_LOOKTHROUGH_PARTIAL not in result.geography.warnings
    assert result.overlaps == ()  # one fund: nothing to overlap with


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("ALPHABET CLASS A", "ALPHABET"),
        ("FOX CORP CLASS B", "FOX CORP"),
        ("META PLATFORMS CLASS A", "META PLATFORMS"),
        ("CLASSIC MOTORS", "CLASSIC MOTORS"),
    ],
)
def test_company_key(name, key):
    assert lt.company_key(name) == key
