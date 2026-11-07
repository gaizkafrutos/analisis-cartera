# Auditoría del MVP

Valoración crítica de Radiografía de cartera tras completar el MVP. Todas las cifras proceden del
propio proyecto: datos de iShares con posiciones a 4-nov-2026, precios hasta esa fecha y tipos del
BCE. Se usan cuatro carteras: las tres de ejemplo (global diversificada, muy concentrada y con fondos
solapados) y un 100 % MSCI World como referencia. Los tests citados están en `tests/`; los
resultados de la validación, en `docs/VALIDACION.md`.

> **Nota posterior (6-nov-2026).** Las cifras de esta auditoría son las del momento en que se
> escribió, antes de aplicar la recomendación 1. Desde entonces: la referencia de las caídas en
> la app y el resumen es el **MSCI ACWI** (en 2022, −16,3 %; aquí se compara con el MSCI World,
> −16,9 %); la rentabilidad simulada usa los **últimos 5 años** para todas las carteras (aquí,
> desde la fecha común de cada una); y la CI tiene **233 tests** (aquí, 219). La tabla con las
> dos referencias está en `docs/GLOSARIO.md`, "Caída en episodios fijos".
>
> **Nota posterior (7-nov-2026).** Al cerrar la v1: la CI tiene **323 tests** y la validación
> **71** (aquí, 219 y 67); el universo tiene **18 ETFs** (los 15 de iShares más uno de Xtrackers,
> Amundi y SPDR, que se analizan subiendo su fichero de posiciones); la app avisa cuando las
> posiciones tienen más de un mes y compara lado a lado la cartera con el mercado mundial (puntos
> 5.6 y 4 de abajo). La actualización completa de esta auditoría está pendiente (fase 4).
>
> Las cifras se reproducen como ejemplos puntuales para explicar la herramienta; los datos
> de iShares pertenecen a su titular.

**Conclusión en una frase:** la parte de *qué tienes* (look-through, divisa, concentración,
solapamiento y costes) es sólida, está validada contra la gestora y responde preguntas que un
inversor no puede contestar solo. La parte de *riesgo histórico* es correcta pero aporta mucho
menos, y en dos casos induce a error. El mayor límite no es técnico: el universo de 15 ETFs de
iShares deja fuera los fondos que más usa un inversor español, y la licencia de los datos impide
publicar la herramienta.

---

## 1. Qué aporta de verdad

| Métrica | Decisión que ayuda a tomar | Evidencia en las carteras de prueba |
|---|---|---|
| **Exposición por divisa** | Entender que comprar en euros no quita el riesgo de divisa, y cuánto pesa | Un 100 % World depende del dólar en un **73 %**. La concentrada, en un **100 %**. Incluso la global, con un 30 % de bonos, tiene un **44 %** en dólares |
| **Exposición por país** | Ver si el reparto geográfico es el buscado | La solapada tiene un **86 %** en EE. UU. frente al **65 %** del MSCI ACWI; la concentrada, un **98 %** |
| **Solapamiento entre pares de ETFs** | Darse cuenta de que añadir un ETF no diversifica | World y S&P 500 comparten un **70,7 %**; World y World cubierto, un **97,7 %** (es el mismo índice); World y emergentes, un **0 %** |
| **Peso de las 10 mayores empresas** | Ver la dependencia real de pocas empresas | Concentrada **58 %**, solapada **35 %**, global **25 %**. En una cartera 60 % World + 30 % S&P 500 + 10 % World cubierto, Apple pesa un 6,25 % sin que el usuario la haya comprado directamente |
| **Coste anual en euros y tracking difference** | Saber cuánto se paga y si el fondo cuesta lo que anuncia | Entre 16,50 € y 24,00 € al año sobre 10.000 €. La diferencia con el índice es más informativa que el TER: el S&P 500 rinde **+0,17 %/año** sobre su índice cobrando un 0,07 %, y el Nasdaq 100 rinde **−0,21 %** cobrando un 0,30 % |
| **Volatilidad** | Comparar el "vaivén" con una referencia | Concentrada **21,8 %** frente a World **13,8 %** y global **9,6 %**. Validada: la volatilidad a 3 años de los 15 ETFs coincide con la de iShares (World 11,62 % = 11,62 %) |
| **Reparto acciones/bonos en el resumen** | Contextualizar todo lo demás | Sin esa frase, la cartera global decía "el 62 % de tu renta variable está en EE. UU." sin que se viera que la renta variable es solo el 70 % |

