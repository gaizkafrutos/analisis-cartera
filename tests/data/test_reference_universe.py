"""Checks on the committed reference universe (data/reference/*.csv). No network needed.

These guard against a bad rebuild of the universe: wrong units, missing listings, a fund that a
Spanish investor could not buy in euros, or tickers that stop resolving.
"""

from collections import Counter

import pytest

from radiografia.data.universe import load_universe
from radiografia.domain.fund import AssetClass
from radiografia.domain.portfolio import CoverageStatus, RawPosition
from radiografia.input import build_portfolio

ACWI = "IE00B6R52259"  # default benchmark (see CLAUDE.md, "Decisiones")


@pytest.fixture(scope="module")
def universe():
    return load_universe()


ISSUER_SITES = {
    "iShares": "https://www.ishares.com/",
    "Xtrackers": "https://etf.dws.com/",
    "Amundi": "https://www.amundietf.es/",
    "SPDR": "https://www.ssga.com/",
}


def test_size_and_asset_classes(universe):
    assert len(universe.funds) == 18
    counts = Counter(f.asset_class for f in universe.funds.values())
    assert counts == {AssetClass.EQUITY: 15, AssetClass.FIXED_INCOME: 3}
    issuers = Counter(f.issuer for f in universe.funds.values())
    assert issuers == {"iShares": 15, "Xtrackers": 1, "Amundi": 1, "SPDR": 1}


def test_benchmark_fund_is_in_the_universe(universe):
    assert "MSCI ACWI" in universe.funds[ACWI].benchmark.replace("All Country World", "ACWI")


def test_every_fund_has_provenance(universe):
    for fund in universe.funds.values():
        assert fund.source_url.startswith(ISSUER_SITES[fund.issuer])
        assert fund.retrieved_on is not None


def test_every_fund_can_be_bought_in_euros(universe):
    with_eur_listing = {li.isin for li in universe.listings if li.currency == "EUR"}
    assert set(universe.funds) <= with_eur_listing


def test_no_ticker_is_ambiguous_inside_the_universe(universe):
    ambiguous = {t: isins for t, isins in universe.index().tickers.items() if len(isins) > 1}
    assert ambiguous == {}


def test_all_funds_are_physical(universe):
    # If a synthetic ETF is added, look-through must not use its holdings file (CLAUDE.md).
    assert {f.replication.value for f in universe.funds.values()} == {"physical"}


@pytest.mark.parametrize(
    ("ticker", "isin"),
    [
        ("EUNL", "IE00B4L5Y983"),
        ("IWDA", "IE00B4L5Y983"),
        ("SXR8", "IE00B5BMR087"),
        ("XDWD", "IE00BJ0KDQ92"),
        ("MWRD", "IE000BI8OT95"),
        ("SPYY", "IE00B44Z5B48"),
    ],
)
def test_common_spanish_broker_tickers_resolve(universe, ticker, isin):
    result = build_portfolio([RawPosition(identifier=ticker, amount_eur=100)], universe.index())
    position = result.portfolio.positions[0]
    assert (position.isin, position.coverage) == (isin, CoverageStatus.COVERED)
