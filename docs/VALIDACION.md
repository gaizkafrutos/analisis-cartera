# Validación contra los datos del gestor

> Las cifras de ejemplo de este documento salen de datos publicados por iShares (BlackRock),
> con posiciones a 4-nov-2026, o de cálculos propios hechos con ellos. Se reproducen como
> ejemplos puntuales para explicar la herramienta; los datos pertenecen a su titular y pueden
> haber cambiado.

Resultados de comparar nuestros cálculos con las cifras que publica iShares. Se regeneran con:

```
.venv\Scripts\python scripts\build_holdings.py
.venv\Scripts\python -m pytest -m validation -rsx
```

## Desglose por sector y por país de cada fondo (paso 6)

**Qué se compara:** el desglose que calculamos a partir del fichero de posiciones de cada ETF
(`latest-holdings.csv`) frente al que publica la gestora en la hoja `Exposure Breakdowns` de su
Excel, con la misma fecha.

**Tolerancia:** 0,01 puntos porcentuales por categoría. La gestora publica con dos decimales, así
que cada cifra suya lleva hasta 0,005 puntos de redondeo; la tolerancia es el doble.

**Resultado (posiciones a 4-nov-2026, descargadas el 6-nov-2026):**

| Resultado | Casos | Detalle |
|---|---|---|
| Coinciden | 19 | Diferencia máxima 0,006 puntos en todos: sector de 10 ETFs de renta variable, país de 7 de ellos y sector de 2 de renta fija |
| Discrepancia explicada | 4 | Ver tabla siguiente |
| No comparables por fecha | 3 | Geografía de los 3 ETFs de renta fija: publicada a 1 y 8 de octubre, posiciones a 4 de noviembre |
| Sin desglose publicado | 4 | Geografía de ETFs de un solo país (S&P 500, Nasdaq 100, S&P 500 IT, Japón) |

**Discrepancias:**

| ETF | Desglose | Diferencia máxima | Causa |
|---|---|---|---|
| S&P 500 Information Technology (IE00B3WJKG14) | Sector | 38,8 puntos | La gestora desglosa este ETF sectorial por industria GICS (Semiconductors, Software...); el fichero de posiciones solo trae el sector. No son comparables. |
| MSCI World EUR Hedged (IE00B441G979) | Sector | 0,17 puntos | Su desglose suma 99,40 %: un 0,6 % del fondo no aparece ni en el desglose ni en el fichero de posiciones. Nuestras cifras son proporcionalmente un 0,6 % mayores. |
| MSCI World EUR Hedged (IE00B441G979) | País | 0,42 puntos | Misma causa (EE. UU.: 71,39 % publicado frente a 71,81 % calculado). |
| Core Global Aggregate Bond (IE00BDBRDM35) | Sector | 1,84 puntos | La gestora no cuenta su fondo monetario interno (~2 %) como liquidez. |

Cada discrepancia está en `tests/validation/test_issuer_breakdowns.py` como fallo esperado
(`xfail` estricto): si un día empieza a cuadrar, el test avisa para revisar la explicación.

**Qué significa para el usuario:** la composición por sector y país que mostraremos para los ETFs
de renta variable reproduce la de la gestora salvo redondeo. En la clase cubierta, las cifras
pueden diferir en unas décimas.

## Rentabilidades anuales de cada fondo (paso 8)

**Qué se compara:** la rentabilidad total de cada uno de los 5 últimos años (de 30 de
septiembre a 30 de septiembre) calculada con el NAV y los repartos, frente a la que publica la
gestora en la hoja `Performance Returns`, en la divisa del NAV (sin conversión).

**Tolerancia (por fondo y año, derivada del redondeo de la gestora):** el NAV se publica con 2
decimales (hasta 0,005 de error en cada extremo del año) y la rentabilidad con 2 decimales en %
(0,005 puntos). Tolerancia = (0,005/NAV inicial + 0,005/NAV final) × (1 + |r|) + 0,005 puntos. Un
ETF con NAV de 5 € tiene más margen que uno de 150 $.

**Resultado (datos a 4-nov-2026):** **15 de 15 ETFs coinciden** en los 5 años. La diferencia
máxima es de 0,015 puntos en los ETFs con NAV alto y de hasta 0,12 puntos en los de NAV bajo
(Global Aggregate, ~5 €; World Small Cap, ~7 $), dentro de su tolerancia.

**Repartos:** en la deuda pública euro, 2025-26, la rentabilidad con repartos (−3,01 %) coincide
con la publicada; solo con el NAV saldría −5,49 %. Test incluido.

## Volatilidad a 3 años de cada fondo (paso 9)

**Qué se compara:** desviación típica muestral de 36 rentabilidades mensuales (rentabilidad
total, divisa del NAV) × √12, frente a la "Standard Deviation (3y)" que publica iShares a 31-oct-2026.

**Tolerancia (derivada, por fondo):** 0,005 puntos del redondeo de la cifra publicada, más el
efecto máximo del redondeo del NAV a 2 decimales sobre la desviación típica (desigualdad de
Minkowski): √(12 × 36/35) × 2 × 0,005 ÷ NAV mínimo de la ventana.

**Resultado:** **15 de 15 coinciden.** En 13 la diferencia es de 0,006 puntos o menos (MSCI World:
11,62 % publicado y calculado). Las dos mayores son los ETFs de NAV bajo: Global Aggregate
(~4,5 €), 0,078 puntos; World Small Cap (~6 $), 0,022 puntos.

