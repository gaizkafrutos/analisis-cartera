"""Xtrackers, Amundi and SPDR readers on real files downloaded by hand (data/raw/muestras/,
git-ignored), against the iShares ETF of the same index in the local snapshot.

What is checked (docs/VALIDACION.md, "Otras gestoras"):
- every file is read: holdings date, fund, weights adding up to about 100 %;
- every country and sector maps to the engine's labels (nothing left in Spanish);
- the same index from two issuers is recognised as the same companies: the share of the other
  issuer's equity weight matched to an iShares company, and the overlap between both funds as
  the app computes it.
Thresholds are what the matching achieves today minus a margin; lower results are reported, the
thresholds are not lowered to make them pass (CLAUDE.md, "Reglas de datos").
"""

from pathlib import Path

import pandas as pd
import pytest

from radiografia import service
from radiografia.analytics.company_names import company_keys
from radiografia.analytics.fund_breakdown import holding_weights, is_cash_like
from radiografia.data.datasets import REAL, UPLOAD
from radiografia.data.snapshots import Snapshot
from radiografia.data.sources.labels import _COUNTRIES, _SECTORS

pytestmark = pytest.mark.validation

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "raw" / "muestras"
# (file pattern, fund ISIN, iShares fund of the same index, min matched share, min overlap)
CASES = [
    ("Constituent_IE00BJ0KDQ92*.xlsx", "IE00BJ0KDQ92", "IE00B4L5Y983", 0.99, 0.95),
    ("Cartera del fondo_*IE000BI8OT95*.xlsx", "IE000BI8OT95", "IE00B4L5Y983", 0.94, 0.93),
    ("holdings-daily-emea-en-spyy-gy*.xlsx", "IE00B44Z5B48", "IE00B6R52259", 0.94, 0.90),
]
ENGINE_COUNTRIES = set(_COUNTRIES.values())
ENGINE_SECTORS = {s for s in _SECTORS.values() if s} | {"Communication"}


def _sample(pattern):
    files = sorted(SAMPLES.glob(pattern))
    if not files:
        pytest.skip(f"no local sample {pattern} in data/raw/muestras/")
    return files[-1]


@pytest.fixture(scope="module")
def stored():
    snapshot = service.get_snapshot(REAL)
    if snapshot is None:
        pytest.skip("no local iShares snapshot")
    return snapshot


def _equity(lines: pd.DataFrame, issuer: str) -> pd.DataFrame:
    lines = lines.assign(w=holding_weights(lines), issuer=issuer)
    return lines[~is_cash_like(lines)]


@pytest.mark.parametrize(("pattern", "isin", "ishares", "matched", "overlap"), CASES)
def test_sample_is_read_and_matches_ishares(stored, pattern, isin, ishares, matched, overlap):
    path = _sample(pattern)
    upload = service.read_holdings_file(path.name, path.read_bytes())
    assert upload.ok, upload.detail
    assert upload.suggested_isin == isin
    h = upload.holdings
    assert h["weight_published"].sum() == pytest.approx(1.0, abs=0.01)
    known = set(stored.holdings["location"].dropna()) | ENGINE_COUNTRIES | {"-"}
    countries = set(h.loc[h["asset_class"] == "Equity", "location"].dropna())
    assert countries <= known, countries - known
    assert set(h["sector"].dropna()) <= ENGINE_SECTORS

    # share of the other issuer's equity weight recognised as an iShares company
    ishares_lines = stored.holdings[stored.holdings["isin"] == ishares]
    both = pd.concat(
        [_equity(ishares_lines, "iShares"), _equity(h, upload.issuer)], ignore_index=True
    )
    both["key"] = company_keys(both)
    ishares_keys = set(both.loc[both["issuer"] == "iShares", "key"])
    other = both[both["issuer"] == upload.issuer]
    share = other.loc[other["key"].isin(ishares_keys), "w"].sum() / other["w"].sum()

    # overlap between both funds, as the app computes it
    uploaded = service.snapshot_from_uploads({isin: upload}).snapshot
    snapshot = Snapshot(
        directory=None,
        holdings=pd.concat([ishares_lines, uploaded.holdings], ignore_index=True),
        breakdowns=uploaded.breakdowns,
        manifest=pd.concat(
            [stored.manifest[stored.manifest["isin"] == ishares], uploaded.manifest]
        ),
    )
    csv = f"identificador;importe_eur\n{ishares};5000\n{isin};5000\n"
    portfolio = service.read_portfolio_csv(csv, service.get_universe(UPLOAD)).portfolio
    pair = service.analyze(portfolio, snapshot=snapshot, source=UPLOAD).lookthrough.overlaps[0]

    print(f"{isin}: matched {share:.4f} of its weight, overlap with {ishares} {pair.overlap:.4f}")
    assert share >= matched, f"matched {share:.3f} below {matched}"
    assert pair.overlap >= overlap, f"overlap {pair.overlap:.3f} below {overlap}"
