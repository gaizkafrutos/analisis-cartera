"""The public dataset (data/public/, SEC N-PORT of US twin ETFs, committed): end to end in CI.

Checks the rules of the approximation: only twins of exactly the same index, every covered fund
says which twin and date it uses, sectors (not in N-PORT) are reported as not available, and the
public app shows the notice.
"""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from radiografia import service
from radiografia.analytics.lookthrough import WARNING_HOLDINGS_FROM_TWIN, UncoveredReason
from radiografia.data.datasets import DATASET_ENV, PUBLIC, DatasetKey
from radiografia.domain.metrics import MetricStatus
from radiografia.reporting.texts import PUBLIC_NOTICE, TWINS_TITLE

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_APP = str(ROOT / "app" / "public.py")
TWINS = pd.read_csv(ROOT / "data" / "reference" / "twins.csv")


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setenv(DATASET_ENV, "public")


def _report(csv):
    return service.analyze(service.read_portfolio_csv(csv).portfolio)


def test_twins_file_is_consistent():
    assert set(TWINS["match"]) <= {"exact", "similar"}
    universe = service._universe(DatasetKey.REAL)
    assert set(TWINS["ucits_isin"]) <= set(universe.funds)
    assert TWINS["ucits_isin"].is_unique
    similar = TWINS[TWINS["match"] == "similar"]
    assert similar["note"].notna().all()  # every approximation says how it differs


def test_only_exact_twins_are_used(public):
    proxies = service.get_snapshot().proxies
    assert set(proxies["match"]) == {"exact"}
    exact = set(TWINS.loc[TWINS["match"] == "exact", "ucits_isin"])
    assert set(proxies["isin"]) == exact
    assert PUBLIC.benchmark_isin in exact


def test_overlapping_example_is_fully_covered_and_labelled(public):
    report = _report(service.example_portfolio_csv("solapada"))
    lt = report.lookthrough
    assert report.dataset is DatasetKey.PUBLIC
    assert lt.geography.status is MetricStatus.AVAILABLE
    assert WARNING_HOLDINGS_FROM_TWIN in lt.geography.warnings
    assert {p.us_ticker for p in lt.proxies} == {"URTH", "IVV", "QQQ"}
    assert all(p.exact_index for p in lt.proxies)
    assert lt.geography.data_as_of == min(p.holdings_as_of for p in lt.proxies)
    assert max(pair.overlap for pair in lt.overlaps) > 0.5  # World and S&P 500
    assert lt.sector.status is MetricStatus.NOT_AVAILABLE  # N-PORT has no sectors
    assert PUBLIC_NOTICE in report.summary.disclaimer


def test_funds_without_exact_twin_are_not_covered(public):
    # S&P 500 Information Technology: its US twin tracks a different index -> not used
    report = _report("identificador;importe_eur\nIE00B5BMR087;6000\nIE00B3WJKG14;4000\n")
    lt = report.lookthrough
    assert lt.geography.status is MetricStatus.PARTIAL
    reasons = {u.label: u.reason for u in lt.uncovered}
    assert UncoveredReason.HOLDINGS_NOT_AVAILABLE in reasons.values()


def test_hedged_bond_class_counts_in_currency_without_holdings(public):
    report = _report("identificador;importe_eur\nIE00BDBRDM35;1000\n")
    currency = report.lookthrough.currency
    assert currency.status is MetricStatus.AVAILABLE
    assert currency.items[0].label == "EUR"


def test_public_app_runs_and_says_where_the_data_come_from():
    app = AppTest.from_file(PUBLIC_APP, default_timeout=60)
    try:
        app.run()
        app.selectbox(key="example").set_value("Con fondos solapados").run()
        assert not app.exception
        assert any(PUBLIC_NOTICE in info.value for info in app.info)
        assert TWINS_TITLE in [expander.label for expander in app.expander]
        captions = " ".join(caption.value for caption in app.caption)
        assert "SEC" in captions  # footer credits
        assert "iShares (BlackRock) para composición" not in captions
    finally:
        import os

        os.environ.pop(DATASET_ENV, None)
