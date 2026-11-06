"""Spanish texts for every metric, warning and the disclaimer. Single source for UI and docs.

Rules (CLAUDE.md, "Regulación y lenguaje"): describe facts about the portfolio; never recommend
buying, selling or switching, and never name alternative products.
"""

from __future__ import annotations

from dataclasses import dataclass

from radiografia.analytics import costs, lookthrough, returns, risk

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
    "Calculado sobre el {covered} de tu cartera; {missing} no se incluyen en este cálculo "
    "(el motivo se indica en cada sección)."
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
        "Es renta fija: cuenta en la exposición por divisa, pero no se desglosa por empresa, "
        "país ni sector."
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
                "Lo que habría rendido de media cada año tu reparto actual en los últimos 5 "
                "años, en euros. No es tu rentabilidad real ni una previsión."
            ),
            how_it_is_computed=(
                "Valor liquidativo diario de cada ETF con sus repartos reinvertidos, pasado a "
                "euros con los tipos del BCE, combinado con tus pesos actuales y anualizado."
            ),
            limitations=(
                "Supone que mantienes los pesos actuales todos los días del periodo.",
                "Siempre los últimos 5 años, para que dos carteras se comparen en las mismas "
                "fechas; si algún ETF tiene menos historia, desde que empezó a cotizar.",
                "Cinco años son pocos: el resultado depende mucho de cómo le fue al mercado en "
                "ese tramo concreto.",
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

METRIC_TEXTS.update(
    {
        risk.VOLATILITY: MetricText(
            title="Volatilidad",
            one_liner=(
                "Cuánto sube y baja tu cartera de una semana a otra, expresado al año. Más "
                "volatilidad significa un camino más movido, no necesariamente peor."
            ),
            how_it_is_computed=(
                "Desviación típica de las rentabilidades semanales de los últimos 5 años, "
                "multiplicada por √52."
            ),
            limitations=(
                "Trata igual las subidas que las bajadas.",
                "Depende de la frecuencia: con datos diarios o mensuales sale distinta.",
            ),
        ),
        risk.EPISODE_DRAWDOWNS: MetricText(
            title="Caídas en dos crisis recientes",
            one_liner=(
                "Cuánto llegó a bajar tu reparto actual desde su máximo en 2020 y en 2022, "
                "comparado con el mercado mundial de acciones en las mismas fechas."
            ),
            how_it_is_computed=(
                "Para cada año se parte del valor al empezar el año y se busca la mayor bajada "
                "desde un máximo anterior dentro de ese año, con datos diarios en euros. Lo mismo "
                "con el iShares MSCI ACWI (mercado mundial de acciones)."
            ),
            limitations=(
                "Son dos episodios de distinto tipo (2020, caída rápida de las bolsas; 2022, "
                "bajada a la vez de acciones y bonos), pero no los únicos posibles: no incluyen "
                "2008 ni crisis más largas.",
                "Simula tus pesos actuales en el pasado; no es lo que te pasó a ti.",
                "Si algún ETF no existía al empezar el año, ese episodio no se muestra.",
            ),
        ),
        risk.MAX_DRAWDOWN: MetricText(
            title="Máxima caída",
            one_liner=(
                "La peor bajada desde un máximo hasta un mínimo en el periodo, y cuánto tardó en "
                "recuperarse. Pregúntate si la aguantarías sin vender."
            ),
            how_it_is_computed=(
                "Para cada día, valor ÷ máximo anterior − 1; se toma el peor. Con datos diarios "
                "de todo el periodo disponible."
            ),
            limitations=(
                "Solo ve el periodo con datos: si empieza en 2009, no incluye la crisis de 2008.",
                "Es un único episodio, no dice con qué frecuencia ocurre.",
            ),
        ),
        risk.VAR_95_1D: MetricText(
            title="Pérdida diaria en 1 de cada 20 días (VaR 95 %)",
            one_liner=(
                "En 1 de cada 20 días de los últimos 5 años, tu cartera perdió al menos esta "
                "cantidad. No es la pérdida máxima."
            ),
            how_it_is_computed=(
                "Percentil 5 de las rentabilidades diarias de los últimos 5 años (VaR histórico)."
            ),
            limitations=(
                "Dice cuánto se perdió como mínimo en los peores días, no cuánto como máximo.",
                "Supone que los próximos 5 años se parecerán a los últimos 5.",
            ),
        ),
        risk.EXPECTED_SHORTFALL_95_1D: MetricText(
            title="Pérdida media en esos días",
            one_liner="La pérdida media en ese 5 % de peores días.",
            how_it_is_computed="Media de las rentabilidades diarias iguales o peores que el VaR.",
            limitations=("Basado en los últimos 5 años: no incluye crisis anteriores.",),
        ),
        risk.BETA: MetricText(
            title="Sensibilidad al mercado (beta)",
            one_liner=(
                "Cuánto se mueve tu cartera cuando se mueve el mercado mundial: con beta 1,2, si "
                "el índice cae un 10 %, tu cartera tiende a caer en torno a un 12 %."
            ),
            how_it_is_computed=(
                "Regresión de tus rentabilidades semanales sobre las del iShares MSCI ACWI, en "
                "euros y por encima del €STR, últimos 5 años."
            ),
            limitations=(
                "Es fiable solo si el mercado explica bien tu cartera (R² alto).",
                "Con mucha renta fija, la comparación con un índice de acciones dice poco.",
            ),
        ),
        risk.ALPHA: MetricText(
            title="Rentabilidad no explicada por el mercado (alpha)",
            one_liner=(
                "La parte de tu rentabilidad que no explica tu beta, con su rango de "
                "incertidumbre. En ETFs indexados no mide talento: suele ser indistinguible de 0."
            ),
            how_it_is_computed=(
                "Constante de la misma regresión, anualizada (× 52), con un intervalo de "
                "confianza del 95 % a partir de su error estándar."
            ),
            limitations=(
                "Con pocos años de datos el intervalo es muy ancho.",
                "No se muestra si la renta variable es menos del 80 % de la cartera.",
            ),
        ),
    }
)

WARNING_TEXTS.update(
    {
        risk.WARNING_SHORT_RISK_HISTORY: (
            "Hay menos de 3 años de historia común: las cifras dependen mucho de ese periodo."
        ),
        risk.WARNING_HISTORY_EXCLUDES_OLDER_CRISES: (
            "Solo incluye el periodo con datos de todos tus ETFs; crisis anteriores (como 2008) "
            "pueden no estar."
        ),
        risk.WARNING_VAR_IS_NOT_MAX_LOSS: (
            "No es la pérdida máxima: en los días malos de verdad se perdió bastante más."
        ),
        risk.WARNING_VOLATILITY_SYMMETRIC: (
            "La volatilidad cuenta igual las subidas que las bajadas."
        ),
        risk.WARNING_LOW_EQUITY_SHARE_FOR_BETA: (
            "Menos del 80 % de tu cartera es renta variable: compararla con un índice de "
            "acciones dice poco. La beta se muestra con cautela y el alpha no se muestra."
        ),
        risk.WARNING_LOW_R_SQUARED: (
            "El mercado explica solo parte de los movimientos de tu cartera (R² bajo): la beta "
            "es menos fiable."
        ),
        risk.WARNING_ALPHA_IS_NOT_SKILL: (
            "En una cartera de ETFs indexados, el alpha recoge comisiones, diferencias de reparto "
            "con el índice y ruido, no habilidad."
        ),
        risk.WARNING_ALPHA_INTERVAL_INCLUDES_ZERO: (
            "El rango incluye el 0: con estos datos no se puede distinguir el alpha de cero."
        ),
    }
)
