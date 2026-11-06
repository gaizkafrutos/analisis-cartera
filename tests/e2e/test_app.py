"""The Streamlit app, run headless with AppTest (no browser, no network).

The costs part only needs the committed universe, so it is checked everywhere (also in CI). The
look-through, returns and risk sections need the local snapshot; without it they must say
"not available" instead of failing.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from radiografia import service
from radiografia.domain.portfolio import RawPosition

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=60).run()


def _metrics(app):
    return {metric.label: metric.value for metric in app.metric}


def _markdown(app):
    return "\n".join(block.value for block in app.markdown)


def test_default_global_example_shows_summary_and_sections(app):
    assert not app.exception
    # 6000 x 0.20 % + 1000 x 0.18 % + 2000 x 0.10 % + 1000 x 0.07 % = 16.50 EUR
    assert _metrics(app)["Coste anual estimado"] == "16,50 € / año"
    headers = [h.value for h in app.header]
    assert headers == ["1. Tu cartera", "2. Lo esencial", "3. En detalle"]
    assert "Tus ETFs te cuestan unos 16,50 € al año" in _markdown(app)
    assert [tab.label for tab in app.tabs] == ["Costes", "Exposición", "Concentración", "Riesgo"]


@pytest.mark.parametrize(
    ("example", "annual_cost"),
    [("Muy concentrada", "24,00 € / año"), ("Con fondos solapados", "18,10 € / año")],
)
def test_other_examples(app, example, annual_cost):
    app.selectbox(key="example").set_value(example).run()
    assert not app.exception
    assert _metrics(app)["Coste anual estimado"] == annual_cost


def test_disclaimer_and_privacy_note_are_visible(app):
    assert any("No es asesoramiento" in info.value for info in app.info)
    captions = " ".join(caption.value for caption in app.caption)
    assert "no se guarda" in captions
    assert captions.count("No es asesoramiento") >= 2  # summary and details


def test_form_with_an_isin_typo_blocks_the_analysis(app):
    app.radio(key="mode").set_value("Escribir a mano").run()
    assert not app.metric  # nothing analysed before submitting
    # Simulates pressing "Analizar" with these rows (AppTest cannot type into data_editor)
    app.session_state["form_rows"] = [
        RawPosition(identifier="IE00B4L5Y984", amount_eur=1000, row=1)
    ]
    app.run()
    assert app.error and "dígito de control" in app.error[0].value
    assert not app.metric
    assert "2. Lo esencial" not in [h.value for h in app.header]


def test_form_with_a_fund_outside_the_universe_is_partial(app):
    app.radio(key="mode").set_value("Escribir a mano").run()
    app.session_state["form_rows"] = [
        RawPosition(identifier="IWDA", amount_eur=9000, row=1),
        RawPosition(identifier="IE00BK5BQT80", amount_eur=1000, row=2),
    ]
    app.run()
    assert not app.exception
    assert _metrics(app)["Coste anual estimado"] == "18,00 € / año"
    assert "aún no está en el universo" in " ".join(w.value for w in app.warning)
    assert "Se ha analizado el 90,0 %" in _markdown(app)


def test_without_snapshot_the_app_degrades_gracefully(app, monkeypatch):
    monkeypatch.setattr(service, "get_snapshot", lambda: None)
    app.run()
    assert not app.exception
    assert _metrics(app)["Coste anual estimado"] == "16,50 € / año"
    assert any("No disponible" in info.value for info in app.info)
