"""Radiografía de cartera: guided flow (portfolio -> summary -> details by section).

Presentation only (CLAUDE.md): every number comes from `radiografia.service`; every text from
`radiografia.reporting`. Nothing is stored: the portfolio lives in this session's memory.

Visual world: a topographic map sheet (docs/DISENO.md). Colours and fonts in
.streamlit/config.toml, the rest of the sheet in app/style.css.

Run: .venv\\Scripts\\streamlit run app\\streamlit_app.py
"""

from __future__ import annotations

import html
import math
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from radiografia import service
from radiografia.analytics.costs import CostLine
from radiografia.analytics.risk import EPISODE_DRAWDOWNS, EpisodeDrawdown, ProfilePoint
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
    REST_NAME,
    country_name,
    currency_name,
    sector_name,
    with_reference,
)
from radiografia.reporting.summary import Topic

MODE_EXAMPLE = "Ejemplo"
MODE_CSV = "Subir CSV"
MODE_FORM = "Escribir a mano"
CHART_CONFIG = {"displayModeBar": False, "staticPlot": False}

# map-sheet inks (same values as .streamlit/config.toml and app/style.css)
INK, INK_2, RULE, MARGIN = "#1C1F22", "#565B60", "#D9D5CC", "#F1EFEA"
PORTFOLIO, REFERENCE = "#B5542A", "#2A6FB0"  # contour sienna = yours, water blue = world market
PORTFOLIO_LABEL, REFERENCE_LABEL = "Tu cartera", "Mercado mundial"

TOPIC_ICONS = {
    Topic.COVERAGE: "hide_source",
    Topic.ASSET_MIX: "donut_large",
    Topic.COSTS: "euro",
    Topic.GEOGRAPHY: "public",
    Topic.CURRENCY: "currency_exchange",
    Topic.CONCENTRATION: "filter_center_focus",
    Topic.OVERLAP: "join_inner",
    Topic.RISK: "south_east",
    Topic.MARKET: "swap_vert",
}

st.set_page_config(page_title="Radiografía de cartera", page_icon="🩻", layout="centered")


# --- the sheet ---------------------------------------------------------------------------------


def source() -> service.Dataset:
    """Data of this session: the one picked in the selector, else the app's default."""
    options = service.selectable_datasets()
    chosen = st.session_state.get("data_source")
    return next((d for d in options if d.key == chosen), options[0])


def labels() -> texts.DatasetTexts:
    """Texts about the data in use (local, the user's files, SEC or the synthetic demo)."""
    return texts.DATASET_TEXTS[source().key]


def contour_svg(width: int = 560, height: int = 280, rings: int = 12) -> str:
    """Nested contour lines (every fifth one thicker, as on a topographic sheet). Decorative.

    A standalone SVG used as a CSS background image: st.html strips inline <svg>.
    """

    def point(radius: float, angle: float, k: int) -> tuple[float, float]:
        wobble = (
            0.17 * math.sin(2 * angle + 0.6 + 0.13 * k)
            + 0.08 * math.sin(3 * angle + 1.9 - 0.21 * k)
            + 0.05 * math.sin(5 * angle + 0.4 * k)
        )
        r = radius * (1 + wobble)
        return 0.64 * width + 1.35 * r * math.cos(angle), 0.6 * height + 0.8 * r * math.sin(angle)

    paths = []
    for k in range(rings):
        pts = [point(14 + 16 * k, 2 * math.pi * i / 48, k) for i in range(48)]
        n = len(pts)
        d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
        for i in range(n):  # closed Catmull-Rom spline as cubic Béziers
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
        length = sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)) * 1.02
        index_line = k % 5 == 4
        paths.append(
            f'<path d="{" ".join(d)}" fill="none" '
            f'stroke="{PORTFOLIO if index_line else "#E3C3AE"}" '
            f'stroke-width="{1.4 if index_line else 0.8}" '
            f'opacity="{0.55 if index_line else 0.9}" '
            f'style="--len:{length:.0f};--delay:{0.05 * k:.2f}s"/>'
        )
    motion = (
        "@media (prefers-reduced-motion: no-preference) {"
        "path { stroke-dasharray: var(--len); stroke-dashoffset: var(--len);"
        " animation: survey 1.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;"
        " animation-delay: var(--delay); }"
        " @keyframes survey { to { stroke-dashoffset: 0; } } }"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f"<style>{motion}</style>{''.join(paths)}</svg>"
    )


