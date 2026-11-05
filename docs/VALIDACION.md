# Validación contra los datos del gestor

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

## Pendiente
