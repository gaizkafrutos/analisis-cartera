"""Our sector/country breakdown of each fund vs the breakdown iShares publishes.

Needs a local snapshot (scripts/build_holdings.py); skipped otherwise. Run with
`pytest -m validation`.

Tolerance: 0.01 percentage points per category. iShares publishes weights rounded to 0.01 %, so
each published figure carries up to 0.005 pp of rounding; 0.01 pp is twice that.

Known discrepancies are listed with their cause and marked xfail(strict=True): if one starts to
match, the test fails and the explanation must be revisited. The tolerance is never widened to
make a case pass (CLAUDE.md). Comparisons where the published breakdown has a different date
from the holdings are skipped, because they would compare different portfolios.
"""

import pytest

from radiografia.analytics.fund_breakdown import compare_with_published, fund_breakdown
from radiografia.data.snapshots import latest_snapshot_dir, read_snapshot
from radiografia.data.universe import load_universe

pytestmark = pytest.mark.validation

TOLERANCE = 0.0001  # 0.01 percentage points, as a fraction
SECTIONS = {"Sector": "sector", "Geography/Locations": "location"}

KNOWN_DISCREPANCIES = {
    ("IE00B3WJKG14", "Sector"): (
        "the issuer breaks this sector ETF down by GICS industry (Semiconductors, Software...) "
        "while the holdings file only carries the sector"
    ),
    ("IE00B441G979", "Sector"): (
        "hedged share class: the issuer's breakdown sums to 99.40 %; about 0.6 % of the fund is "
        "neither in the breakdown nor in the holdings file, so our weights are 0.6 % larger"
    ),
    ("IE00B441G979", "Geography/Locations"): "same cause as the hedged class sector breakdown",
    ("IE00BDBRDM35", "Sector"): "the issuer does not count its in-house money-market fund as cash",
}


@pytest.fixture(scope="module")
def snapshot():
    directory = latest_snapshot_dir()
    if directory is None:
        pytest.skip("no local snapshot: run scripts/build_holdings.py")
    return read_snapshot(directory)


def _cases():
    universe = load_universe()
    # iShares only: the other issuers' published breakdowns are not in the local snapshot
    for isin in sorted(i for i, f in universe.funds.items() if f.issuer == "iShares"):
        for section in SECTIONS:
            marks = []
            if (isin, section) in KNOWN_DISCREPANCIES:
                reason = KNOWN_DISCREPANCIES[(isin, section)]
                marks = [pytest.mark.xfail(strict=True, reason=reason)]
            yield pytest.param(isin, section, marks=marks, id=f"{isin}-{section.split('/')[0]}")


@pytest.mark.parametrize(("isin", "section"), list(_cases()))
def test_breakdown_matches_issuer(snapshot, isin, section):
    published = snapshot.breakdowns[
        (snapshot.breakdowns["isin"] == isin) & (snapshot.breakdowns["section"] == section)
    ]
    if published.empty:
        pytest.skip(f"issuer publishes no {section} breakdown for this fund")
    holdings_as_of = snapshot.manifest.set_index("isin").loc[isin, "holdings_as_of"]
    published_as_of = published["as_of"].iloc[0]
    if published_as_of != holdings_as_of:
        pytest.skip(
            f"published {section} is as of {published_as_of:%Y-%m-%d}, holdings as of "
            f"{holdings_as_of:%Y-%m-%d}: not comparable"
        )
    holdings = snapshot.holdings[snapshot.holdings["isin"] == isin]
    comparison = compare_with_published(fund_breakdown(holdings, SECTIONS[section]), published)
    worst = comparison.loc[comparison["difference"].abs().idxmax()]
    assert abs(worst["difference"]) <= TOLERANCE, (
        f"{worst['label']}: published {worst['published']:.4%}, computed {worst['computed']:.4%}"
    )