def masthead() -> None:
    css = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")
    contours = quote(contour_svg())
    contour_rule = (
        f'.sheet-head::before {{ background-image: url("data:image/svg+xml,{contours}"); }}'
    )
    st.html(f"<style>{css}\n{contour_rule}</style>")
    stamp = f'<p class="demo-stamp">{html.escape(texts.DEMO_STAMP)}</p>' if source().is_demo else ""
    st.html(
        f"""<header class="sheet-head">
        <div class="title"><h1>Radiografía<br>de cartera</h1>
        <p class="tagline">{html.escape(texts.APP_TAGLINE)}</p>{stamp}</div></header>"""
    )
    with st.container(key="disclaimer"):
        st.info(labels().disclaimer)


def survey_bar(covered: float) -> str:
    """Analysed part in solid ink, the rest hatched (unmapped land on a topographic sheet)."""
    done = max(0.0, min(1.0, covered)) * 100
    return (
        f'<div class="survey" role="img" aria-label="{format_percent(covered, 1)} analizado">'
        f'<div class="done" style="width:{done:.2f}%"></div><div class="gap"></div></div>'
    )


def cartouche(report: service.AnalysisReport) -> None:
    """Title block of the analysed sheet: what, how much, from which data, how much is covered."""
    portfolio = report.portfolio
    n = len(portfolio.positions)
    covered = portfolio.covered_weight
    holdings_date = report.lookthrough.geography.data_as_of
    prices_end = report.risk.volatility.window_end or report.returns.annualised_return.window_end
    coverage = f"{format_percent(covered, 1)} de la cartera"
    if covered < 1 - 1e-12:
        coverage += f"; {format_eur(portfolio.not_covered_weight * portfolio.total_eur)} sin datos"
    rows = [("Analizado", survey_bar(covered) + f'<span class="survey-note">{coverage}</span>')]
    if holdings_date:
        rows.append(("Posiciones a", format_date(holdings_date)))
    if prices_end:
        rows.append(("Precios hasta", format_date(prices_end)))
    rows += [
        ("Referencia", texts.DATASET_TEXTS[report.dataset].reference),
        ("Fuentes", texts.DATASET_TEXTS[report.dataset].sources),
    ]
    items = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    st.html(
        f"""<section class="cartouche" aria-label="Datos de la cartera analizada">
        <div class="inner"><div class="scale"><strong>{format_eur(portfolio.total_eur, 0)}</strong>
        <span>en {n} {"posición" if n == 1 else "posiciones"}</span></div>
        <dl>{items}</dl></div></section>"""
    )


def chart_layout(figure: go.Figure, height: int, **layout) -> go.Figure:
    figure.update_layout(
        height=height,
        font={"family": "Barlow, sans-serif", "color": INK, "size": 14},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": INK, "font": {"family": "Barlow"}},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "title": None},
        **layout,
    )
    return figure


# --- input ------------------------------------------------------------------------------------


def choose_data() -> service.Dataset:
    options = service.selectable_datasets()
    st.radio(
        texts.DATA_CHOICE_LABEL,
        [d.key for d in options],
        format_func=lambda key: texts.DATASET_TEXTS[key].choice,
        horizontal=True,
        key="data_source",
        help=texts.DATA_CHOICE_HELP,
    )
    return source()


def read_input() -> PortfolioInputResult | None:
    st.header("1. Tu cartera")
    data = choose_data()
    universe = service.get_universe(data)
    mode = st.radio(
        "¿Cómo quieres introducir tu cartera?",
        [MODE_EXAMPLE, MODE_CSV, MODE_FORM],
        horizontal=True,
        key="mode",
    )
    st.caption(im.AMOUNT_FIELD_HELP)
    if data.is_demo and mode != MODE_EXAMPLE:
        st.caption(texts.DEMO_INPUT_HINT)

    if mode == MODE_EXAMPLE:
        titles = {example.title: example for example in service.examples(data)}
        choice = st.selectbox("Cartera de ejemplo", list(titles), key="example")
        example = titles[choice]
        st.caption(example.description)
        return service.read_portfolio_csv(
            service.example_portfolio_csv(example.key, data), universe
        )

    if mode == MODE_CSV:
        st.caption(im.CSV_FORMAT_HELP)
        uploaded = st.file_uploader("Fichero CSV", type=["csv", "txt"])
        return service.read_portfolio_csv(uploaded.getvalue(), universe) if uploaded else None

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
        if st.form_submit_button("Analizar", type="primary"):
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
    return service.read_portfolio_rows(rows, universe) if rows is not None else None


