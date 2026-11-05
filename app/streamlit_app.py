"""Radiografía de cartera: minimal screen (step 5). Portfolio input -> costs.

Presentation only (CLAUDE.md): every number comes from `radiografia.service`; every text from
`radiografia.reporting`. Nothing is stored: the portfolio lives in this session's memory.

Run: .venv\\Scripts\\streamlit run app\\streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from radiografia import service
from radiografia.analytics.costs import CostLine
from radiografia.domain.metrics import MetricResult, MetricStatus
from radiografia.domain.portfolio import CoverageStatus, PortfolioInputResult, RawPosition
from radiografia.reporting import input_messages as im
from radiografia.reporting import texts
from radiografia.reporting.formatting import (
    format_date,
    format_eur,
    format_percent,
    short_fund_name,
)

MODE_EXAMPLE = "Cartera de ejemplo"
MODE_CSV = "Subir CSV"
MODE_FORM = "Escribir a mano"

st.set_page_config(page_title="Radiografía de cartera", page_icon="🩻", layout="centered")


def read_input() -> PortfolioInputResult | None:
    st.header("1. Tu cartera")
    mode = st.radio(
        "¿Cómo quieres introducir tu cartera?",
        [MODE_EXAMPLE, MODE_CSV, MODE_FORM],
        horizontal=True,
        key="mode",
    )
    st.caption(im.AMOUNT_FIELD_HELP)

    if mode == MODE_EXAMPLE:
        st.caption("Tres ETFs de iShares: MSCI World, S&P 500 y MSCI World cubierto a euros.")
        return service.read_portfolio_csv(service.example_portfolio_csv())

    if mode == MODE_CSV:
        st.caption(im.CSV_FORMAT_HELP)
        uploaded = st.file_uploader("Fichero CSV", type=["csv", "txt"])
        return service.read_portfolio_csv(uploaded.getvalue()) if uploaded else None

    with st.form("portfolio_form"):
        edited = st.data_editor(
            pd.DataFrame({"identificador": [""] * 3, "importe": [None] * 3}),
            num_rows="dynamic",
            width="stretch",
            column_config={
                "identificador": st.column_config.TextColumn(
                    "ISIN o ticker", help=im.IDENTIFIER_FIELD_HELP
                ),
                "importe": st.column_config.NumberColumn(
                    im.AMOUNT_FIELD_LABEL, help=im.AMOUNT_FIELD_HELP, min_value=0.0, format="%.2f"
                ),
            },
        )
        if st.form_submit_button("Analizar"):
            st.session_state["form_rows"] = [
                RawPosition(
                    identifier=str(row.identificador or ""),
                    amount_eur=float(row.importe) if pd.notna(row.importe) else float("nan"),
                    row=index + 1,
                )
                for index, row in enumerate(edited.itertuples())
                if str(row.identificador or "").strip() or pd.notna(row.importe)
            ]
    rows = st.session_state.get("form_rows")
    return service.read_portfolio_rows(rows) if rows is not None else None


def show_input_problems(result: PortfolioInputResult) -> bool:
    """Show errors (blocking) and not-covered positions. Returns True if analysis can run."""
    if not result.ok:
        st.error(
            "No se puede analizar la cartera hasta corregir esto:\n\n"
            + "\n".join(f"- {im.format_input_error(error)}" for error in result.errors)
        )
        return False
    not_covered = [
        p for p in result.portfolio.positions if p.coverage is CoverageStatus.NOT_COVERED
    ]
    if not_covered:
        st.warning(
            "Algunas posiciones no se pueden analizar:\n\n"
            + "\n".join(
                f"- **{' / '.join(p.identifiers)}** ({format_percent(p.weight)} de la cartera): "
                f"{im.NOT_COVERED_MESSAGES[p.not_covered_reason]}"
                for p in not_covered
            )
        )
    return True


def show_metric(column, metric: MetricResult, value_text: str) -> None:
    text = texts.METRIC_TEXTS[metric.key]
    column.metric(text.title, value_text)
    column.caption(text.one_liner)


def cost_line_text(line: CostLine) -> str:
    """One markdown bullet per position: a list wraps on a phone, a wide table does not."""
    name = short_fund_name(line.label)
    if line.currency_hedged:
        name += f" · {texts.HEDGED_LABEL}"
    weight = format_percent(line.weight, decimals=0)
    if line.ter is None:
        return f"- **{name}** · {weight} de la cartera · sin dato de TER"
    return (
        f"- **{name}** · {weight} de la cartera · TER {format_percent(line.ter)} → "
        f"**{format_eur(line.annual_cost_eur)}/año** "
        f"({format_percent(line.share_of_cost, decimals=0)} del coste)"
    )


def show_costs(report: service.AnalysisReport) -> None:
    st.header("2. Costes")
    costs = report.costs
    ter, annual = costs.weighted_ter, costs.annual_cost

    if ter.status is MetricStatus.NOT_AVAILABLE:
        st.info(texts.NOT_AVAILABLE_NOTE)
        return

    left, right = st.columns(2)
    show_metric(left, ter, format_percent(ter.value, decimals=3))
    show_metric(right, annual, f"{format_eur(annual.value)} / año")

    if ter.status is MetricStatus.PARTIAL:
        st.warning(
            texts.PARTIAL_COVERAGE_NOTE.format(
                covered=format_percent(ter.coverage.covered_weight, decimals=1),
                missing=format_eur(ter.coverage.not_covered_amount_eur),
            )
        )

    st.markdown("**Por posición** (de mayor a menor coste)")
    st.markdown("\n".join(cost_line_text(line) for line in costs.lines))

    with st.expander("¿Cómo se calcula y qué limitaciones tiene?"):
        for metric in (ter, annual):
            text = texts.METRIC_TEXTS[metric.key]
            st.markdown(f"**{text.title}.** {text.how_it_is_computed}")
            st.markdown("\n".join(f"- {limitation}" for limitation in text.limitations))
        st.markdown("**Ten en cuenta:**")
        st.markdown("\n".join(f"- {texts.WARNING_TEXTS[w]}" for w in ter.warnings))
        st.caption(texts.DATA_DATE_NOTE.format(date=format_date(ter.data_as_of)))

    st.caption(texts.DISCLAIMER)


def main() -> None:
    st.title("Radiografía de cartera")
    st.write(texts.APP_TAGLINE)
    st.info(texts.DISCLAIMER)

    result = read_input()
    if result is not None and show_input_problems(result):
        show_costs(service.analyze(result.portfolio))

    st.divider()
    st.caption(texts.PRIVACY_NOTE)


main()
