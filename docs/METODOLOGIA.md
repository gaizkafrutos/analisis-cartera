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

## Por métrica
Cada métrica tendrá: datos de entrada, fórmula, frecuencia y ventana, anualización (si aplica),
supuestos, limitaciones, cómo se valida contra el gestor y tolerancia aceptada.

(Se irá rellenando a partir del paso 4: costes.)
