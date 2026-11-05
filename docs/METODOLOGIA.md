# Metodología

Cómo se calcula cada resultado, con qué datos y bajo qué supuestos. El glosario explica los
conceptos; este documento fija las decisiones concretas de implementación.

> Herramienta informativa. Nada de lo aquí descrito es asesoramiento de inversión.

## Supuestos generales
- Divisa base: euro. Las series en otra divisa se convierten con los tipos de referencia del BCE.
- La cartera se describe por su **valor de mercado actual**, no por el precio de compra.
- El riesgo histórico aplica los **pesos actuales** a todo el periodo analizado: es una
  simulación, no la rentabilidad que obtuvo el usuario.
- Si falta un dato, el resultado se marca "no disponible" con su motivo y se indica qué
  porcentaje de la cartera queda sin cubrir. Nunca se rellena con supuestos.

## Entrada de cartera
Código: `radiografia.input` (lectura y validación) y `radiografia.domain` (ISIN y modelos).

**Formato:** una fila por posición con un identificador (ISIN o ticker) y su **valor de mercado
actual en euros**. Por formulario o CSV con cabecera.

**CSV:** se acepta el formato de Excel en español (separador `;`, coma decimal: `1.234,56`) y en
inglés (separador `,`, punto decimal: `1,234.56`). El separador de la cabecera fija la convención
de todo el fichero. Codificación UTF-8 (con o sin BOM) o Windows-1252. Máximo 200 posiciones.

**Importes:** se ignoran `€`, `EUR` y espacios. Los separadores de miles deben formar grupos de 3
cifras. Máximo 2 decimales. Un número con exactamente 3 cifras tras el separador decimal y sin
separador de miles (`1.500` en un CSV en inglés, `1,500` en uno en español) se rechaza por
ambiguo en lugar de adivinar. El importe debe ser mayor que cero.

**Identificadores:**
- 9 caracteres o más: se trata como ISIN. Formato incorrecto o dígito de control erróneo → error
  que el usuario debe corregir (un carácter de más o de menos no se convierte en un ticker
  desconocido).
- Menos de 9 caracteres: se trata como ticker. Solo se resuelve si corresponde a un único ETF del
  universo (se admite sufijo de bolsa, `EUNL.DE` → `EUNL`). Si no se reconoce o es ambiguo, la
  posición queda **no cubierta** con su motivo.
- ISIN válido pero fuera del universo → **no cubierto**, no es un error.

**Pesos:** importe de cada posición / suma de todos los importes, incluidas las posiciones no
cubiertas. Así el porcentaje "no cubierto" es un porcentaje de la cartera completa. Las filas que
corresponden al mismo fondo (por ISIN, ticker o ambos) se suman.

**Errores:** si hay cualquier error, no se construye la cartera y se listan todos los errores con
su número de fila. Una cartera parcial tendría pesos incorrectos.

**Limitaciones:** el dígito de control solo detecta erratas (no comprueba que el ISIN exista) y no
detecta todos los intercambios de caracteres. El código de país se comprueba como dos letras, no
contra la lista ISO 3166.

## Universo de fondos
Código: `scripts/build_universe.py`, `radiografia.data.sources.ishares`, `radiografia.data.universe`.

**Qué contiene:** 15 ETFs UCITS de iShares (12 de renta variable, 3 de renta fija), elegidos para
cubrir las carteras de ejemplo: núcleo global, regiones, un sector, factores, una clase cubierta
a euros y renta fija. Lista y motivo de cada uno en `data/reference/universe_seed.csv`.

**Cómo se construye:** para cada ETF se descargan la ficha web y el Excel oficial del gestor
(sitio británico, en inglés). Del Excel (hoja `Key Facts`) salen ISIN, TER, clase de activo,
índice, divisas, uso de los ingresos, domicilio, estructura y método de réplica, y fechas de
lanzamiento. De la ficha web salen el nombre, si la clase está cubierta en divisa y la tabla de
cotizaciones (bolsa, ticker, divisa). Resultado: `data/reference/universe.csv` y `listings.csv`,
con URL de origen y fecha de descarga por fondo. Los ficheros descargados quedan en `data/raw/`
(fuera de git).

**Comprobaciones:** el TER de los 15 coincide con el que publica el buscador de productos de
iShares (otra fuente del mismo gestor) el 5-nov-2026. Los tests de `tests/data/` verifican sobre
los ficheros versionados que todos los ISIN son válidos, que cada fondo tiene cotización en
euros, que ningún ticker es ambiguo dentro del universo y que los tickers habituales resuelven.

