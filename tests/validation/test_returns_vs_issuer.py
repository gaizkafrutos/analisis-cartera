"""Our NAV-based yearly total returns vs the yearly returns iShares publishes.

Compared in the NAV currency (no FX involved), for the five discrete years of every fund.

Tolerance, derived from the issuer's own rounding (not tuned to pass):
    - each NAV is published with 2 decimals: up to 0.005 of error at each end of the year,
      i.e. a relative error of 0.005/NAV_start + 0.005/NAV_end on the growth factor;
    - each published return is rounded to 0.01 %: up to 0.005 percentage points.
So funds with a low NAV per share (a few euros) get a wider tolerance than funds at 100+.
"""

import pandas as pd
import pytest

from radiografia import service
from radiografia.analytics.returns import total_return_index

pytestmark = pytest.mark.validation

NAV_ROUNDING = 0.005
PUBLISHED_ROUNDING = 0.00005  # 0.005 percentage points as a fraction


@pytest.fixture(scope="module")
def snapshot():
    snap = service.get_snapshot()
    if snap is None or snap.navs is None:
        pytest.skip("no local price snapshot: run scripts/build_holdings.py and build_prices.py")
    return snap


def _isins():
    # only iShares: the local price snapshot is built from its workbooks (build_prices.py)
    return sorted(i for i, f in service.get_universe().funds.items() if f.issuer == "iShares")


@pytest.mark.parametrize("isin", _isins())
def test_yearly_returns_match_issuer(snapshot, isin):
    nav = snapshot.navs[snapshot.navs["isin"] == isin].set_index("date")["nav"].sort_index()
    dist = snapshot.distributions[snapshot.distributions["isin"] == isin]
    index = total_return_index(nav, dist.set_index("ex_date")["amount"] if len(dist) else None)
    published = snapshot.performance[
        (snapshot.performance["isin"] == isin) & (snapshot.performance["table"] == "Discrete")
    ].dropna(subset=["fund"])
    assert len(published) > 0
    for row in published.itertuples():
        # the issuer uses the last NAV on or before each date (year ends can fall on a weekend)
        start, end = pd.Timestamp(row.start), pd.Timestamp(row.end)
        nav_start, nav_end = nav.asof(start), nav.asof(end)
        computed = index.asof(end) / index.asof(start) - 1
        tolerance = (NAV_ROUNDING / nav_start + NAV_ROUNDING / nav_end) * (
            1 + abs(computed)
        ) + PUBLISHED_ROUNDING
        assert computed == pytest.approx(row.fund, abs=tolerance), (
            f"{row.period}: published {row.fund:.4%}, computed {computed:.4%}"
        )


def test_distributions_matter_for_distributing_funds(snapshot):
    """Without distributions the euro government bond ETF would lose ~2.5 points more a year."""
    isin = "IE00B4WXJJ64"
    nav = snapshot.navs[snapshot.navs["isin"] == isin].set_index("date")["nav"].sort_index()
    dist = snapshot.distributions[snapshot.distributions["isin"] == isin].set_index("ex_date")
    start, end = pd.Timestamp("2025-09-30"), pd.Timestamp("2026-09-30")
    with_dist = total_return_index(nav, dist["amount"])
    nav_only = total_return_index(nav)
    gap = (with_dist.asof(end) / with_dist.asof(start)) - (
        nav_only.asof(end) / nav_only.asof(start)
    )
    assert gap > 0.02