def _keep_uploaded_files() -> None:
    """Copy the uploaded files' bytes to the session (memory only), so a rerun keeps them."""
    files = st.session_state.get("holdings_files") or []
    st.session_state["holdings_uploads"] = [(f.name, f.getvalue()) for f in files]


def holdings_files(portfolio) -> service.UploadedData:
    """The user's own holdings files: read each, let the user confirm its ETF, report problems.

    Nothing is written to disk: the files stay in this session's memory."""
    st.subheader(texts.UPLOAD_TITLE)
    st.caption(texts.UPLOAD_HELP)
    st.file_uploader(
        "Ficheros de posiciones (iShares, Xtrackers, Amundi o SPDR)",
        type=["csv", "xls", "xlsx"],
        accept_multiple_files=True,
        key="holdings_files",
        on_change=_keep_uploaded_files,
    )
    universe = service.get_universe(source())
    funds = sorted(universe.funds.values(), key=lambda f: f.name)
    names = {f.isin: f"{short_fund_name(f.name)} · {f.isin}" for f in funds}
    assigned: dict[str, object] = {}
    for i, (filename, content) in enumerate(st.session_state.get("holdings_uploads", [])):
        upload = service.read_holdings_file(filename, content, universe)
        if not upload.ok:
            message = im.format_holdings_file_error(upload.error, upload.detail, upload.issuer)
            st.error(f"**{filename}**: {message}")
            continue
        read = texts.UPLOAD_READ.format(
            lines=format_number(len(upload.holdings), 0), date=format_date(upload.as_of)
        )
        options = list(names)
        isin = st.selectbox(
            f"**{filename}** ({read}). {texts.UPLOAD_FUND_LABEL}",
            options,
            index=options.index(upload.suggested_isin) if upload.suggested_isin else None,
            format_func=names.get,
            placeholder="Elige el ETF",
            key=f"upload_fund_{i}_{filename}",
        )
        if isin is not None:
            if isin in assigned:
                st.warning(texts.UPLOAD_DUPLICATE.format(fund=names[isin]))
            assigned[isin] = upload
    uploaded = service.snapshot_from_uploads(assigned, universe)
    for isin, problem in uploaded.problems:
        st.warning(f"**{names.get(isin, isin)}**: {im.UPLOAD_PROBLEM_MESSAGES[problem]}")
    if not st.session_state.get("holdings_uploads"):
        st.info(texts.UPLOAD_NO_FILES)
    elif portfolio is not None:
        missing = service.missing_holdings(portfolio, uploaded, universe)
        if missing:
            st.caption(
                texts.UPLOAD_MISSING.format(
                    funds=", ".join(short_fund_name(universe.funds[i].name) for i in missing)
                )
            )
    return uploaded


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
    with st.expander("¿Cómo se calcula y qué limitaciones tiene?", icon=":material/straighten:"):
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
            details.append(labels().data_date_note.format(date=format_date(first.data_as_of)))
        if extra:
            details.append(extra)
        if details:
            st.caption(" ".join(details))


def coverage_note(metric: MetricResult | BreakdownResult) -> None:
    if metric.status is MetricStatus.PARTIAL:
        st.html(survey_bar(metric.coverage.covered_weight))
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


