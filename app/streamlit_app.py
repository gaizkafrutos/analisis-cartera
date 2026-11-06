"""Radiografía de cartera: guided flow (portfolio -> summary -> details by section).

Presentation only (CLAUDE.md): every number comes from `radiografia.service`; every text from
`radiografia.reporting`. Nothing is stored: the portfolio lives in this session's memory.

Run: .venv\\Scripts\\streamlit run app\\streamlit_app.py
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from radiografia import service
from radiografia.analytics.costs import CostLine
from radiografia.domain.metrics import BreakdownResult, MetricResult, MetricStatus
from radiografia.domain.portfolio import CoverageStatus, PortfolioInputResult, RawPosition
from radiografia.reporting import input_messages as im
from radiografia.reporting import texts
from radiografia.reporting.formatting import (
    format_date,
    format_eur,
    format_number,
    format_percent,
    short_fund_name,
)
from radiografia.reporting.presentation import (
    country_name,
    currency_name,
    sector_name,
    top_with_rest,
)

MODE_EXAMPLE = "Ejemplo"
MODE_CSV = "Subir CSV"
MODE_FORM = "Escribir a mano"
CHART_CONFIG = {"displayModeBar": False, "staticPlot": False}

st.set_page_config(page_title="Radiografía de cartera", page_icon="🩻", layout="centered")


# --- input ------------------------------------------------------------------------------------


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
        titles = {example.title: example for example in service.EXAMPLES}
        choice = st.selectbox("Cartera de ejemplo", list(titles), key="example")
        example = titles[choice]
        st.caption(example.description)
        return service.read_portfolio_csv(service.example_portfolio_csv(example.key))

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
    """Errors block the analysis; not-covered positions are listed. True if analysis can run."""
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


# --- building blocks --------------------------------------------------------------------------


def explain(metrics: list[MetricResult | BreakdownResult], extra: str | None = None) -> None:
    """'How is it computed' expander: method, limitations, warnings, window and data date."""
    with st.expander("¿Cómo se calcula y qué limitaciones tiene?"):
        warnings: list[str] = []
        for metric in metrics:
            text = texts.METRIC_TEXTS.get(metric.key)
            if text is not None:
                st.markdown(f"**{text.title}.** {text.how_it_is_computed}")
                st.markdown("\n".join(f"- {limitation}" for limitation in text.limitations))
            warnings += [w for w in metric.warnings if w not in warnings]
        if warnings:
            st.markdown("**Ten en cuenta:**")
            st.markdown("\n".join(f"- {texts.WARNING_TEXTS[w]}" for w in warnings))
        details = []
        first = metrics[0]
        start = getattr(first, "window_start", None)
        end = getattr(first, "window_end", None)
        if start and end:
            details.append(f"Periodo: {format_date(start)} a {format_date(end)}.")
        if first.data_as_of:
            details.append(texts.DATA_DATE_NOTE.format(date=format_date(first.data_as_of)))
        if extra:
            details.append(extra)
        if details:
            st.caption(" ".join(details))


def coverage_note(metric: MetricResult | BreakdownResult) -> None:
    if metric.status is MetricStatus.PARTIAL:
        st.caption(
            texts.PARTIAL_COVERAGE_NOTE.format(
                covered=format_percent(metric.coverage.covered_weight, 1),
                missing=format_eur(metric.coverage.not_covered_amount_eur),
            )
        )


def metric_card(column, metric: MetricResult, value_text: str) -> None:
    text = texts.METRIC_TEXTS[metric.key]
    column.metric(text.title, value_text)
    column.caption(text.one_liner)


def bar_chart(breakdown: BreakdownResult, name: Callable[[str], str], n: int = 8) -> None:
    rows = top_with_rest(breakdown.items, n)
    labels = [name(label) if label != "Resto" else label for label, _ in rows]
    labels = [label[:1].upper() + label[1:] for label in labels]  # 'dólar' -> 'Dólar'
    values = [weight * 100 for _, weight in rows]
    figure = go.Figure(
        go.Bar(
            x=values[::-1],
            y=labels[::-1],
            orientation="h",
            text=[format_percent(v / 100, 1) for v in values[::-1]],
            textposition="outside",
            cliponaxis=False,
            hoverinfo="skip",
        )
    )
    figure.update_layout(
        height=40 + 32 * len(rows),
        margin={"l": 0, "r": 40, "t": 10, "b": 10},
        xaxis={"visible": False, "range": [0, max(values) * 1.25]},
        yaxis={"automargin": True},
        showlegend=False,
    )
    st.plotly_chart(figure, config=CHART_CONFIG, width="stretch")


def not_available(metric: MetricResult | BreakdownResult) -> bool:
    if metric.status is MetricStatus.NOT_AVAILABLE:
        st.info("No disponible con los datos actuales.")
        return True
    return False


# --- sections ---------------------------------------------------------------------------------


def show_summary(report: service.AnalysisReport) -> None:
    st.header("2. Lo esencial")
    st.markdown("\n\n".join(f"- {point.text}" for point in report.summary.points))
    st.caption(report.summary.disclaimer)


def cost_line_text(line: CostLine) -> str:
    """One markdown bullet per position: a list wraps on a phone, a wide table does not."""
    name = short_fund_name(line.label)
    if line.currency_hedged:
        name += f" · {texts.HEDGED_LABEL}"
    weight = format_percent(line.weight, decimals=0)
    if line.ter is None:
        return f"- **{name}** · {weight} de la cartera · sin dato de TER"
    text = (
        f"- **{name}** · {weight} de la cartera · TER {format_percent(line.ter)} → "
        f"**{format_eur(line.annual_cost_eur)}/año** "
        f"({format_percent(line.share_of_cost, decimals=0)} del coste)"
    )
    if line.tracking_difference is not None:
        text += f" · diferencia con su índice {format_percent(line.tracking_difference, 2)}/año"
    return text


def show_costs(report: service.AnalysisReport) -> None:
    costs = report.costs
    if not_available(costs.weighted_ter):
        return
    left, right = st.columns(2)
    metric_card(left, costs.weighted_ter, format_percent(costs.weighted_ter.value, decimals=3))
    metric_card(right, costs.annual_cost, f"{format_eur(costs.annual_cost.value)} / año")
    coverage_note(costs.weighted_ter)
    if costs.tracking_difference.value is not None:
        metric_card(
            st,
            costs.tracking_difference,
            f"{format_percent(costs.tracking_difference.value, 2)} / año",
        )
    st.markdown("**Por posición** (de mayor a menor coste)")
    st.markdown("\n".join(cost_line_text(line) for line in costs.lines))
    explain([costs.weighted_ter, costs.annual_cost, costs.tracking_difference])


def show_exposure(report: service.AnalysisReport) -> None:
    lt = report.lookthrough
    for breakdown, name, subtitle in (
        (lt.geography, country_name, None),
        (lt.sector, sector_name, None),
        (lt.currency, currency_name, None),
    ):
        text = texts.METRIC_TEXTS[breakdown.key]
        st.subheader(text.title)
        st.caption(text.one_liner)
        if not_available(breakdown):
            continue
        coverage_note(breakdown)
        bar_chart(breakdown, name)
        explain([breakdown], subtitle)
    if lt.uncovered:
        st.markdown("**No desglosado por empresa, país ni sector**")
        st.markdown(
            "\n".join(
                f"- {short_fund_name(u.label)} ({format_percent(u.weight, 0)}): "
                f"{texts.UNCOVERED_TEXTS[u.reason]}"
                for u in lt.uncovered
            )
        )


def show_concentration(report: service.AnalysisReport) -> None:
    lt = report.lookthrough
    if not_available(lt.top10_weight):
        return
    left, right = st.columns(2)
    metric_card(left, lt.top10_weight, format_percent(lt.top10_weight.value, 0))
    metric_card(right, lt.effective_companies, format_number(lt.effective_companies.value, 0))
    st.caption(f"Número real de empresas: {format_number(lt.companies_count, 0)}.")
    st.markdown("**Las 10 empresas en las que más tienes**")
    st.markdown(
        "\n".join(
            f"{i}. {c.company.title()} · {format_percent(c.weight, 1)}"
            + (f" · en {len(c.fund_isins)} de tus ETFs" if len(c.fund_isins) > 1 else "")
            for i, c in enumerate(lt.top_companies, start=1)
        )
    )
    explain([lt.top10_weight, lt.effective_companies])

    st.subheader("Solapamiento entre tus ETFs")
    if not lt.overlaps:
        st.caption("Solo hay un ETF de renta variable: no hay nada que comparar.")
        return
    names = {line.isin: line.label for line in report.costs.lines if line.isin}
    metric_card(st, lt.shared_companies_weight, format_percent(lt.shared_companies_weight.value, 0))
    st.markdown(
        "\n".join(
            f"- {short_fund_name(names.get(p.isin_a, p.isin_a))} y "
            f"{short_fund_name(names.get(p.isin_b, p.isin_b))}: **{format_percent(p.overlap, 0)}** "
            "en común"
            for p in lt.overlaps
        )
    )
    explain([lt.shared_companies_weight])


def show_risk(report: service.AnalysisReport) -> None:
    risk = report.risk
    if not_available(risk.volatility):
        return
    left, right = st.columns(2)
    metric_card(left, risk.volatility, format_percent(risk.volatility.value, 1))
    metric_card(right, risk.max_drawdown, format_percent(risk.max_drawdown.value, 1))
    if risk.drawdown:
        dd = risk.drawdown
        recovered = (
            f"recuperada el {format_date(dd.recovered)}"
            if dd.recovered
            else "aún no recuperada en la fecha de los datos"
        )
        st.caption(
            f"Peor caída: del {format_date(dd.peak)} al {format_date(dd.trough)}; {recovered}."
        )
    explain([risk.volatility, risk.max_drawdown])

    left, right = st.columns(2)
    metric_card(
        left,
        risk.var_95_1d,
        f"{format_eur(risk.var_95_1d_eur, 0)} ({format_percent(risk.var_95_1d.value, 2)})",
    )
    metric_card(
        right, risk.expected_shortfall_95_1d, format_percent(risk.expected_shortfall_95_1d.value, 2)
    )
    explain([risk.var_95_1d, risk.expected_shortfall_95_1d])

    st.subheader("Frente al mercado mundial")
    if risk.beta.value is None:
        st.info("No disponible con los datos actuales.")
    else:
        left, right = st.columns(2)
        metric_card(left, risk.beta, format_number(risk.beta.value, 2))
        if risk.alpha.value is not None and risk.alpha.interval is not None:
            interval = risk.alpha.interval
            metric_card(right, risk.alpha, format_percent(risk.alpha.value, 2))
            right.caption(
                f"Rango probable (95 %): de {format_percent(interval.low, 2)} a "
                f"{format_percent(interval.high, 2)} al año."
            )
        else:
            right.caption(
                texts.WARNING_TEXTS[risk.alpha.warnings[0]] if risk.alpha.warnings else ""
            )
        extra = f"Índice de referencia: {risk.benchmark_name}." if risk.benchmark_name else None
        if risk.r_squared is not None:
            extra = (extra or "") + f" R²: {format_number(risk.r_squared, 2)}."
        explain([risk.beta, risk.alpha], extra)

    st.subheader("Contexto: rentabilidad pasada")
    annualised = report.returns.annualised_return
    if annualised.value is None:
        st.info("No disponible con los datos actuales.")
    else:
        metric_card(st, annualised, format_percent(annualised.value, 1))
        if report.returns.limited_by:
            st.caption(
                f"El periodo empieza cuando empezó a cotizar "
                f"{short_fund_name(report.returns.limited_by)}."
            )
        explain([annualised])


def show_details(report: service.AnalysisReport) -> None:
    st.header("3. En detalle")
    costs, exposure, concentration, risk = st.tabs(
        ["Costes", "Exposición", "Concentración", "Riesgo"]
    )
    with costs:
        show_costs(report)
    with exposure:
        show_exposure(report)
    with concentration:
        show_concentration(report)
    with risk:
        show_risk(report)
    st.caption(texts.DISCLAIMER)


def show_sources(report: service.AnalysisReport) -> None:
    holdings_date = report.lookthrough.geography.data_as_of
    window_end = report.returns.annualised_return.window_end
    parts = ["Fuentes: iShares (BlackRock) para composición, comisiones y valores liquidativos; "
             "BCE para tipos de cambio y €STR (valores convertidos a euros)."]  # fmt: skip
    if holdings_date:
        parts.append(f"Posiciones a {format_date(holdings_date)}.")
    if window_end:
        parts.append(f"Precios hasta {format_date(window_end)}.")
    st.caption(" ".join(parts))


def main() -> None:
    st.title("Radiografía de cartera")
    st.write(texts.APP_TAGLINE)
    st.info(texts.DISCLAIMER)

    result = read_input()
    if result is not None and show_input_problems(result):
        report = service.analyze(result.portfolio)
        show_summary(report)
        show_details(report)
        show_sources(report)

    st.divider()
    st.caption(texts.PRIVACY_NOTE)


main()
