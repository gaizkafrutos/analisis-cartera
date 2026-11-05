"""Spanish texts for every metric, warning and the disclaimer. Single source for UI and docs.

Rules (CLAUDE.md, "Regulación y lenguaje"): describe facts about the portfolio; never recommend
buying, selling or switching, and never name alternative products.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiografia.analytics import costs

DISCLAIMER = (
    "Herramienta informativa. No es asesoramiento de inversión ni una recomendación de comprar, "
    "vender o mantener ningún producto. Los datos proceden de fuentes públicas y pueden contener "
    "errores o estar desactualizados."
)


APP_TAGLINE = "Qué tienes realmente en tu cartera de ETFs, explicado sin jerga."
PRIVACY_NOTE = (
    "Tu cartera no se guarda: se procesa en memoria mientras tienes la página abierta y no se "
    "envía a ningún servicio externo."
)
PARTIAL_COVERAGE_NOTE = (
    "Calculado sobre el {covered} de tu cartera. {missing} corresponden a posiciones sin datos."
)
NOT_AVAILABLE_NOTE = "Ninguna posición de tu cartera está en el universo analizado."
DATA_DATE_NOTE = "Datos de la gestora consultados el {date}."
HEDGED_LABEL = "cubierto en divisa"


@dataclass(frozen=True)
class MetricText:
    title: str
    one_liner: str
    """One line for someone with no financial background."""
    how_it_is_computed: str
    limitations: tuple[str, ...]


METRIC_TEXTS: dict[str, MetricText] = {
    costs.WEIGHTED_TER: MetricText(
        title="Comisión media (TER ponderado)",
        one_liner=(
            "Lo que cobran de media tus ETFs cada año por gestionarse, en porcentaje de lo que "
            "tienes invertido. No te llega factura: se descuenta del valor del fondo."
        ),
        how_it_is_computed=(
            "Media de los TER de cada ETF ponderada por el peso de cada posición. TER publicado "
            "por la gestora en la fecha indicada."
        ),
        limitations=(
            "Solo incluye los ETFs del universo analizado; el resto se indica como no cubierto.",
            "El TER puede cambiar; se muestra la fecha del dato.",
        ),
    ),
    costs.ANNUAL_COST: MetricText(
        title="Coste anual estimado",
        one_liner="Cuántos euros al año supone esa comisión con el valor actual de tu cartera.",
        how_it_is_computed=(
            "Suma, para cada ETF, de su importe actual por su TER. Si el valor de la cartera "
            "cambia, el coste en euros cambia en la misma proporción."
        ),
        limitations=(
            "No es una proyección: no supone ninguna rentabilidad futura.",
            "Es el coste de hoy sobre el valor de hoy.",
        ),
    ),
}

WARNING_TEXTS: dict[str, str] = {
    costs.WARNING_TER_IS_NOT_TOTAL_COST: (
        "El TER no es el coste total: no incluye los costes de compraventa dentro del fondo, la "
        "horquilla de precios en bolsa ni las comisiones de tu bróker o de cambio de divisa."
    ),
    costs.WARNING_HEDGING_COST_NOT_IN_TER: (
        "Tienes clases con cobertura de divisa: la cobertura tiene además un coste o beneficio "
        "implícito, según la diferencia de tipos de interés entre divisas, que el TER no recoge."
    ),
    costs.WARNING_PARTIAL_COVERAGE: (
        "Parte de tu cartera no está en el universo analizado: la comisión media se calcula solo "
        "sobre la parte cubierta y el coste en euros no incluye esas posiciones."
    ),
}
