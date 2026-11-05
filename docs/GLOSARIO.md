# Glosario

Conceptos de inversión que usa Radiografía de cartera, explicados para alguien sin formación
financiera. Cada entrada se escribe **antes** de implementar la métrica y se revisa después con
los resultados reales.

> Este glosario es informativo. No es asesoramiento de inversión.

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

(Pendientes: TER, coste anual, look-through, exposición por divisa, solapamiento, volatilidad,
máxima caída, VaR histórico, beta, alpha...)

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