Por qué estas sí: responden a preguntas concretas que el usuario no puede contestar mirando su
bróker, y su fiabilidad está demostrada. El desglose por sector y por país reproduce el de la
gestora con una diferencia de **0,006 puntos** en 19 de 19 comparaciones válidas.

## 2. Qué no merece la pena (o hay que rebajar)

**VaR al 95 % y pérdida media en la cola: redundantes. Propuesta: quitarlos de la vista
principal.**
En las cuatro carteras el VaR histórico coincide con 1,645 × la desviación típica diaria
(World 1,43 % frente a 1,55 %; concentrada 2,52 % frente a 2,56 %; global 0,96 % frente a 1,03 %;
solapada 1,77 % frente a 1,79 %). No dice nada que la volatilidad no diga ya, y a un
horizonte de un día es irrelevante para quien invierte a años. Además, "en 1 de cada 20 días
perdió al menos 96 €" se lee fácilmente como "pierdo como mucho 96 €".

**Alpha: no aporta. Propuesta: sacarlo de la interfaz y dejarlo en la metodología como
material didáctico.**
En las tres carteras donde se calcula, el intervalo incluye el cero:
- World: [−1,18 %, +1,36 %];
- solapada: [−2,6 %, +2,9 %];
- concentrada: **[−7,2 %, +10,4 %]**.

En la cartera global no se muestra, porque la renta variable no llega al 80 %. Cuando sí se
mostraba sin esa regla, una cartera con un 60 % de bonos daba −2,95 % "significativo", que en
realidad era solo la renta fija comparada con acciones. Una métrica que o es indistinguible de
cero o es engañosa no ayuda a decidir nada. Mostrarla con su rango fue la decisión correcta para
aprender, pero no para el producto.

**Máxima caída en la ventana disponible: engañosa al comparar carteras. Propuesta: sustituirla
por caídas en episodios fijos.**
La concentrada (volatilidad 21,8 %) sale con una máxima caída de **−30,7 %**, *menor* que la del
World (−33,9 %), porque en las dos el peor episodio es el covid de 2020 y la tecnología se recuperó
antes. En 2022, en cambio, la concentrada cayó un **−28,5 %** y el World un **−16,9 %**, y esa
caída no aparece en ninguna parte. Además, cada cartera tiene su propia ventana (World desde
2009, global desde 2017), así que las máximas caídas no son comparables entre sí, y ninguna
incluye 2008. Mostrar la caída en episodios fijos (2020, 2022 y, con índices, 2008) es más honesto
y más útil. Es justo la fase 3, y pasa a ser prioritaria.

**Rentabilidad histórica simulada: rebajar o quitar.**
Desde la fecha común (21-nov-2017), la concentrada habría rendido un **20,9 %** anual frente al
**12,6 %** del World. Aunque lleva todos sus avisos, es la cifra que más invita a decidir mirando
el retrovisor ("me paso a tecnología"), y eso choca con el espíritu del proyecto. Además, como cada
cartera usa su propia ventana (concentrada desde 2015, global desde 2017), las cifras que muestra
la app no son comparables entre carteras. Si se mantiene, debería ser con una ventana fija y común,
y fuera del resumen.

**Peso en empresas repetidas: redundante con el solapamiento por pares. Rebajar.**
Mezcla dos cosas distintas. En la cartera 60 % World + 30 % S&P 500 + 10 % World cubierto da un 99,2 % porque el World y el World
cubierto son el mismo índice; en la solapada, un 85 % (454 empresas). El solapamiento por pares
explica lo mismo y además dice *entre qué fondos*.

**Número efectivo de empresas: útil, pero difícil de leer. Mantener como dato secundario.**
"Tienes 4.185 empresas pero tu concentración equivale a 107" es llamativo, pero exige entender la
idea de Herfindahl. El peso de las 10 mayores comunica casi lo mismo de forma inmediata
(25 % en la global, 58 % en la concentrada).

**Beta: mantener, pero en segundo plano.**
Discrimina bien entre carteras (concentrada 1,47, World 1,04, global 0,72), aunque con renta fija
dice poco y con un R² de 0,79 (concentrada) pierde fiabilidad. Para un no experto, "si el mercado
cae un 10 %, tu cartera tiende a caer un 15 %" es útil; el resto del bloque, no.

## 3. Problemas en los datos y en los cálculos, y fiabilidad real

**Problemas encontrados y cómo se resolvieron:**
- **iShares:**
  - El Excel no es XML válido con nombres como "S&P 500". Se escapa el `&`.
  - El símbolo € llega corrupto. El nombre se toma de la web.
  - Las etiquetas cambian entre fondos ("Fund Base Currency" frente a "Base Currency"). Se aceptan las dos.
  - El CSV de posiciones no trae ISIN, así que la clave es ticker + bolsa. Funciona dentro de iShares, pero no se puede cruzar con otras gestoras.
