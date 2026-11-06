# Glosario

Conceptos de inversión que usa Radiografía de cartera, explicados para alguien sin formación
financiera. Cada entrada se escribe **antes** de implementar la métrica y se revisa después con
los resultados reales.

> Este glosario es informativo. No es asesoramiento de inversión.

> Las cifras de ejemplo de este documento salen de datos publicados por iShares (BlackRock),
> con posiciones a 4-nov-2026, o de cálculos propios hechos con ellos. Se reproducen como
> ejemplos puntuales para explicar la herramienta; los datos pertenecen a su titular y pueden
> haber cambiado.

## Cómo está organizada cada entrada

```
## Nombre del concepto
**En una frase:** qué es, sin jerga.
**Qué mide:** ...
**Cómo se calcula:** fórmula y pasos, con un ejemplo numérico pequeño.
**Qué decisión ayuda a tomar:** qué puede hacer un inversor particular con este dato.
**Trampas habituales:** errores de interpretación y limitaciones de los datos.
**En el código:** módulo y función donde se implementa.
**Relacionado:** otras entradas.
```

## Índice
- [ISIN](#isin)
- [Acumulación y distribución](#acumulación-y-distribución)
- [Divisa de la clase, de cotización y de exposición](#divisa-de-la-clase-de-cotización-y-de-exposición)
- [Cobertura de divisa (clase "Hedged")](#cobertura-de-divisa-clase-hedged)
- [Réplica física, sintética y optimizada](#réplica-física-sintética-y-optimizada)
- [Domicilio del fondo](#domicilio-del-fondo)
- [TER y coste anual](#ter-y-coste-anual)
- [Tracking difference](#tracking-difference)
- [Look-through](#look-through)
- [Exposición por país y por sector](#exposición-por-país-y-por-sector)
- [Exposición por divisa](#exposición-por-divisa)
- [Concentración y número efectivo de empresas](#concentración-y-número-efectivo-de-empresas)
- [Solapamiento](#solapamiento)
- [Rentabilidad simple y rentabilidad total](#rentabilidad-simple-y-rentabilidad-total)
- [Rentabilidad en euros](#rentabilidad-en-euros)
- [Rentabilidad anualizada](#rentabilidad-anualizada)
- [Rentabilidad simulada con pesos constantes](#rentabilidad-simulada-con-pesos-constantes)
- [Volatilidad](#volatilidad)
- [Máxima caída](#máxima-caída)
- [Caída en episodios fijos](#caída-en-episodios-fijos)
- [VaR histórico y pérdida esperada en la cola](#var-histórico-y-pérdida-esperada-en-la-cola)
- [Beta](#beta)
- [Alpha e intervalo de confianza](#alpha-e-intervalo-de-confianza)



---

## ISIN
**En una frase:** el "DNI" internacional de un valor: un código de 12 caracteres que identifica
un fondo (y su clase concreta) en cualquier país y bolsa.

**Qué mide:** no mide nada; identifica. Su estructura (norma ISO 6166):

| Parte | Ejemplo `IE00B4L5Y983` | Significado |
|---|---|---|
| 2 letras | `IE` | País. En un ETF es el país donde está **domiciliado el fondo** (IE Irlanda, LU Luxemburgo), no dónde invierte ni dónde cotiza |
| 9 caracteres | `00B4L5Y98` | Código nacional asignado por la agencia de ese país |
| 1 dígito | `3` | Dígito de control |

**Cómo se calcula el dígito de control:**
1. Se toman los 11 primeros caracteres y cada letra se convierte en número: A=10, B=11 … Z=35.
   Los dígitos se quedan igual.
2. Se pegan en una sola cadena de dígitos.
3. Algoritmo de Luhn (el de las tarjetas bancarias): empezando por la derecha, se duplica un
   dígito sí y otro no (empezando por el último); si al duplicar sale más de 9, se resta 9; se
   suma todo.
4. Dígito de control = (10 − (suma mod 10)) mod 10.

Ejemplo: `IE00B4L5Y98` → I=18, E=14, B=11, L=21, Y=34 → `1814001142153498` → suma de Luhn 57
→ (10 − 7) mod 10 = **3**. Coincide con el último carácter: el ISIN es válido.

**Qué decisión ayuda a tomar:** saber exactamente qué producto tienes. El mismo fondo cotiza con
tickers distintos en cada bolsa (`IE00B4L5Y983` es `SWDA` en Londres, `EUNL` en Xetra, `IWDA` en
Ámsterdam), y el mismo índice tiene ISIN distintos según la clase: acumulación frente a
distribución (Vanguard FTSE All-World: `IE00BK5BQT80` y `IE00B3RBWM25`) o cubierta en divisa.
Si dudas de qué clase tienes, el ISIN de tu bróker lo resuelve.

**Trampas habituales:**
- Un dígito de control correcto **no garantiza que el ISIN exista**: solo descarta errores de
  tecleo.
- Luhn detecta cualquier error en un solo dígito y la mayoría de intercambios de dos caracteres
  seguidos, pero no todos: intercambiar `09` por `90` pasa inadvertido.
- El prefijo de país de un ETF no indica su exposición geográfica: un ETF irlandés puede invertir
  sobre todo en EE. UU.
- El ticker no sustituye al ISIN: depende de la bolsa, puede repetirse entre bolsas y no tiene
  dígito de control.

**En el código:** `radiografia.domain.isin` (`isin_check_digit`, `isin_problem`).

**Relacionado:** acumulación y distribución, cobertura de divisa, domicilio del fondo.

---

## Acumulación y distribución
**En una frase:** qué hace el fondo con los dividendos (o cupones) que cobra: reinvertirlos
(acumulación, "Acc") o pagártelos (distribución, "Dist").

**Qué mide:** no es una métrica; es una característica de la clase del fondo. Cada opción tiene
su propio ISIN aunque el fondo y el índice sean los mismos.

**Cómo se ve en los datos:** campo `Use of Income` del gestor (`Accumulating` / `Distributing`).

**Qué decisión ayuda a tomar:** en España los dividendos cobrados tributan en el año en que se
cobran; en una clase de acumulación la tributación se difiere hasta la venta. Esta herramienta no
calcula impuestos: solo identifica la clase.

**Trampas habituales:**
- El precio (o valor liquidativo) de una clase de distribución baja cada vez que reparte. Si se
  mira solo la evolución del precio, parece que rinde menos que la de acumulación: hay que sumar
  los repartos (rentabilidad total). Por eso el universo prefiere clases de acumulación para
  calcular rentabilidades.

**En el código:** `radiografia.domain.fund.IncomeTreatment`.

---

## Divisa de la clase, de cotización y de exposición
**En una frase:** un mismo ETF tiene hasta tres "divisas" distintas y solo una importa para el
riesgo de divisa.

| Divisa | Ejemplo: iShares Core MSCI World (IE00B4L5Y983) | ¿Afecta a tu riesgo? |
|---|---|---|
| De la clase (valor liquidativo) | USD | No directamente: es la unidad de contabilidad |
| De cotización (lo que pagas en tu bróker) | EUR en Xetra (`EUNL`), GBP o USD en Londres | No: es solo el "mostrador" |
| De exposición (la de las empresas que hay dentro) | ~70 % USD, más JPY, GBP, CHF... | **Sí** |

**Qué decisión ayuda a tomar:** saber cuánto de tu cartera sube o baja con el tipo de cambio del
euro aunque todo lo compres en euros.

**Trampas habituales:** creer que comprar en euros elimina el riesgo de divisa. Solo una clase
cubierta ("Hedged") lo reduce. La exposición real se calcula con el look-through (paso 7).

**En el código:** `Fund.share_class_currency`, `Fund.base_currency`, `Listing.currency`.

---

## Cobertura de divisa (clase "Hedged")
**En una frase:** una clase que usa contratos a plazo de divisas para neutralizar el efecto del
tipo de cambio entre la divisa de las inversiones y la de la clase (p. ej. el euro).

**Qué decisión ayuda a tomar:** separar dos riesgos que una clase sin cubrir mezcla: el de las
acciones y el del tipo de cambio.

**Trampas habituales:**
- Cuesta más: en el universo, iShares MSCI World EUR Hedged tiene un TER del 0,55 % frente al
  0,20 % de la versión sin cubrir (datos del gestor, 5-nov-2026). Además, la cobertura tiene un
  coste o beneficio implícito según la diferencia de tipos de interés entre divisas, que el TER
  no recoge.
- La cobertura no es perfecta y se ajusta periódicamente.

**Cómo se detecta:** el gestor lo indica con la palabra "Hedged" en el nombre o en el título de
la ficha. No hay un campo específico en sus datos: ver `docs/METODOLOGIA.md`.

**En el código:** `Fund.currency_hedged`.

---

## Réplica física, sintética y optimizada
**En una frase:** cómo consigue el ETF comportarse como su índice.

- **Física completa ("Replicated"):** compra todas las empresas del índice en su peso.
- **Física optimizada o por muestreo ("Optimised", "Sampled"):** compra una selección
  representativa. Habitual en índices con miles de valores, sobre todo de renta fija.
- **Sintética (swap):** el fondo compra una cesta de otros activos y un banco le paga, mediante
  un contrato (swap), la rentabilidad del índice.

**Qué decisión ayuda a tomar:** saber si las posiciones que publica el fondo representan lo que
de verdad te expone. En un ETF sintético no es así: su lista de posiciones es la cesta de
colateral, no el índice. Por eso esta herramienta no hace look-through de ETFs sintéticos.

**Trampas habituales:** en una réplica optimizada, la composición del fondo y la del índice no
coinciden exactamente; el look-through usa la del fondo.

**En el código:** `Fund.replication`, `Fund.methodology`. Hoy los 15 ETFs del universo son de
réplica física.

---

## Domicilio del fondo
**En una frase:** país cuya ley regula el fondo (Irlanda, Luxemburgo...). Son las dos primeras
letras del ISIN de un ETF.

**Qué decisión ayuda a tomar:** el domicilio afecta a la fiscalidad interna del fondo (por
ejemplo, la retención que sufre sobre los dividendos de empresas de EE. UU.) y al marco legal
(UCITS). No indica dónde invierte.

**Trampas habituales:** confundir domicilio con exposición geográfica: un ETF irlandés del S&P 500
invierte en EE. UU.

**En el código:** `Fund.domicile`.

---

## TER y coste anual
**En una frase:** el porcentaje de tu dinero que el ETF se cobra cada año por gestionarse
(*Total Expense Ratio*; en el documento de datos fundamentales, "gastos corrientes").

**Qué mide:** el coste explícito de tener el fondo. No llega factura: se descuenta poco a poco,
cada día, del valor liquidativo.

**Cómo se calcula para una cartera:**
- Coste anual (€) = Σ importe de cada posición × su TER.
- TER ponderado = coste anual ÷ valor de la parte con dato (media de los TER ponderada por peso).

Ejemplo con datos del universo (5-nov-2026), 10.000 €:

| Posición | Importe | TER | Coste/año |
|---|---|---|---|
| iShares Core MSCI World | 6.000 € | 0,20 % | 12,00 € |
| iShares Core S&P 500 | 3.000 € | 0,07 % | 2,10 € |
| iShares MSCI World EUR Hedged | 1.000 € | 0,55 % | 5,50 € |
| **Total** | 10.000 € | **0,196 %** | **19,60 €** |

El 10 % del dinero (la clase cubierta) genera el 28 % del coste.

**Qué decisión ayuda a tomar:** saber cuánto pagas al año y qué posición concentra el coste.

**Trampas habituales:**
- **El TER no es el coste total:** no incluye costes de compraventa dentro del fondo, la
  horquilla en bolsa, comisiones del bróker o de cambio de divisa, ni el coste implícito de la
  cobertura de divisa. La medida más fiel es el [tracking difference](#tracking-difference).
- **Cambiar de ETF para ahorrar TER puede salir caro:** en España vender un ETF tributa por la
  plusvalía, porque los ETFs, en general, no tienen el régimen de traspasos de los fondos. Los
  impuestos pueden superar el ahorro. Esta herramienta muestra el coste; no sugiere cambios.
- **Cambia con el tiempo:** cada TER lleva la fecha en que se consultó.
- **Una diferencia pequeña rara vez es la decisión importante:** el reparto entre acciones y
  renta fija o entre regiones pesa mucho más que 0,1 puntos de comisión.
- **No se proyecta a 10 o 20 años:** hacerlo exige suponer una rentabilidad futura.

**En el código:** `radiografia.analytics.costs.compute_costs`.

**Relacionado:** cobertura de divisa, tracking difference.

---

## Tracking difference
**En una frase:** cuánto ha rendido el ETF por encima (o por debajo) de su índice en un periodo.

**Qué mide:** el coste real que has soportado: incluye el TER, pero también los costes de
compraventa, los impuestos sobre dividendos dentro del fondo y los ingresos por préstamo de
valores, que lo compensan en parte. Puede ser mejor que el TER.

**Cómo se calcula:** rentabilidad anual del fondo − rentabilidad anual del índice, mismo periodo y
divisa. Usamos la media anual a 5 años que publica la gestora.

**Ejemplos reales (5 años a 31-oct-2026):** iShares Core MSCI World, TER 0,20 % y tracking
difference **+0,07 %** al año (ganó a su índice); iShares Core S&P 500, TER 0,07 % y **+0,17 %**.
Los fondos irlandeses pagan menos impuesto sobre los dividendos de EE. UU. del que supone el
índice, y prestan acciones a cambio de una comisión.

**Trampas habituales:**
- Es un dato pasado: no garantiza el futuro.
- En las clases cubiertas en divisa, la gestora compara con el índice **sin cubrir** y en otra
  divisa (Global Aggregate cubierto: −13,85 % frente a −20,43 % en 2021-22). Esa diferencia es
  divisa, no coste: no la mostramos.

**En el código:** `radiografia.analytics.costs.tracking_differences`.

---

## Look-through
**En una frase:** "mirar a través" de cada ETF para ver qué empresas tienes de verdad.

**Cómo se calcula:** peso de X en tu cartera = Σ (peso del ETF en tu cartera × peso de X dentro
del ETF), donde X es una empresa, un país, un sector o una divisa.

Ejemplo real (posiciones a 4-nov-2026), cartera 60 % MSCI World + 30 % S&P 500 + 10 % MSCI World
cubierto: Apple = 60 % × 5,63 % + 30 % × 7,7 % + 10 % × 5,6 % ≈ **6,25 %**. Uno de cada 16 euros.

**Qué decisión ayuda a tomar:** comprobar si tu exposición a una empresa, país o sector es la que
crees antes de añadir otro ETF.

**Trampas habituales:**
- Es una foto: las posiciones tienen fecha y los fondos se rebalancean.
- Una empresa puede aparecer con varias clases de acción (Alphabet A y C); hay que agruparlas.
- No sirve para ETFs sintéticos: su lista de posiciones es colateral, no exposición.
- En renta fija no tiene sentido hablar de "empresas en las que más tienes" del mismo modo; aquí
  solo se usa para la divisa.

**En el código:** `radiografia.analytics.lookthrough.compute_lookthrough`.

---

## Exposición por país y por sector
**En una frase:** el reparto de tu dinero por países y sectores económicos tras abrir los ETFs.

**Ejemplo real:** en la cartera anterior, EE. UU. pesa el **80,7 %**, más que en el MSCI World
(72,5 %) porque el S&P 500 añade más EE. UU.

**Qué decisión ayuda a tomar:** ver si tu reparto es el que querías o el que te ha salido.

**Trampas habituales:** el país es el domicilio que asigna la gestora, no de dónde vienen los
ingresos (Nestlé cuenta como Suiza). La liquidez y los derivados forman su propio grupo.

---

## Exposición por divisa
Completa la entrada [Divisa de la clase, de cotización y de exposición](#divisa-de-la-clase-de-cotización-y-de-exposición).

**Cómo se calcula:** suma por la divisa en que cotiza cada posición dentro de los ETFs. Las clases
cubiertas cuentan al 100 % en su divisa de cobertura (supuesto: ver metodología).

**Ejemplo real:** en la cartera anterior el dólar pesa un **74 %**; sin la clase cubierta, el 81 %.

**Trampas habituales:** la divisa en que cotiza una empresa no es la de sus ingresos; comprar en
euros no elimina el riesgo de divisa.

---

## Concentración y número efectivo de empresas
**En una frase:** cuánto depende tu cartera de pocas empresas.

**Cómo se calcula:**
- Peso de las 10 mayores empresas.
- Número efectivo = 1 ÷ Σ peso² (inverso del índice de Herfindahl-Hirschman, HHI). Si tienes N
  empresas a partes iguales, sale N; cuanto más desigual, menor.

Ejemplo: tres empresas con 50 %, 25 % y 25 % → 1 ÷ (0,25 + 0,0625 + 0,0625) = **2,67**: se comporta
como si tuvieras menos de tres a partes iguales.

**Ejemplo real:** la cartera anterior tiene 1.300 empresas, pero su número efectivo es **67,5**; las
10 mayores suman el 31,1 %.

**Qué decisión ayuda a tomar:** saber si "tengo 1.300 empresas" significa de verdad diversificación.

**Trampas habituales:** describe, no juzga: los índices ponderados por tamaño ya están concentrados.
No mide riesgo (no tiene en cuenta cómo se mueven las empresas entre sí).

---

## Solapamiento
**En una frase:** cuánto de un ETF ya lo tienes en otro.

**Cómo se calcula:** para cada pareja de ETFs, Σ por empresa del menor de sus dos pesos.

Ejemplo: A tiene 50 % Apple y 50 % Microsoft; B tiene 30 % Apple y 70 % Nestlé → solapamiento =
min(50, 30) + min(50, 0) + min(0, 70) = **30 %**.

**Ejemplos reales (4-nov-2026):** World y S&P 500, 70,7 %; S&P 500 y Nasdaq 100, 52,8 %; World y
Nasdaq 100, 38,2 %; World y World cubierto, 97,7 % (es el mismo índice); World y Emergentes, 0 %.

**Qué decisión ayuda a tomar:** entender que añadir un S&P 500 a un World no diversifica: sobre
todo aumenta el peso de EE. UU.

**Trampas habituales:** el solapamiento no es malo en sí; lo que importa es la exposición final.

---

## Rentabilidad simple y rentabilidad total
**En una frase:** cuánto ha subido o bajado tu dinero en un periodo, contando o no los repartos.

**Cómo se calcula:** r = valor final ÷ valor inicial − 1. Para la **rentabilidad total**, cada
reparto se suma el día en que el valor liquidativo baja por él (fecha ex-dividendo) y se supone
reinvertido.

**Ejemplo real:** iShares Core MSCI World, NAV de 126,43 $ (30-sept-2025) a 145,71 $
(30-sept-2026): **15,25 %**, exactamente lo que publica iShares. Deuda pública euro (distribución)
en el mismo año: −3,01 % con repartos (lo publicado) frente a −5,49 % mirando solo el NAV.

**Trampa habitual:** en una clase de distribución, el NAV solo infravalora la rentabilidad.

---

## Rentabilidad en euros
**Cómo se calcula:** NAV en € = NAV en $ ÷ (dólares por euro del BCE). La rentabilidad en euros
combina la del fondo y la de la divisa: (1 + r$) × (1 + efecto divisa) − 1.

**Ejemplo real:** el MSCI World del ejemplo anterior rindió 15,25 % en dólares y **19,17 % en
euros**, porque el dólar se revalorizó un 3,4 % frente al euro (1,1741 → 1,1355 $ por €).

**Trampa habitual:** el BCE fija el tipo a las 14:15 y el NAV se calcula al cierre: a diario hay
ruido; a semanas o meses apenas importa.

---

## Rentabilidad anualizada
**Cómo se calcula:** (valor final ÷ valor inicial)^(365,25 / días) − 1.

**Trampa habitual:** no es la media de los años. +50 % y luego −50 % da una media de 0 %, pero te
deja el 75 % del dinero: −13,4 % anual.

---

## Rentabilidad simulada con pesos constantes
**En una frase:** lo que habría rendido tu reparto actual si lo hubieras mantenido igual cada día.

**Cómo se calcula:** cada día, Σ (peso actual × rentabilidad del ETF), anualizado sobre los
últimos 5 años (o desde que empezó a cotizar el ETF más reciente, si es más tarde).

**Ejemplos reales (en euros, hasta 4-nov-2026):** 100 % MSCI World desde 2009, 12,73 % anual;
60 % World + 30 % S&P 500 + 10 % World cubierto desde 2010, 13,32 %; 60 % World + 20 % deuda
pública + 20 % Global Aggregate desde 2017, 7,56 %.

**Trampas habituales:**
- No es tu rentabilidad: tú compraste en otras fechas y con otros pesos.
- Depende mucho del periodo: desde 2009 incluye uno de los mejores ciclos de la bolsa. Por eso
  ahora se usa siempre la misma ventana de 5 años: dos carteras con ETFs de distinta edad se
  comparan en las mismas fechas (los ejemplos de arriba, calculados antes del cambio, no).
- Rentabilidades pasadas no garantizan rentabilidades futuras.

**En el código:** `radiografia.analytics.returns.compute_returns`.

---

## Volatilidad
**En una frase:** cuánto sube y baja tu cartera de un periodo a otro, expresado al año.

**Cómo se calcula:** desviación típica (muestral) de las rentabilidades de cada periodo ×
√(periodos al año). Usamos semanas de los últimos 5 años: × √52.

**Ejemplos reales (5 años a 4-nov-2026, en euros):** MSCI World 13,8 %; 60 % World + 30 % S&P 500 +
10 % World cubierto 14,1 %; 60 % Nasdaq 100 + 40 % S&P 500 Tecnología 21,8 %; 40 % World + 60 %
renta fija 7,0 %.

**Qué decisión ayuda a tomar:** comparar el "vaivén" de tu cartera con el de una referencia.

**Trampas habituales:**
- Depende de la frecuencia: el World sale 15,0 % con datos diarios, 13,8 % semanales y 12,9 %
  mensuales. En euros, los datos diarios llevan ruido por el desfase de horario del tipo de cambio.
- Cuenta igual subidas y bajadas.
- Muestral (divide entre n − 1) o poblacional (entre n): con 36 meses cambia ~0,16 puntos. iShares
  usa la muestral, y nosotros también.

---

## Máxima caída
**En una frase:** la peor bajada desde un máximo hasta un mínimo posterior, y cuánto tardó en
recuperarse.

**Cómo se calcula:** para cada día, valor ÷ máximo anterior − 1; se toma el peor.

**Ejemplo real:** MSCI World en euros, **−33,9 %** del 19-feb-2020 al 23-mar-2020 (covid);
recuperado el 7-ene-2021. Peor día: 16-mar-2020, −9,9 %.

**Qué decisión ayuda a tomar:** ¿aguantarías ver tu cartera un 34 % abajo sin vender?

**Trampas habituales:** solo ve el periodo con datos (desde 2009 no incluye 2008, cuando la bolsa
mundial cayó cerca del 50 %); es un único episodio, no una frecuencia. Y no sirve para comparar
carteras: cada una tiene su peor momento en un año distinto (ver la entrada siguiente).

---

## Caída en episodios fijos
**En una frase:** cuánto llegó a caer tu cartera dentro de un año malo concreto, comparado con el
mercado mundial en las mismas fechas.

**Cómo se calcula:** se parte del valor al empezar el año y, para cada día del año, valor ÷ máximo
anterior − 1; se toma el peor. Se hace con tu cartera y con el iShares MSCI ACWI. Usamos 2020
(covid: caída rápida y fuerte de las bolsas) y 2022 (inflación y subida de tipos: bajaron a la vez
acciones y bonos).

**Ejemplos reales (en euros, datos a 4-nov-2026):**

| Cartera | 2020 | 2022 |
|---|---|---|
| MSCI ACWI (referencia) | −33,6 % | −16,3 % |
| 100 % MSCI World | −33,9 % | −16,9 % |
| Global con 30 % de bonos | −25,0 % | −14,7 % |
| 60 % Nasdaq 100 + 40 % S&P 500 Tecnología | −30,7 % | −28,5 % |

La cartera tecnológica cae menos que el mercado en 2020 y casi el doble en 2022. Con una sola
"máxima caída" de todo el periodo (−30,7 %, en 2020) parecía más tranquila que el MSCI World
(−33,9 %): era una ilusión del episodio elegido.

**Qué decisión ayuda a tomar:** ver si tu cartera sufre más o menos que el mercado según el tipo
de crisis, y si podrías aguantar esa caída.

**Trampas habituales:** son solo dos episodios y no incluyen 2008 ni crisis largas (2000-2002); la
próxima crisis no tiene por qué parecerse a ninguna. Con bonos, 2022 es especialmente duro porque
los bonos no amortiguaron la caída de las acciones.

**En el código:** `radiografia.analytics.risk.episode_drawdowns`.

---

## VaR histórico y pérdida esperada en la cola
**En una frase:** la pérdida que solo se superó en el 5 % de los peores días.

**Cómo se calcula:** percentil 5 de las rentabilidades diarias de los últimos 5 años. La pérdida
esperada en la cola (*expected shortfall*) es la media de esos peores días.

**Ejemplo real:** MSCI World, VaR 95 % a 1 día = 1,43 % → **143 € por cada 10.000**: "en 1 de cada
20 días se perdió al menos 143 €". Media de esos días: 2,18 %.

**Trampas habituales:**
- No es la pérdida máxima (el 16-mar-2020 se perdió casi un 10 %).
- Con datos mensuales no es fiable: 60 meses dejan solo 3 en la cola del 5 %.
- Para un inversor a largo plazo, la máxima caída suele decir más.

---

## Beta
**En una frase:** cuánto se mueve tu cartera cuando se mueve el mercado.

**Cómo se calcula:** pendiente de la regresión de las rentabilidades semanales de tu cartera sobre
las del índice (iShares MSCI ACWI en euros), ambas por encima del tipo sin riesgo (€STR del BCE),
5 años. El R² dice qué parte de los movimientos explica el mercado.

**Ejemplos reales:** MSCI World 1,04 (R² 0,99); 60 % Nasdaq 100 + 40 % S&P 500 Tecnología **1,47**
(R² 0,79): si el mercado cae un 20 %, tiende a caer en torno a un 29 %.

**Trampas habituales:** solo es fiable con R² alto; con mucha renta fija, compararla con un índice
de acciones dice poco.

---

## Alpha e intervalo de confianza
**En una frase:** la rentabilidad que no explica tu beta, con el rango en que probablemente está.

**Cómo se calcula:** constante de la regresión anterior, × 52 para anualizarla. Intervalo al 95 % =
alpha ± 1,96 × error estándar.

**Ejemplos reales (5 años):** MSCI World +0,09 % [−1,18 %, +1,36 %]; 60 % Nasdaq 100 + 40 % S&P 500
Tecnología +1,61 % **[−7,20 %, +10,42 %]**. En los dos casos el intervalo incluye el 0: con estos
datos, el alpha no se distingue de cero.

**Trampas habituales:**
- En ETFs indexados no mide talento: recoge comisiones, diferencias de reparto con el índice y
  ruido.
- Con mucha renta fija sale un alpha grande y aparentemente significativo que solo es la renta
  fija comparada con un índice de acciones (40 % World + 60 % bonos: −2,95 % [−5,64 %, −0,26 %]).
  Por eso no lo mostramos si la renta variable es menos del 80 %.
- El intervalo supone semanas independientes; si no lo son, sería más ancho.

**En el código:** `radiografia.analytics.risk.compute_risk`.