def bar_chart(
    breakdown: BreakdownResult,
    reference: BreakdownResult | None,
    name: Callable[[str], str],
    n: int = 8,
) -> None:
    """Your share per row as a bar; the world market's share as a blue tick on the same scale."""
    ref_items = (
        reference.items
        if reference and reference.status is not MetricStatus.NOT_AVAILABLE
        else None
    )
    rows = with_reference(breakdown.items, ref_items, n)[::-1]  # plotly draws bottom-up
    labels = [name(label) if label != REST_NAME else label for label, _, _ in rows]
    labels = [label[:1].upper() + label[1:] for label in labels]  # 'dólar' -> 'Dólar'
    values = [weight * 100 for _, weight, _ in rows]
    refs = [ref * 100 if ref is not None else None for _, _, ref in rows]
    hover = [
        f"{PORTFOLIO_LABEL}: {format_percent(v / 100, 1)}"
        + (f"<br>{REFERENCE_LABEL}: {format_percent(r / 100, 1)}" if r is not None else "")
        for v, r in zip(values, refs, strict=True)
    ]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            name=PORTFOLIO_LABEL,
            marker={"color": PORTFOLIO},
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )
    if ref_items is not None:
        figure.add_scatter(
            x=refs,
            y=labels,
            mode="markers",
            name=REFERENCE_LABEL,
            marker={"symbol": "line-ns", "size": 22, "line": {"width": 3, "color": REFERENCE}},
            hoverinfo="skip",
        )
    # value labels after whichever is longer, the bar or the tick, so they never overlap it
    ends = [max(v, r if r is not None else 0) for v, r in zip(values, refs, strict=True)]
    figure.add_scatter(
        x=ends,
        y=labels,
        mode="text",
        text=["\u2002" + format_percent(v / 100, 1) for v in values],  # en space: clear of the tick
        textposition="middle right",
        textfont={"family": "Barlow Semi Condensed", "size": 14, "color": INK},
        showlegend=False,
        hoverinfo="skip",
        cliponaxis=False,
    )
    top = max(ends)
    chart_layout(
        figure,
        height=70 + 34 * len(rows),
        margin={"l": 0, "r": 48, "t": 30, "b": 0},
        xaxis={"visible": False, "range": [0, top * 1.22], "fixedrange": True},
        yaxis={"automargin": True, "fixedrange": True, "tickfont": {"size": 14, "color": INK}},
        bargap=0.38,
        showlegend=ref_items is not None,
    )
    st.plotly_chart(figure, config=CHART_CONFIG, width="stretch")


def not_available(metric: MetricResult | BreakdownResult) -> bool:
    if metric.status is MetricStatus.NOT_AVAILABLE:
        with st.container(key=f"unsurveyed_{metric.key}"):
            st.info("No disponible con los datos actuales.", icon=":material/texture:")
        return True
    return False


# --- sections ---------------------------------------------------------------------------------


def show_summary(report: service.AnalysisReport) -> None:
    st.header("2. Lo esencial")
    cartouche(report)
    with st.container(key="legend"):
        for point in report.summary.points:
            st.markdown(f":material/{TOPIC_ICONS.get(point.topic, 'info')}: {point.text}")
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


def twin_sources(report: service.AnalysisReport) -> None:
    """Public dataset: which US ETF lends its SEC holdings to each of the user's ETFs."""
    proxies = report.lookthrough.proxies
    if not proxies:
        return
    with st.expander(texts.TWINS_TITLE, icon=":material/compare_arrows:", expanded=True):
        for proxy in proxies:
            match = texts.TWIN_EXACT if proxy.exact_index else texts.TWIN_SIMILAR
            line = (
                f"**{short_fund_name(proxy.fund_name)}** ({proxy.ucits_index}) → "
                f"{proxy.us_name} ({proxy.us_ticker}, {proxy.us_index}): {match}. "
                f"Datos de la SEC a {format_date(proxy.holdings_as_of)}."
            )
            if proxy.note:
                line += f" {proxy.note}"
            st.markdown(f"- {line}")