- **Pesos publicados redondeados a 0,01 %:** en el Global Aggregate (20.000 bonos) la columna suma el **76 %**. Se calcula todo por valor de mercado.
- **Desgloses geográficos de renta fija:** publicados con un mes de retraso respecto a las posiciones. No son comparables y se saltan en la validación.
- **Clase cubierta:**
  - Su desglose oficial suma el 99,40 %; hay un 0,6 % del fondo que no aparece en ningún sitio.
  - Las posiciones muestran los contratos a plazo solo por su valor neto (31 millones en un fondo de 5.386), así que la cobertura real **no se puede calcular**. Se supone del 100 %.
- **Tracking difference de clases cubiertas:** iShares las compara con el índice sin cubrir y en otra divisa (Global Aggregate: −13,85 % frente a −20,43 % en 2021-22). No se muestra.
- **Repartos de los fondos de distribución:** solo están como JSON dentro de la página web. Sin ellos, la rentabilidad de la deuda pública 2025-26 sería −5,49 % en lugar de −3,01 %. Funciona, pero es la pieza más frágil del sistema.
- **NAV con 2 decimales:** en ETFs con NAV de unos 5 € (Global Aggregate, World Small Cap), el redondeo produce diferencias de hasta 0,12 puntos en rentabilidades y de 0,078 en volatilidad. Tolerancias derivadas, no ajustadas.
- **BCE:** su API devolvía errores 500/503 el 5-nov. De ahí la copia local.
- **Saldos negativos de liquidez:** en la concentrada, la divisa euro sale −0,1 % y el dólar 100,1 %. Es correcto contablemente, pero se mostraba como "−0 %" hasta corregirlo.
- **Yahoo Finance:** descartado al principio porque sus términos prohíben el acceso automatizado. Fue una buena decisión: los NAV del gestor dan rentabilidad total y son verificables.

**Fiabilidad por resultado:**

| Resultado | Fiabilidad | Por qué |
|---|---|---|
| País y sector (renta variable) | **Alta** | 19/19 comparaciones válidas con diferencia ≤ 0,006 puntos |
| TER y coste anual | **Alta** | TER contrastado con dos fuentes del gestor (15/15) |
| Rentabilidades en divisa del NAV | **Alta** | 15/15 ETFs × 5 años coinciden con el gestor |
| Volatilidad | **Alta** | 15/15 coinciden con el gestor a 3 años |
| Solapamiento y concentración | **Alta** dentro de iShares | Misma fuente y misma clave de empresa; con otras gestoras habría que rehacer el cruce |
| Divisa | **Media** | Usa la divisa de cotización, no la de los ingresos; las clases cubiertas son un supuesto |
| Rentabilidades en euros | **Media-alta** | Tipo del BCE a las 14:15 frente al NAV al cierre: ruido diario, despreciable a semanas o meses |
| Tracking difference | **Media-alta** | Dato del gestor; no disponible en clases cubiertas |
| Beta | **Media** | Índice aproximado con un ETF (con su TER); sensible al R² |
| Máxima caída | **Correcta, poco representativa** | Un solo episodio y una ventana distinta en cada cartera |
| VaR y pérdida en la cola | **Correctos, poco útiles** | Ver punto 2 |
| Alpha | **Baja** | Intervalos anchos; supone semanas independientes y usa aproximación normal |

**Lo que no está verificado:** la subida real de un CSV desde el navegador y escribir en la tabla
del formulario (la lógica está cubierta por tests, la interfaz no). La beta publicada por iShares
no se puede contrastar, porque es frente a su propio índice y no tenemos esa serie.

## 4. Qué haría distinto si empezara de cero

- **Datos antes que métricas.** Lo primero sería resolver cobertura y licencia:
  - **Cobertura:** los ETFs globales equivalentes de otras gestoras (VWCE de Vanguard, XDWD de
    Xtrackers, MWRD de Amundi) **no están en el universo**. La app los marca como "no cubiertos"
    (comprobado). La propuesta inicial ya anticipaba que esas gestoras y los fondos indexados son
    habituales en España; la auditoría confirma que es el límite principal.
  - **Licencia:** la de iShares impide publicar.
  Habría buscado antes una fuente con derecho de redistribución o planteado desde el inicio una
  herramienta local, en lugar de descubrirlo en el paso 0 con la arquitectura ya diseñada.
