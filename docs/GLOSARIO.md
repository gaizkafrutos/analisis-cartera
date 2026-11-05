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

**Relacionado:** clase de acumulación / distribución, cobertura de divisa (pendientes).