**Lo que confirma:** la gestora usa la desviación típica muestral (con la poblacional saldría
~0,16 puntos menos).

## Modo SEC: gemelos de EE. UU. frente a los datos de iShares (fase 1 de datos reales)
El modo SEC aproxima la composición de cada ETF UCITS con la del ETF de EE. UU. que
replica el mismo índice (formulario N-PORT de la SEC). Comparación, fondo a fondo, entre lo que
calcula la app con los datos exactos de iShares (posiciones a 4-nov-2026) y con el gemelo (datos
de la SEC a 30-jun, 31-jul o 31-ago-2026). Se regenera con `scripts/build_public.py`.

| ETF UCITS (índice) | Gemelo | EE. UU. | 10 mayores | Nº efectivo | Empresas |
|---|---|---|---|---|---|
| MSCI World | URTH | 72,5 % / 69,4 % | 27,8 % / 27,5 % | 83 / 85 | 1.242 / 1.283 |
| MSCI ACWI | ACWI | 64,6 % / 60,8 % | 25,7 % / 24,8 % | 99 / 106 | 1.655 / 2.217 |
| S&P 500 | IVV | 100 % / 96,8 % | 39,2 % / 37,8 % | 44 / 47 | 501 / 501 |
| Nasdaq-100 | QQQ | 97,1 % / 94,3 % | 49,5 % / 47,7 % | 30 / 32 | 100 / 101 |
| MSCI EM IMI | IEMG | — | 32,0 % / 31,7 % | 39 / 37 | 2.943 / 2.868 |
| EURO STOXX 50 | FEZ | — | 41,5 % / 41,9 % | 33 / 31 | 50 / 50 |

(iShares / gemelo.) Cartera de ejemplo con fondos solapados: EE. UU. 85,7 % / 82,6 %,
solapamiento World–S&P 500 70,7 % / 66,4 %, 10 mayores 35,0 % / 34,4 %, nº efectivo 56 / 60.

**De dónde salen las diferencias:**
- **Fechas:** la SEC publica con unos 60 días de retraso y solo a fin de mes; entre junio y
  noviembre el mercado cambia los pesos (sobre todo los de las mayores empresas).
- **País:** la SEC usa el país del emisor (Accenture, Medtronic o Linde cuentan como Irlanda o
  Reino Unido); iShares las asigna a EE. UU. Por eso el peso de EE. UU. sale unos 3 puntos más
  bajo con el gemelo. No es un error de ninguno de los dos: son dos definiciones.
- **Muestreo:** el MSCI ACWI de iShares UCITS compra una muestra (1.655 empresas); el gemelo,
  casi todo el índice (2.217).

**Gemelos con un índice solo parecido: descartados.** El error era demasiado grande para
llamarlo aproximación, así que esos ETFs salen como "no cubierto" en el modo SEC:

| ETF UCITS (índice) | Gemelo (índice) | 10 mayores | Nº efectivo | Empresas |
|---|---|---|---|---|
| MSCI Europe | IEUR (MSCI Europe IMI) | 21,6 % / 18,7 % | 111 / 135 | 381 / 1.004 |
| MSCI Japan IMI | EWJ (MSCI Japan) | 23,5 % / 30,1 % | 104 / 67 | 928 / 169 |
| S&P 500 Capped 35/20 IT | XLK (Technology Select Sector) | 76,7 % / 64,4 % | 8 / 16 | 76 / 74 |

## Otras gestoras: el mismo índice en dos gestoras (fase 2 de la v1)
Test: `tests/validation/test_other_issuers_samples.py`, con los ficheros descargados a mano el
7-nov-2026 (`data/raw/muestras/`, fuera de git) y el snapshot de iShares a 4-nov-2026. Cada
fichero se compara con el ETF de iShares que replica el mismo índice: si la app reconoce bien las
empresas, el solapamiento debe acercarse al 100 % (no llega por diferencias de muestreo, liquidez
y fechas).

| Fichero | Comparado con | Peso reconocido como empresa de iShares | Solapamiento en la app |
|---|---|---|---|
| Xtrackers MSCI World 1C | iShares Core MSCI World | 99,9 % | 97,3 % |
| Amundi Core MSCI World Acc | iShares Core MSCI World | 95,8 % | 94,6 % |
| SPDR MSCI ACWI | iShares MSCI ACWI | 95,7 % | 92,0 % |

- **Xtrackers** escribe los nombres casi como iShares; lo que falta son diferencias de país.
- **Amundi** abrevia o cambia el orden en algunos nombres ("SCHWAB CHARLES", "TORONTO DOMINIO
  BANK") y usa nombres anteriores ("GENERAL ELECTRIC" frente a "GE AEROSPACE"): unos 80 nombres,
  un 4 % del peso, quedan sin emparejar.
- **SPDR** frente a iShares ACWI: el ETF de iShares tiene un 2,5 % en otros ETFs de iShares
  (India, Brasil, China A, Arabia Saudí) que no se pueden emparejar con acciones; el resto son
  nombres distintos como en Amundi.
- Umbrales del test (lo de hoy menos un margen): reconocido 99 %, 94 % y 94 %; solapamiento 95 %,
  93 % y 90 %. Si un fichero nuevo queda por debajo, se informa; no se bajan los umbrales.
- Países y sectores de los tres ficheros se traducen todos a etiquetas del motor (el test falla
  si queda alguno en español).

## Pendiente
