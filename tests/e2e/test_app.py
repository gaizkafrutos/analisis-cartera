"""The Streamlit screen, run headless with AppTest (no browser, no network)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from radiografia.domain.portfolio import RawPosition

APP = str(Path(__file__).resolve().parents[2] / "app" / "streamlit_app.py")


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=30).run()


def _metric_values(app):
    return {metric.label: metric.value for metric in app.metric}


def test_example_portfolio_shows_costs_on_first_load(app):
    assert not app.exception
    # Same numbers as the worked example: 12 + 2.10 + 5.50 EUR on 10,000 EUR
    assert _metric_values(app) == {
        "Comisión media (TER ponderado)": "0,196 %",
        "Coste anual estimado": "19,60 € / año",
    }
    lines = next(m.value for m in app.markdown if m.value.startswith("- **Core MSCI World"))
    assert lines.splitlines() == [
        "- **Core MSCI World** · 60 % de la cartera · "
        "TER 0,20 % → **12,00 €/año** (61 % del coste)",
        "- **MSCI World EUR Hedged (Acc) · cubierto en divisa** · 10 % de la cartera · "
        "TER 0,55 % → **5,50 €/año** (28 % del coste)",
        "- **Core S&P 500** · 30 % de la cartera · TER 0,07 % → **2,10 €/año** (11 % del coste)",
    ]


def test_disclaimer_and_privacy_note_are_visible(app):
    assert any("No es asesoramiento" in info.value for info in app.info)
    assert any("no se guarda" in caption.value for caption in app.caption)


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


def test_form_with_a_fund_outside_the_universe_is_partial(app):
    app.radio(key="mode").set_value("Escribir a mano").run()
    app.session_state["form_rows"] = [
        RawPosition(identifier="IWDA", amount_eur=9000, row=1),
        RawPosition(identifier="IE00BK5BQT80", amount_eur=1000, row=2),
    ]
    app.run()
    assert not app.exception
    assert _metric_values(app)["Coste anual estimado"] == "18,00 € / año"
    warnings = " ".join(w.value for w in app.warning)
    assert "aún no está en el universo" in warnings
    assert "Calculado sobre el 90,0 %" in warnings