- **Una clave de empresa común.** El ISIN de cada posición (o un identificador como FIGI) desde el
  primer día. Con ticker + bolsa, añadir otra gestora obliga a rehacer el cruce de empresas.
- **Menos métricas de riesgo y mejor elegidas.** En lugar de volatilidad + máxima caída + VaR +
  pérdida en la cola + beta + alpha, tendría volatilidad, caída en episodios fijos y comunes
  (2020, 2022) y beta. Habría llegado antes a la conclusión del punto 2 si hubiera ejecutado las
  carteras de prueba al terminar cada métrica, y no al final.
- **La arquitectura sí la repetiría:**
  - el `MetricResult` con estado y cobertura;
  - el motor puro separado de la interfaz;
  - la validación contra el gestor con tolerancias derivadas.

  Son lo mejor del proyecto. Los errores reales (alpha engañoso con bonos, "−0 %", nota de
  cobertura falsa para los bonos) se encontraron al leer resultados reales, no en los tests
  sintéticos: la revisión con datos reales debería formar parte del flujo de cada métrica, y la
  skill `nueva-metrica` ya lo pide.
- **Interfaz:** la mantendría con el resumen primero. Añadiría la comparación lado a lado con una
  cartera de referencia (100 % MSCI ACWI), que hoy solo aparece en una frase del resumen.

## 5. Qué echaría en falta un inversor particular antes que cualquier fase posterior

1. **Sus propios fondos.** Vanguard, Xtrackers, Amundi y los fondos indexados no cotizados
   (MyInvestor, Indexa) quedan fuera. Una cartera con VWCE sale hoy como "no cubierta" en esa
   parte: la app la reconoce como ISIN válido, pero no puede analizar nada de ella. Es lo primero,
   antes de los escenarios o el PDF.
2. **Importar el extracto del bróker.** DEGIRO, Trade Republic o MyInvestor exportan CSV con sus
   propios formatos; escribir ISIN e importes a mano es fricción.
3. **Caídas en crisis comparables** (fase 3 simplificada): "en 2022 tu cartera habría caído un 28 %;
   el World, un 17 %" dice más que todas las métricas de riesgo actuales juntas.
4. **Reparto frente a su propio objetivo.** Si el usuario indica que quiere 70/30, mostrar dónde está
   hoy. Es información, no recomendación, siempre que no diga qué hacer.
5. **Fiscalidad informativa.** Que vender un ETF en España tributa (sin traspasos) y que las clases
   de distribución tributan cada año. Es lo que más condiciona cualquier decisión real.
6. **Datos frescos.** Hoy el snapshot se actualiza a mano; la app debería mostrar su antigüedad de
   forma destacada (ya muestra la fecha) y avisar a partir de un mes.

## 6. Valoración global

**Para qué es útil hoy:**
- Para un inversor con ETFs de iShares que quiere entender qué tiene: cuánto depende del dólar,
  cuánto pesa EE. UU., qué ETFs se solapan y cuánto paga. Ahí es preciso, está validado y lo
  explica bien.
- Como herramienta para aprender: el glosario con cifras reales y los desplegables de cada métrica
  cumplen el objetivo didáctico.
- Como muestra de trabajo: ingesta con problemas reales de datos resueltos, validación contra la
  fuente con tolerancias justificadas y separación motor/interfaz. 219 tests sin red y 67 de
  validación.

**Para qué no es útil todavía:**
- Para la cartera típica de un inversor español (VWCE, fondos indexados): demasiado de ella queda
  sin cubrir.
- Para valorar el riesgo de una cartera con rigor: la máxima caída engaña al comparar, el VaR
  repite la volatilidad y el alpha no dice nada.
- Para cualquier decisión que dependa de la fiscalidad.
- Para enseñarlo públicamente con una URL: sin permiso de BlackRock, solo se puede usar en local, y
  las capturas del README tienen el mismo problema.

**Orden recomendado a partir de aquí:**
1. ~~Quitar o rebajar alpha, VaR y la rentabilidad simulada, y sustituir la máxima caída por
   episodios fijos.~~ Hecho: caídas en 2020 y 2022 frente al MSCI ACWI en la interfaz y el
   resumen; rentabilidad simulada a 5 años y fuera del resumen; máxima caída, VaR y alpha en un
   desplegable de "otras medidas técnicas"; peso en empresas compartidas rebajado a una nota.
2. Ampliar la cobertura a otras gestoras (empezando por Vanguard y Xtrackers) con una clave de
   empresa común.
3. Resolver el permiso de datos o elegir otra fuente.
4. Solo después, las fases 2 y 4.
