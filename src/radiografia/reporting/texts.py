"""Spanish texts for every metric, warning and the disclaimer. Single source for UI and docs.

Rules (CLAUDE.md, "Regulación y lenguaje"): describe facts about the portfolio; never recommend
buying, selling or switching, and never name alternative products.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiografia.analytics import costs, lookthrough, returns

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
    lookthrough.GEOGRAPHY: MetricText(
        title="Exposición por país",
        one_liner=(
            "En qué países están las empresas que tienes, sumando lo que hay dentro de cada ETF."
        ),
        how_it_is_computed=(
            "Para cada país, suma de (peso del ETF en tu cartera × peso de ese país dentro del "
            "ETF), a partir de las posiciones que publica la gestora."
        ),
        limitations=(
            "El país es el que asigna la gestora a cada empresa (sobre todo su domicilio), no "
            "de dónde vienen sus ingresos.",
            "Solo incluye ETFs de renta variable con posiciones disponibles.",
        ),
    ),
    lookthrough.SECTOR: MetricText(
        title="Exposición por sector",
        one_liner="A qué sectores económicos está expuesto tu dinero, abriendo cada ETF.",
        how_it_is_computed=(
            "Para cada sector, suma de (peso del ETF × peso del sector dentro del ETF). "
            "Clasificación sectorial de la gestora (GICS)."
        ),
        limitations=("Solo incluye ETFs de renta variable con posiciones disponibles.",),
    ),
    lookthrough.CURRENCY: MetricText(
        title="Exposición por divisa",
        one_liner=(
            "Qué parte de tu cartera sube o baja con el tipo de cambio del euro, aunque compres "
            "todo en euros."
        ),
        how_it_is_computed=(
            "Suma por la divisa en que cotiza cada posición dentro de los ETFs. Las clases "
            "cubiertas cuentan en la divisa a la que se cubren."
        ),
        limitations=(
            "La divisa en que cotiza una empresa no es necesariamente la de sus ventas.",
            "Incluye renta variable y renta fija con posiciones disponibles.",
        ),
    ),
    lookthrough.TOP10_WEIGHT: MetricText(
        title="Peso de las 10 mayores empresas",
        one_liner="Qué parte de tu renta variable está en las 10 empresas en las que más tienes.",
        how_it_is_computed="Suma de los pesos de las 10 mayores empresas tras abrir los ETFs.",
        limitations=("Las clases de una misma empresa (p. ej. Alphabet A y C) se agrupan.",),
    ),
    lookthrough.EFFECTIVE_COMPANIES: MetricText(
        title="Número efectivo de empresas",
        one_liner=(
            "Con cuántas empresas a partes iguales tendrías la misma concentración. Suele ser "
            "mucho menor que el número real de empresas."
        ),
        how_it_is_computed="1 ÷ suma de los pesos al cuadrado (inverso del índice de Herfindahl).",
        limitations=("Describe concentración, no riesgo: no mide cómo se mueven las empresas.",),
    ),
    lookthrough.SHARED_COMPANIES_WEIGHT: MetricText(
        title="Peso en empresas repetidas",
        one_liner=(
            "Qué parte de tu renta variable está en empresas que aparecen en más de uno de "
            "tus ETFs."
        ),
        how_it_is_computed=(
            "Suma del peso de las empresas presentes en dos o más de tus ETFs. El solapamiento "
            "entre cada par de ETFs es la suma, empresa a empresa, del menor de sus dos pesos."
        ),
        limitations=("Lo relevante es la exposición final, no cuántas veces aparece una empresa.",),
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
    lookthrough.WARNING_HOLDINGS_ARE_A_SNAPSHOT: (
        "Las posiciones son una foto en la fecha indicada; los fondos cambian después."
    ),
    lookthrough.WARNING_COUNTRY_IS_DOMICILE: (
        "El país es el domicilio de cada empresa, no de dónde vienen sus ingresos: una empresa "
        "suiza puede ingresar casi todo fuera de Suiza."
    ),
    lookthrough.WARNING_CURRENCY_IS_TRADING_CURRENCY: (
        "Se usa la divisa en que cotiza cada posición. Una empresa europea que ingresa en dólares "
        "también depende del dólar, y eso no se refleja aquí."
    ),
    lookthrough.WARNING_HEDGED_CLASSES_ASSUMED: (
        "Las clases cubiertas cuentan al 100 % en su divisa de cobertura. Es un supuesto basado en "
        "el objetivo del fondo: sus posiciones no permiten calcular cuánto cubre exactamente."
    ),
    lookthrough.WARNING_LOOKTHROUGH_PARTIAL: (
        "Parte de tu cartera no se ha podido desglosar: los porcentajes se refieren solo a la "
        "parte analizada."
    ),
    lookthrough.WARNING_CONCENTRATION_IS_DESCRIPTIVE: (
        "La concentración describe, no juzga: los índices que ponderan por tamaño ya están "
        "concentrados en las mayores empresas."
    ),
    lookthrough.WARNING_OVERLAP_IS_NOT_A_PROBLEM_BY_ITSELF: (
        "Que una empresa aparezca en varios ETFs no es un problema por sí mismo: lo que cuenta es "
        "cuánto pesa al final en tu cartera."
    ),
}

UNCOVERED_TEXTS: dict[str, str] = {
    lookthrough.UncoveredReason.OUTSIDE_UNIVERSE: "No está en el universo analizado.",
    lookthrough.UncoveredReason.FIXED_INCOME_NOT_LOOKED_THROUGH: (
        "Renta fija: cuenta en la exposición por divisa, pero no se desglosa por empresa, país ni "
        "sector."
    ),
    lookthrough.UncoveredReason.OTHER_ASSET_CLASS: "Clase de activo que no se desglosa.",
    lookthrough.UncoveredReason.SYNTHETIC_REPLICATION: (
        "ETF sintético: sus posiciones no reflejan su exposición real, así que no se abre."
    ),
    lookthrough.UncoveredReason.HOLDINGS_NOT_AVAILABLE: (
        "No hay posiciones disponibles para este ETF."
    ),
}

METRIC_TEXTS.update(
    {
        costs.TRACKING_DIFFERENCE: MetricText(
            title="Diferencia con el índice (tracking difference)",
            one_liner=(
                "Cuánto ha rendido cada año tu ETF por encima o por debajo del índice que copia. "
                "Es el coste real que has soportado, no el anunciado."
            ),
            how_it_is_computed=(
                "Rentabilidad anual del fondo menos la de su índice, media de los últimos 5 años, "
                "según publica la gestora. Negativo: el fondo quedó por detrás del índice."
            ),
            limitations=(
                "Es un dato pasado de la gestora; puede cambiar en el futuro.",
                "No se muestra para clases cubiertas en divisa: la gestora las compara con el "
                "índice sin cubrir en otra divisa.",
            ),
        ),
        returns.ANNUALISED_RETURN: MetricText(
            title="Rentabilidad anual histórica (simulada)",
            one_liner=(
                "Lo que habría rendido cada año tu reparto actual en el periodo indicado, en "
                "euros. No es tu rentabilidad real ni una previsión."
            ),
            how_it_is_computed=(
                "Valor liquidativo diario de cada ETF con sus repartos reinvertidos, pasado a "
                "euros con los tipos del BCE, combinado con tus pesos actuales y anualizado."
            ),
            limitations=(
                "Supone que mantienes los pesos actuales todos los días del periodo.",
                "El periodo empieza cuando empezó a cotizar el ETF más reciente de tu cartera.",
                "Rentabilidades pasadas no garantizan rentabilidades futuras.",
            ),
        ),
    }
)

WARNING_TEXTS.update(
    {
        costs.WARNING_TD_IS_PAST_AND_ISSUER_DATA: (
            "Dato publicado por la gestora sobre los últimos 5 años: describe el pasado."
        ),
        costs.WARNING_TD_NOT_FOR_HEDGED: (
            "Las clases cubiertas en divisa no tienen este dato: la gestora las compara con el "
            "índice sin cubrir, así que la diferencia sería sobre todo de divisa."
        ),
        returns.WARNING_PAST_PERFORMANCE: (
            "Rentabilidades pasadas no garantizan rentabilidades futuras."
        ),
        returns.WARNING_CONSTANT_WEIGHTS: (
            "Es una simulación: aplica tus pesos de hoy a todo el periodo, como si volvieras a "
            "ellos cada día. Tu rentabilidad real depende de cuándo y cuánto compraste."
        ),
        returns.WARNING_FX_TIMING: (
            "Los valores en otras divisas se pasan a euros con el tipo del BCE (14:15), que no "
            "coincide con la hora de cálculo del valor liquidativo: añade algo de ruido diario."
        ),
        returns.WARNING_SHORT_HISTORY: (
            "El periodo es de menos de 3 años: la cifra depende mucho de lo que pasó en ese "
            "periodo concreto."
        ),
        returns.WARNING_TOO_SHORT_TO_ANNUALISE: (
            "Hay menos de un año de historia común: no se anualiza."
        ),
    }
)

RETURNS_UNCOVERED_TEXTS: dict[str, str] = {
    returns.ReturnsUncoveredReason.OUTSIDE_UNIVERSE: "No está en el universo analizado.",
    returns.ReturnsUncoveredReason.NAV_NOT_AVAILABLE: "No hay histórico de valor liquidativo.",
    returns.ReturnsUncoveredReason.DISTRIBUTIONS_NOT_AVAILABLE: (
        "ETF de distribución sin datos de repartos: su rentabilidad total no se puede calcular."
    ),
}
