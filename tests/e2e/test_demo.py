"""The synthetic demo (data/demo/, committed): every section end to end, also in CI.

The demo data are invented by scripts/build_demo.py, so these tests can check the whole engine
(look-through, risk, summary) without the real snapshot. The assertions are the relationships each
example is built to show, plus the rules of the demo itself: it never mixes with real funds and
it says on every screen that the data are fictitious.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from radiografia import service
from radiografia.data import datasets
from radiografia.data.datasets import DATASET_ENV, DEMO, REAL, DatasetKey
from radiografia.data.snapshots import HOLDINGS_FILE, NAVS_FILE
from radiografia.domain.metrics import MetricStatus
from radiografia.reporting.texts import DEMO_NOTICE, DEMO_STAMP, VERSUS_TITLE

ROOT = Path(__file__).resolve().parents[2]
DEMO_APP = str(ROOT / "app" / "demo.py")


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv(DATASET_ENV, "demo")


def _report(key):
    csv = service.example_portfolio_csv(key)
    return service.analyze(service.read_portfolio_csv(csv).portfolio)


def _weights(breakdown):
    return {item.label: item.weight for item in breakdown.items}


def test_dataset_selection(monkeypatch, tmp_path):
    monkeypatch.delenv(DATASET_ENV, raising=False)
    # without the variable: real data if there is a local snapshot, the demo if not
    monkeypatch.setattr(datasets, "latest_snapshot_dir", lambda root: tmp_path)
    assert datasets.current_dataset() is REAL
    assert datasets.selectable(REAL) == (REAL, DEMO, datasets.UPLOAD)
    monkeypatch.setattr(datasets, "latest_snapshot_dir", lambda root: None)
    assert datasets.current_dataset() is DEMO
    assert datasets.selectable(DEMO) == (DEMO, datasets.UPLOAD)  # no SEC mode on the public URL
    assert datasets.selectable(datasets.PUBLIC)[0] is datasets.PUBLIC
    monkeypatch.setenv(DATASET_ENV, " Demo ")
    assert datasets.current_dataset() is DEMO
    monkeypatch.setenv(DATASET_ENV, "otra")
    with pytest.raises(ValueError, match="RADIOGRAFIA_DATA"):
        datasets.current_dataset()


def test_demo_funds_never_collide_with_real_ones(demo):
    demo_isins = set(service.get_universe().funds)
    assert all(isin.startswith("ZZDEMO") for isin in demo_isins)
    assert DEMO.benchmark_isin in demo_isins
    real = service._universe(DatasetKey.REAL)
    assert not demo_isins & set(real.funds)
    assert REAL.benchmark_isin in real.funds


@pytest.mark.parametrize("key", [example.key for example in service.DEMO_EXAMPLES])
def test_every_section_is_available(demo, key):
    report = _report(key)
    assert report.dataset is DatasetKey.DEMO
    assert report.portfolio.covered_weight == pytest.approx(1.0)
    assert report.lookthrough.geography.status is not MetricStatus.NOT_AVAILABLE
    assert report.lookthrough.top_companies
    assert report.reference is not None
    assert report.risk.volatility.value is not None
    assert report.risk.beta.value is not None
    assert len(report.risk.episodes) == 2
    assert all(e.portfolio is not None and e.reference is not None for e in report.risk.episodes)
    assert report.risk.profile
    assert report.costs.tracking_difference.value is not None


def test_examples_show_what_they_are_built_for(demo):
    concentrated = _report("concentrada")
    assert _weights(concentrated.lookthrough.geography)["United States"] > 0.99
    episodes = {e.key: e for e in concentrated.risk.episodes}
    assert episodes["2022"].portfolio < episodes["2022"].reference - 0.05  # deeper fall
    assert concentrated.risk.beta.value > 1

    overlapping = _report("solapada")
    assert max(pair.overlap for pair in overlapping.lookthrough.overlaps) > 0.5

    diversified = _report("global")
    assert diversified.risk.beta.value < 1
    assert diversified.risk.alpha.value is None  # equity under 80 % of the covered part


def test_summary_says_the_data_are_fictitious(demo):
    summary = _report("concentrada").summary
    assert DEMO_NOTICE in summary.disclaimer
    text = " ".join(point.text for point in summary.points)
    assert "mercado mundial ficticio" in text
    assert "MSCI" not in text and "iShares" not in text
    assert "Liquidez" not in text  # the runner-up country is never the cash bucket


def test_crises_are_named_as_fictitious(demo):
    report = _report("concentrada")
    labels = [episode.label for episode in report.risk.episodes]
    assert labels == ["2020 (caída ficticia)", "2022 (caída ficticia)"]
    text = " ".join(point.text for point in report.summary.points)
    assert "caída ficticia" in text
    assert "covid" not in text and "inflación" not in text


def test_committed_files_match_the_generator(tmp_path):
    """data/demo/ is exactly what scripts/build_demo.py produces (nobody edits it by hand)."""
    spec = importlib.util.spec_from_file_location("build_demo", ROOT / "scripts" / "build_demo.py")
    build_demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_demo)
    build_demo.build(tmp_path)
    committed = ROOT / "data" / "demo"
    for name in ("universe.csv", "listings.csv"):
        rebuilt = (tmp_path / "reference" / name).read_text(encoding="utf-8")
        assert rebuilt == (committed / "reference" / name).read_text(encoding="utf-8")
    snapshot = build_demo.END.isoformat()
    for name in (HOLDINGS_FILE, NAVS_FILE, "performance.csv", "estr.csv", "manifest.csv"):
        rebuilt = pd.read_csv(tmp_path / "snapshots" / snapshot / name)
        stored = pd.read_csv(committed / "snapshots" / snapshot / name)
        # floating point can differ in the last digit between platforms, nothing more
        pd.testing.assert_frame_equal(rebuilt, stored, check_exact=False, rtol=1e-6)


def test_demo_app_runs_and_is_stamped():
    app = AppTest.from_file(DEMO_APP, default_timeout=60).run()
    try:
        assert not app.exception
        assert any(DEMO_NOTICE in info.value for info in app.info)
        html_blocks = " ".join(block.body for block in app.get("html"))
        assert DEMO_STAMP in html_blocks
        assert VERSUS_TITLE in html_blocks  # side by side with the (fictitious) world market
        assert not app.warning  # invented dates are never flagged as old
        captions = " ".join(caption.value for caption in app.caption)
        assert captions.count(DEMO_NOTICE) >= 2  # summary and details
        assert "sintéticos" in captions  # footer credits, no third-party data named
        metrics = {metric.label: metric.value for metric in app.metric}
        assert metrics["Coste anual estimado"] == "16,70 € / año"
    finally:
        # app/demo.py sets the variable for the whole process: leave the real data as default
        import os

        os.environ.pop(DATASET_ENV, None)
