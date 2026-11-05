"""Our 3-year volatility of each ETF vs the 'Standard Deviation (3y)' iShares publishes.

The issuer's figure: sample standard deviation of 36 monthly total returns in the NAV currency,
annualised with sqrt(12) (with the population formula it would be ~0.16 points lower).

Tolerance, derived from rounding (not tuned to pass):
    - the published figure has 2 decimals: 0.005 percentage points;
    - NAVs have 2 decimals, so each monthly return carries an error of at most 2 x 0.005 / NAV.
      The standard deviation moves at most by the size of that error (Minkowski inequality),
      i.e. sqrt(12 x 36/35) x 2 x 0.005 / lowest NAV in the window, annualised.
Funds with a NAV of a few euros therefore get a much wider tolerance.
"""

import numpy as np
import pandas as pd
import pytest

from radiografia import service
from radiografia.analytics.returns import total_return_index

pytestmark = pytest.mark.validation

MONTHS = 36


@pytest.fixture(scope="module")
def snapshot():
    snap = service.get_snapshot()
    if snap is None or snap.characteristics is None:
        pytest.skip("no local price snapshot: run scripts/build_holdings.py and build_prices.py")
    return snap


@pytest.mark.parametrize("isin", sorted(service.get_universe().funds))
def test_three_year_volatility_matches_issuer(snapshot, isin):
    published = snapshot.characteristics[
        (snapshot.characteristics["isin"] == isin)
        & (snapshot.characteristics["label"] == "Standard Deviation (3y)")
    ]
    if published.empty:
        pytest.skip("issuer publishes no 3-year standard deviation")
    value = float(published["value"].iloc[0].rstrip("%")) / 100
    as_of = pd.Timestamp(published["as_of"].iloc[0])

    nav = snapshot.navs[snapshot.navs["isin"] == isin].set_index("date")["nav"].sort_index()
    dist = snapshot.distributions[snapshot.distributions["isin"] == isin]
    index = total_return_index(nav, dist.set_index("ex_date")["amount"] if len(dist) else None)
    month_ends = index.resample("ME").last()
    monthly = month_ends[month_ends.index <= as_of].pct_change().dropna().iloc[-MONTHS:]
    computed = monthly.std(ddof=1) * np.sqrt(12)

    lowest_nav = nav[nav.index > as_of - pd.DateOffset(months=MONTHS + 1)].min()
    tolerance = 0.00005 + np.sqrt(12 * MONTHS / (MONTHS - 1)) * 2 * 0.005 / lowest_nav
    assert computed == pytest.approx(value, abs=tolerance), (
        f"published {value:.4%}, computed {computed:.4%}"
    )