**Problemas encontrados en los datos del gestor y cómo se tratan:**
- El Excel no es XML válido cuando un nombre contiene `&` ("S&P 500"). Se escapa el `&` antes de
  leer: reparación de formato, sin cambio de contenido.
- El Excel sustituye `€` por un carácter inválido (U+FFFD). El nombre se toma de la ficha web,
  donde aparece bien.
- Las etiquetas varían entre fondos ("Fund Base Currency" / "Base Currency", "Share Class Launch
  Date" / "Inception Date"). Se aceptan ambas.
- Un fondo (MSCI World EUR Hedged) no publica divisa de la clase ni fecha de lanzamiento de la
  clase: quedan vacías ("no disponible"), no se deducen.
- No hay un campo de cobertura de divisa. Se marca como cubierta si "Hedged" aparece como
  segmento del título de la ficha (`... | AGGH | Hedged`) o como palabra del nombre
  (`MSCI World EUR Hedged`). Comprobado en los dos ETFs cubiertos del universo.
- Un valor inesperado (estructura distinta de Physical/Synthetic, uso de ingresos desconocido,
  TER fuera de 0-3 %) detiene la construcción en lugar de adivinar.

**Limitaciones:** el universo no incluye fondos indexados no cotizados ni ETFs de otras gestoras.
Los tickers solo se resuelven si aparecen en la tabla de cotizaciones de iShares.

## Posiciones de los fondos
Código: `scripts/build_holdings.py`, `radiografia.data.sources.ishares_holdings`,
`radiografia.data.snapshots`, `radiografia.analytics.fund_breakdown`.

**Fuente:** el fichero `latest-holdings.csv` de cada ETF (enlazado desde su ficha). Se usa el CSV y
no la hoja `Holdings` del Excel porque solo el CSV trae país (`Location`) y bolsa. Se guardan todas
las líneas, liquidez y derivados incluidos, en `data/snapshots/<fecha>/` (fuera de git), junto con
los desgloses publicados por la gestora y la fecha de las posiciones de cada fondo.

**Pesos:** valor de mercado de cada línea ÷ suma del valor de mercado del fondo. No se usa la
columna de peso de la gestora porque está redondeada a 0,01 %: en un fondo con miles de posiciones
pequeñas casi todas aparecen como 0,00 % y la columna suma mucho menos del 100 % (76 % en el
Global Aggregate Bond el 4-nov-2026).

**Liquidez y derivados:** efectivo, fondos monetarios, garantías, divisas, futuros y contratos a
plazo forman un único grupo, "Cash and/or Derivatives", como en los desgloses de la gestora.

**Limitaciones:**
- Los futuros valen 0 a precio de mercado; la exposición que añaden (su nocional) no se cuenta.
  Suelen ser pequeños: sirven para mantener invertida la liquidez.
- En las clases cubiertas, los contratos a plazo de divisa aparecen como líneas del fichero. Su
  efecto sobre la exposición a divisa se tratará en el paso 7.
- El país es el que asigna la gestora a cada empresa (sobre todo su domicilio), no dónde vende.
- En renta fija, el desglose geográfico de la gestora se publica con un mes de retraso respecto a
  las posiciones.

**Validación:** ver `docs/VALIDACION.md`. Coinciden 19 de 19 comparaciones válidas sin
discrepancia conocida, con una diferencia máxima de 0,006 puntos; 4 discrepancias explicadas.

## Por métrica
Cada métrica tendrá: datos de entrada, fórmula, frecuencia y ventana, anualización (si aplica),
supuestos, limitaciones, cómo se valida contra el gestor y tolerancia aceptada.

### Costes: TER ponderado y coste anual
Código: `radiografia.analytics.costs.compute_costs`.

- **Datos:** TER de cada ETF de `data/reference/universe.csv` (publicado por la gestora, con fecha
  de consulta) e importes actuales de la cartera.
- **Fórmulas:** coste anual = Σ importe × TER; TER ponderado = coste anual ÷ importe cubierto.
- **Cobertura:** solo las posiciones con TER conocido. Las demás se muestran sin dato y la
  métrica pasa a "parcial"; su coste nunca se supone cero ni se reparte entre las demás.
- **Fecha del dato:** la más antigua de los TER usados.
- **Avisos:** el TER no es el coste total (siempre); la cobertura de divisa tiene un coste
  implícito no incluido (si hay clases cubiertas); cobertura parcial (si aplica).
- **Sin proyección temporal:** el coste es el de hoy sobre el valor de hoy.
- **Validación:** el TER de cada ETF se contrasta con el buscador de productos del gestor al
  construir el universo (15 de 15 coinciden, 5-nov-2026). Tests con un ejemplo calculado a mano
  (19,60 € y 0,196 %) y comprobación de que coste anual = TER ponderado × importe cubierto.

### Look-through: país, sector, divisa, concentración y solapamiento
Código: `radiografia.analytics.lookthrough.compute_lookthrough`.

- **Datos:** posiciones del snapshot local (`data/snapshots/`), con su fecha; pesos por valor de
  mercado (ver "Posiciones de los fondos").
- **Fórmula:** peso de X = Σ (peso del ETF en la cartera × peso de X dentro del ETF).
- **Cobertura:**
  - País, sector, empresas, concentración y solapamiento: ETFs de renta variable del universo,
    de réplica física y con posiciones disponibles.
  - Divisa: además, los ETFs de renta fija con posiciones.
  - El resto se lista como no cubierto, con su peso y motivo. Los porcentajes se refieren a la
    parte cubierta, y la métrica pasa a "parcial" si no es el 100 %.
- **Liquidez y derivados:** un grupo propio en país y sector; en divisa, cada línea en su divisa.
- **Clases cubiertas (supuesto):** cuentan al 100 % en su divisa de cobertura (divisa de la clase
  o, si la gestora no la publica, la divisa base). El fichero de posiciones solo muestra los
  contratos a plazo por su valor neto (en el MSCI World EUR Hedged, unos 31 millones de euros en
  un fondo de 5.386 millones), no el importe que cubren, así que la cobertura no se puede calcular
  desde los datos. Se avisa al usuario.
- **Empresas:** se agrupan las clases de acción por nombre ("ALPHABET CLASS A" y "CLASS C") y
  país. Fiable dentro de una misma gestora.
- **Concentración:** peso de las 10 mayores y número efectivo de empresas = 1 ÷ Σ peso²
  (calculado sobre las empresas, sin la liquidez).
- **Solapamiento:** por pareja de ETFs, Σ min(peso en A, peso en B), con los pesos de cada fondo.
  Además, peso y número de empresas presentes en dos o más ETFs de la cartera.
- **Sin datos:** si no hay snapshot, todo sale como "no disponible"; nunca se estima.
- **Validación:** una cartera 100 % MSCI World reproduce el desglose por país publicado por la
  gestora (tolerancia 0,01 puntos); el peso de Apple en una cartera de tres ETFs coincide con la
  fórmula hecha a mano; la clase cubierta reduce la exposición al dólar exactamente en su peso.
  Tests en `tests/validation/test_lookthrough_real.py`.

### Rentabilidades en euros
Código: `scripts/build_prices.py`, `radiografia.data.sources.ishares_prices`,
`radiografia.data.sources.ecb`, `radiografia.analytics.returns`.

- **Datos:** NAV diario de cada ETF desde su lanzamiento (hoja `Historical NAVs`), su divisa
  (hoja `Fund Header`), los repartos de las clases de distribución (pestaña de la ficha web) y los
  tipos de referencia del BCE (`EXR`, desde 2009). Todo en el snapshot local.
- **Rentabilidad total:** factor diario = (NAV_t + reparto con fecha ex-dividendo t) ÷ NAV_(t−1).
  Un reparto en fecha sin NAV se aplica en la siguiente fecha con NAV.
- **Euros:** NAV ÷ tipo del BCE (unidades de la divisa por euro), con el último tipo publicado en
  o antes de cada fecha. Si falta el tipo de una divisa, el ETF no se cubre (nunca se supone EUR).
- **Cartera:** pesos actuales constantes (rebalanceo diario), reescalados a la parte cubierta.
  Ventana común desde el lanzamiento del ETF más reciente; un día sin NAV de un ETF cuenta como
  0 % para él.
- **Anualizada:** (valor final ÷ inicial)^(365,25 / días) − 1. No se anualiza con menos de un año
  de historia común; con menos de tres se avisa.
- **No cubiertos:** ETFs fuera del universo, sin NAV, o de distribución sin datos de repartos.
- **Validación:** rentabilidades anuales de los 15 ETFs frente a las publicadas por iShares, en la
  divisa del NAV. Ver `docs/VALIDACION.md`.

### Tracking difference
- **Dato de la gestora:** rentabilidad anualizada a 5 años del fondo − la de su índice, en la
  última fecha de fin de mes publicada. Media ponderada sobre los fondos que lo tienen.
- **Clases cubiertas:** no disponible (la gestora compara con el índice sin cubrir en otra divisa).

(Siguientes métricas a partir del paso 9.)
