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
from radiografia.analytics.risk import EPISODE_DRAWDOWNS, EpisodeDrawdown
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


def method_texts(keys: list[str], warnings: list[str]) -> None:
    """Method, limitations and warnings of the given metric keys (Markdown, no container)."""
    for key in keys:
        text = texts.METRIC_TEXTS.get(key)
        if text is not None:
            st.markdown(f"**{text.title}.** {text.how_it_is_computed}")
            st.markdown("\n".join(f"- {limitation}" for limitation in text.limitations))
    if warnings:
        st.markdown("**Ten en cuenta:**")
        st.markdown("\n".join(f"- {texts.WARNING_TEXTS[w]}" for w in warnings))


def explain(
    metrics: list[MetricResult | BreakdownResult],
    extra: str | None = None,
    keys: tuple[str, ...] = (),
) -> None:
    """'How is it computed' expander: method, limitations, warnings, window and data date.

    `keys`: texts of results that are not a MetricResult (e.g. the crisis episodes), shown first.
    """
    with st.expander("¿Cómo se calcula y qué limitaciones tiene?"):
        warnings: list[str] = []
        for metric in metrics:
            warnings += [w for w in metric.warnings if w not in warnings]
        method_texts([*keys, *(metric.key for metric in metrics)], warnings)
        details = []
        first = metrics[0] if metrics else None
        start = getattr(first, "window_start", None)
        end = getattr(first, "window_end", None)
        if start and end:
            details.append(f"Periodo: {format_date(start)} a {format_date(end)}.")
        if first is not None and first.data_as_of:
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
    st.markdown(
        "\n".join(
            f"- {short_fund_name(names.get(p.isin_a, p.isin_a))} y "
            f"{short_fund_name(names.get(p.isin_b, p.isin_b))}: **{format_percent(p.overlap, 0)}** "
            "en común"
            for p in lt.overlaps
        )
    )
    shared = lt.shared_companies_weight
    if shared.value is not None:
        st.caption(
            f"{texts.METRIC_TEXTS[shared.key].title}: {format_percent(shared.value, 0)}. "
            f"{texts.METRIC_TEXTS[shared.key].one_liner}"
        )
    explain([shared])


def episode_chart(episodes: list[EpisodeDrawdown]) -> None:
    labels = [e.label.replace(" (", "<br>(") for e in episodes]
    figure = go.Figure()
    for name, values in (
        ("Tu cartera", [e.portfolio for e in episodes]),
        ("Mercado mundial", [e.reference for e in episodes]),
    ):
        figure.add_bar(
            name=name,
            x=labels,
            y=[v * 100 if v is not None else None for v in values],
            text=[format_percent(v, 1) if v is not None else "" for v in values],
            textposition="outside",
            cliponaxis=False,
            hoverinfo="skip",
        )
    deepest = min(min(e.portfolio, e.reference or 0) for e in episodes) * 100
    figure.update_layout(
        barmode="group",
        height=300,
        margin={"l": 0, "r": 0, "t": 10, "b": 10},
        yaxis={"visible": False, "range": [deepest * 1.3, 0]},
        legend={"orientation": "h", "y": -0.25, "x": 0},
    )
    st.plotly_chart(figure, config=CHART_CONFIG, width="stretch")


def technical_line(metric: MetricResult, value_text: str, note: str | None = None) -> None:
    text = texts.METRIC_TEXTS[metric.key]
    st.markdown(f"**{text.title}: {value_text}.** {text.one_liner}")
    if note:
        st.caption(note)


def show_risk(report: service.AnalysisReport) -> None:
    risk = report.risk
    if not_available(risk.volatility):
        return

    title = texts.METRIC_TEXTS[EPISODE_DRAWDOWNS]
    st.subheader(title.title)
    st.caption(title.one_liner)
    episodes = [e for e in risk.episodes if e.portfolio is not None]
    if episodes:
        episode_chart(episodes)
    else:
        st.info(
            "Alguno de tus ETFs no existía en 2020 ni en 2022: no hay ningún episodio completo "
            "que comparar."
        )
    coverage_note(risk.volatility)
    explain([], keys=(EPISODE_DRAWDOWNS,))

    st.subheader("Cuánto se mueve")
    left, right = st.columns(2)
    metric_card(left, risk.volatility, format_percent(risk.volatility.value, 1))
    if risk.beta.value is not None:
        metric_card(right, risk.beta, format_number(risk.beta.value, 2))
    extra = f"Índice de referencia: {risk.benchmark_name}." if risk.benchmark_name else None
    if risk.r_squared is not None:
        extra = (extra or "") + f" R²: {format_number(risk.r_squared, 2)}."
    explain([risk.volatility, risk.beta], extra)

    annualised = report.returns.annualised_return
    if annualised.value is not None:
        st.subheader("Contexto: rentabilidad pasada")
        metric_card(st, annualised, format_percent(annualised.value, 1))
        explain([annualised])

    with st.expander("Otras medidas técnicas"):
        st.caption(
            "Se calculan, pero no forman parte del resumen: o repiten lo que ya dice la "
            "volatilidad, o su incertidumbre es tan grande que se leen mal."
        )
        if risk.drawdown and risk.max_drawdown.value is not None:
            dd = risk.drawdown
            recovered = (
                f"recuperada el {format_date(dd.recovered)}"
                if dd.recovered
                else "aún no recuperada en la fecha de los datos"
            )
            technical_line(
                risk.max_drawdown,
                format_percent(risk.max_drawdown.value, 1),
                f"Desde el {format_date(risk.max_drawdown.window_start)}: del "
                f"{format_date(dd.peak)} al {format_date(dd.trough)}; {recovered}.",
            )
        if risk.var_95_1d.value is not None:
            technical_line(
                risk.var_95_1d,
                f"{format_eur(risk.var_95_1d_eur, 0)} ({format_percent(risk.var_95_1d.value, 2)})",
            )
            technical_line(
                risk.expected_shortfall_95_1d,
                format_percent(risk.expected_shortfall_95_1d.value, 2),
            )
        if risk.alpha.value is not None and risk.alpha.interval is not None:
            interval = risk.alpha.interval
            technical_line(
                risk.alpha,
                format_percent(risk.alpha.value, 2),
                f"Rango probable (95 %): de {format_percent(interval.low, 2)} a "
                f"{format_percent(interval.high, 2)} al año.",
            )
        elif risk.alpha.warnings:
            st.markdown(f"**Alpha.** {texts.WARNING_TEXTS[risk.alpha.warnings[0]]}")


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
