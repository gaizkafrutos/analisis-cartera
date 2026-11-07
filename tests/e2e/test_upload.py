"""The user's own holdings files ("Tus ficheros de la gestora"), end to end, synthetic files.

The file has the iShares CSV format but invented companies (tests/fixtures/SWDA_holdings.csv),
so this runs in CI. The validation test at the end checks, with the real files of a local
download, that uploading them gives exactly the analysis of the stored snapshot.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from radiografia import service
from radiografia.data.datasets import UPLOAD
from radiografia.data.snapshots import latest_snapshot_dir, read_snapshot
from radiografia.domain.metrics import MetricStatus
from radiografia.reporting import input_messages as im
from radiografia.reporting.texts import DATASET_TEXTS, UPLOAD_NO_FILES, UPLOAD_NOTICE

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "app" / "streamlit_app.py")
FIXTURE = ROOT / "tests" / "fixtures" / "SWDA_holdings.csv"
WORLD, EMERGING, EURO_GOVT = "IE00B4L5Y983", "IE00BKM4GZ66", "IE00B4WXJJ64"


def _global_portfolio():
    csv = service.example_portfolio_csv("global", UPLOAD)
    return service.read_portfolio_csv(csv, service.get_universe(UPLOAD)).portfolio


def _upload():
    return service.read_holdings_file("SWDA_holdings.csv", FIXTURE.read_bytes())


def test_uploaded_file_is_analysed_in_memory():
    upload = _upload()
    assert upload.suggested_isin == WORLD  # SWDA is a ticker of the MSCI World ETF
    uploaded = service.snapshot_from_uploads({WORLD: upload})
    assert uploaded.used == (WORLD,) and not uploaded.problems
    assert uploaded.snapshot.directory is None  # built in memory, never written

    portfolio = _global_portfolio()
    report = service.analyze(portfolio, snapshot=uploaded.snapshot, source=UPLOAD)
    lt = report.lookthrough
    assert report.dataset is UPLOAD.key
    assert lt.geography.status is MetricStatus.PARTIAL  # emerging markets has no file
    assert lt.geography.data_as_of == date(2026, 10, 30)
    countries = {item.label for item in lt.geography.items}
    assert {"United States", "Germany", "Japan", "United Kingdom"} <= countries
    assert lt.companies_count == 5
    assert report.costs.annual_cost.value is not None  # TER from the committed universe
    assert report.risk.volatility.status is MetricStatus.NOT_AVAILABLE  # no prices in this mode
    assert UPLOAD_NOTICE in report.summary.disclaimer
    assert service.missing_holdings(portfolio, uploaded) == (EMERGING,)
    # the asset mix comes from the funds' asset class, not from which ones have a file
    mix = next(p.text for p in report.summary.points if p.topic.value == "asset_mix")
    assert "un 70 % es renta variable" in mix and "un 30 % renta fija" in mix


def test_file_for_the_wrong_kind_of_fund_is_left_out():
    uploaded = service.snapshot_from_uploads({EURO_GOVT: _upload()})
    assert uploaded.snapshot is None and uploaded.used == ()
    assert uploaded.problems == ((EURO_GOVT, service.UploadProblem.ASSET_CLASS_MISMATCH),)
    unknown = service.snapshot_from_uploads({"IE00BK5BQT80": _upload()})
    assert unknown.problems == (("IE00BK5BQT80", service.UploadProblem.UNKNOWN_FUND),)
    assert set(im.UPLOAD_PROBLEM_MESSAGES) == set(service.UploadProblem)


def test_unreadable_files_are_ignored_not_guessed():
    bad = service.read_holdings_file("notas.csv", b"hola")
    uploaded = service.snapshot_from_uploads({WORLD: bad})
    assert uploaded.snapshot is None and uploaded.problems == ()


def test_funds_of_different_issuers_share_their_companies():
    """iShares, Xtrackers and Amundi files of the same (synthetic) companies, named and placed a
    little differently by each issuer: the overlap and the company count see them as one."""
    from tests.xlsx_builder import amundi_file, xtrackers_file

    xtrackers, amundi = "IE00BJ0KDQ92", "IE000BI8OT95"
    files = {
        WORLD: _upload(),
        xtrackers: service.read_holdings_file("Constituent_IE00BJ0KDQ92.xlsx", xtrackers_file()),
        amundi: service.read_holdings_file("Cartera del fondo_x.xlsx", amundi_file()),
    }
    assert files[xtrackers].suggested_isin == xtrackers
    assert files[amundi].suggested_isin == amundi
    uploaded = service.snapshot_from_uploads(files)
    assert set(uploaded.used) == {WORLD, xtrackers, amundi}
    csv = f"identificador;importe_eur\n{WORLD};5000\n{xtrackers};3000\n{amundi};2000\n"
    portfolio = service.read_portfolio_csv(csv, service.get_universe(UPLOAD)).portfolio
    lt = service.analyze(portfolio, snapshot=uploaded.snapshot, source=UPLOAD).lookthrough
    assert lt.companies_count == 5
    assert all(pair.overlap == pytest.approx(0.95, abs=0.01) for pair in lt.overlaps)
    countries = {item.label for item in lt.geography.items}
    assert "Netherlands" not in countries  # Amundi's country for Epsilon gives way to iShares'


@pytest.fixture
def app():
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.radio(key="data_source").set_value(UPLOAD.key).run()
    return app


def test_app_without_files_says_what_to_upload(app):
    assert not app.exception
    assert any(UPLOAD_NO_FILES in info.value for info in app.info)
    assert any(UPLOAD_NOTICE in info.value for info in app.info)
    captions = " ".join(caption.value for caption in app.caption)
    assert DATASET_TEXTS[UPLOAD.key].choice_help in captions
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Coste anual estimado"] == "16,50 € / año"  # costs need no holdings


def test_app_with_a_file_analyses_it_and_lists_what_is_missing(app):
    # Simulates the upload (AppTest cannot drive st.file_uploader): the app keeps the files'
    # bytes in this session key when the user uploads them
    app.session_state["holdings_uploads"] = [
        ("SWDA_holdings.csv", FIXTURE.read_bytes()),
        ("ficha.xls", b'<ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'),
    ]
    app.run()
    assert not app.exception
    assert "Excel de la ficha de iShares" in app.error[0].value
    fund = app.selectbox(key="upload_fund_0_SWDA_holdings.csv")
    assert fund.value == WORLD  # suggested from the file name, the user can change it
    captions = " ".join(caption.value for caption in app.caption)
    assert "Sin fichero" in captions and "MSCI EM IMI" in captions
    assert "posiciones a" in fund.label


@pytest.mark.validation
def test_uploading_the_real_files_gives_the_stored_analysis():
    """Same result whether the iShares CSVs come from a local download or from an upload."""
    snapshot_dir = latest_snapshot_dir()
    raw_dirs = sorted((ROOT / "data" / "raw" / "ishares").glob("*"))
    if snapshot_dir is None or not raw_dirs:
        pytest.skip("needs a local iShares download (data/raw, data/snapshots)")
    stored = read_snapshot(snapshot_dir)
    universe = service.get_universe(UPLOAD)
    product = {fund.issuer_product_id: isin for isin, fund in universe.funds.items()}
    files = {}
    for path in sorted(raw_dirs[-1].glob("*_holdings.csv")):
        isin = product[path.name.split("_")[0]]
        files[isin] = service.read_holdings_file(path.name, path.read_bytes(), universe)
    uploaded = service.snapshot_from_uploads(files, universe)
    stored_dates = {r.isin: r.holdings_as_of.date() for r in stored.manifest.itertuples()}
    if any(stored_dates.get(isin) != f.as_of for isin, f in files.items() if f.ok):
        pytest.skip("the raw download and the snapshot are from different days")

    for key in ("global", "concentrada", "solapada"):
        csv = service.example_portfolio_csv(key, UPLOAD)
        portfolio = service.read_portfolio_csv(csv, universe).portfolio
        expected = service.analyze(portfolio, universe, stored, service.DATASETS["real"])
        got = service.analyze(portfolio, universe, uploaded.snapshot, UPLOAD)
        assert got.lookthrough.geography.items == expected.lookthrough.geography.items
        assert got.lookthrough.currency.items == expected.lookthrough.currency.items
        assert got.lookthrough.sector.items == expected.lookthrough.sector.items
        assert got.lookthrough.overlaps == expected.lookthrough.overlaps
        assert got.lookthrough.top10_weight.value == expected.lookthrough.top10_weight.value