def show_exposure(report: service.AnalysisReport) -> None:
    lt, ref = report.lookthrough, report.reference
    twin_sources(report)
    for breakdown, reference, name in (
        (lt.geography, ref.geography if ref else None, country_name),
        (lt.sector, ref.sector if ref else None, sector_name),
        (lt.currency, ref.currency if ref else None, currency_name),
    ):
        text = texts.METRIC_TEXTS[breakdown.key]
        st.subheader(text.title)
        st.caption(text.one_liner)
        if not_available(breakdown):
            continue
        coverage_note(breakdown)
        bar_chart(breakdown, reference, name)
        explain(
            [breakdown],
            texts.DATASET_TEXTS[report.dataset].reference_mark if reference else None,
        )
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
    for name, color, values in (
        (PORTFOLIO_LABEL, PORTFOLIO, [e.portfolio for e in episodes]),
        (REFERENCE_LABEL, REFERENCE, [e.reference for e in episodes]),
    ):
        figure.add_bar(
            name=name,
            x=labels,
            y=[v * 100 if v is not None else None for v in values],
            marker={"color": color},
            text=[format_percent(v, 1) if v is not None else "" for v in values],
            textposition="outside",
            textfont={"family": "Barlow Semi Condensed", "size": 15},
            cliponaxis=False,
            hoverinfo="skip",
        )
    deepest = min(min(e.portfolio, e.reference or 0) for e in episodes) * 100
    chart_layout(
        figure,
        height=310,
        barmode="group",
        bargap=0.3,
        bargroupgap=0.08,
        margin={"l": 0, "r": 0, "t": 30, "b": 10},
        xaxis={"side": "top", "fixedrange": True, "tickfont": {"size": 14, "color": INK}},
        yaxis={"visible": False, "range": [deepest * 1.3, 0], "fixedrange": True},
    )
    figure.update_layout(legend={"y": -0.04, "yanchor": "top"})
    st.plotly_chart(figure, config=CHART_CONFIG, width="stretch")


def profile_chart(profile: tuple[ProfilePoint, ...], episodes: list[EpisodeDrawdown]) -> None:
    """Elevation-profile style: how far below its previous peak each line was, week by week."""
    days = [p.day for p in profile]
    mine = [p.portfolio * 100 for p in profile]
    world = [p.reference * 100 if p.reference is not None else None for p in profile]
    figure = go.Figure()
    for e in episodes:
        figure.add_vrect(
            x0=e.start, x1=e.end, fillcolor=MARGIN, opacity=1, layer="below", line_width=0
        )
        figure.add_annotation(
            x=e.start, y=0, yanchor="bottom", xanchor="left", text=e.key, showarrow=False,
            font={"family": "Barlow Semi Condensed", "size": 13, "color": INK_2},
        )  # fmt: skip
    if any(w is not None for w in world):
        figure.add_scatter(
            x=days,
            y=world,
            name=REFERENCE_LABEL,
            line={"color": REFERENCE, "width": 1.4},
            customdata=[format_percent(w / 100, 1) if w is not None else "" for w in world],
            hovertemplate=REFERENCE_LABEL + ": %{customdata}<extra></extra>",
        )
    figure.add_scatter(
        x=days,
        y=mine,
        name=PORTFOLIO_LABEL,
        line={"color": PORTFOLIO, "width": 1.8},
        fill="tozeroy",
        fillcolor="rgba(181, 84, 42, 0.13)",
        customdata=[format_percent(m / 100, 1) for m in mine],
        hovertemplate=PORTFOLIO_LABEL + ": %{customdata}<extra></extra>",
    )
    deepest = min([*mine, *(w for w in world if w is not None)])
    chart_layout(
        figure,
        height=300,
        hovermode="x unified",
        margin={"l": 0, "r": 0, "t": 30, "b": 0},
        xaxis={"showgrid": False, "linecolor": INK, "ticks": "outside", "tickcolor": INK},
        yaxis={
            "range": [deepest * 1.12, 3],
            "ticksuffix": " %",
            "gridcolor": RULE,
            "zeroline": True,
            "zerolinecolor": INK,
            "zerolinewidth": 1,
            "fixedrange": True,
        },
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
    if risk.profile:
        st.markdown("**Todo el periodo: cuánto estaba por debajo de su máximo cada día**")
        profile_chart(risk.profile, episodes)
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

    with st.expander("Otras medidas técnicas", icon=":material/functions:"):
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
    st.caption(texts.DATASET_TEXTS[report.dataset].disclaimer)


def main() -> None:
    masthead()
    result = read_input()
    ready = result is not None and show_input_problems(result)
    data = source()
    if data.key is service.DatasetKey.UPLOAD:
        uploaded = holdings_files(result.portfolio if ready else None)
        if ready:
            report = service.analyze(result.portfolio, snapshot=uploaded.snapshot, source=data)
    elif ready:
        report = service.analyze(result.portfolio, source=data)
    if ready:
        show_summary(report)
        show_details(report)

    with st.container(key="footer"):
        st.caption(texts.PRIVACY_NOTE)
        st.caption(labels().credits)


main()
