from datetime import date

import pytest

from radiografia.data.universe import Universe, load_universe, write_universe
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Listing, Replication


def _fund(isin="IE00B4L5Y983", **overrides):
    data = {
        "isin": isin,
        "name": "Test fund",
        "issuer": "iShares",
        "issuer_product_id": "1",
        "asset_class": AssetClass.EQUITY,
        "asset_class_raw": "Equity",
        "benchmark": "Index",
        "ter": 0.002,
        "share_class_currency": None,
        "base_currency": "USD",
        "currency_hedged": False,
        "income_treatment": IncomeTreatment.ACCUMULATING,
        "replication": Replication.PHYSICAL,
        "methodology": "Optimised",
        "domicile": "Ireland",
        "fund_launch_date": date(2009, 9, 25),
        "share_class_launch_date": None,
        "source_url": "https://example.org",
        "retrieved_on": date(2026, 11, 5),
    }
    return Fund(**{**data, **overrides})


def _listing(isin, ticker, exchange="Xetra"):
    return Listing(isin=isin, exchange=exchange, ticker=ticker, currency="EUR")


def test_round_trip_keeps_every_field(tmp_path):
    funds = [_fund(), _fund("IE00BK5BQT80", ter=0.0022, currency_hedged=True)]
    listings = [_listing("IE00B4L5Y983", "EUNL"), _listing("IE00BK5BQT80", "VWCE")]
    write_universe(funds, listings, tmp_path)
    universe = load_universe(tmp_path)
    assert universe.funds == {f.isin: f for f in funds}
    assert set(universe.listings) == set(listings)


def test_duplicate_isin_is_rejected(tmp_path):
    write_universe([_fund(), _fund()], [], tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        load_universe(tmp_path)


def test_listing_without_fund_is_rejected(tmp_path):
    write_universe([_fund()], [_listing("IE00BK5BQT80", "VWCE")], tmp_path)
    with pytest.raises(ValueError, match="not in universe"):
        load_universe(tmp_path)


def test_index_maps_every_ticker_and_detects_ambiguity():
    universe = Universe(
        funds={f.isin: f for f in [_fund(), _fund("IE00BK5BQT80")]},
        listings=(
            _listing("IE00B4L5Y983", "EUNL"),
            _listing("IE00B4L5Y983", "IWDA", "Euronext Amsterdam"),
            _listing("IE00B4L5Y983", "IWDA", "London Stock Exchange"),
            _listing("IE00BK5BQT80", "VWCE"),
            _listing("IE00BK5BQT80", "IWDA", "Somewhere else"),
        ),
    )
    index = universe.index()
    assert index.isins == {"IE00B4L5Y983", "IE00BK5BQT80"}
    assert index.tickers["EUNL"] == {"IE00B4L5Y983"}
    assert index.tickers["IWDA"] == {"IE00B4L5Y983", "IE00BK5BQT80"}  # ambiguous
