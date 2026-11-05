---
name: nueva-metrica
description: Flujo para dar de alta una métrica nueva en Radiografía de cartera (volatilidad, máxima caída, VaR, beta, alpha, exposición, solapamiento...). Úsala siempre que se vaya a implementar o rediseñar una métrica del motor. Solo ordena los pasos; las reglas viven en CLAUDE.md.
---

# Nueva métrica

Lista de pasos para añadir una métrica. **Las reglas no están aquí: están en `CLAUDE.md`** (no
inventar datos, lenguaje sin recomendaciones, ingesta offline, cobertura, privacidad). Si algo
de esta lista pareciera contradecir `CLAUDE.md`, manda `CLAUDE.md`.

Lleva un paso del plan por cada punto y no saltes ninguno.

## 1. Explicar antes de programar (y esperar)
Al autor, en pocas líneas y sin jerga:
- **Qué mide.**
- **Cómo se calcula**, con un ejemplo numérico pequeño que se pueda comprobar a mano. Si usa
  datos del universo, cita la fuente y la fecha.
- **Qué decisión ayuda a tomar** a un inversor particular.
- **Trampas habituales**: errores de interpretación y límites de los datos.
- **Cómo se implementará**: datos de entrada, frecuencia, ventana, anualización, qué pasa con
  la parte no cubierta, avisos previstos.

Si la petición contiene un error de concepto financiero, corrígelo aquí. **No escribas código
hasta que el autor confirme que lo ha entendido.**

## 2. Glosario
Entrada nueva (o actualizada) en `docs/GLOSARIO.md` con la plantilla del propio fichero y enlace
en el índice. El ejemplo numérico del paso 1 va en la entrada.

## 3. Tests primero, con datos sintéticos
En `tests/unit/test_<métrica>.py`, como mínimo:
- el ejemplo del paso 1, calculado a mano (el comentario del test muestra la cuenta);
- cobertura parcial (una posición sin datos): la métrica pasa a `PARTIAL` y la parte no
  cubierta nunca se rellena con supuestos;
- nada cubierto: `NOT_AVAILABLE` con `value=None`;
- una propiedad que deba cumplirse siempre (p. ej. coste = TER × importe cubierto);
- si hay intervalo, que contiene el valor central y se ensancha con menos datos.

## 4. Implementar
- En `src/radiografia/analytics/<métrica>.py`, como **función pura** (sin red, ficheros ni
  Streamlit) que devuelve uno o varios `MetricResult` (`domain/metrics.py`).
- Docstring del módulo con fórmula, supuestos y limitaciones.
- Constantes para la clave de la métrica y de cada aviso.
- Rellena `coverage`, `data_as_of`, `window_start`/`window_end` y `observations` cuando apliquen,
  e `interval` cuando la cifra sea inestable (alpha, por ejemplo).

## 5. Textos
En `src/radiografia/reporting/texts.py`: `MetricText` (título, explicación de una línea, cómo se
calcula, limitaciones) y el texto de cada aviso. Deben pasar `tests/unit/test_texts.py`
(describir hechos, nunca recomendar ni nombrar productos alternativos).

## 6. Validar contra el gestor
Si iShares publica la misma cifra (p. ej. `Portfolio Characteristics`: volatilidad y beta a 3
años; `Exposure Breakdowns`: sector y geografía; `Performance Returns`), añade un test en
`tests/validation/` marcado con `@pytest.mark.validation`, que se salte si faltan los datos de
`data/raw/`. La tolerancia se justifica en el test. **Si no cuadra, se informa al autor; no se
amplía la tolerancia para que pase.**

## 7. Metodología
Sección en `docs/METODOLOGIA.md`: datos, fórmula, frecuencia y ventana, supuestos, cobertura,
avisos, validación y resultado de la validación.

## 8. Conectar
Añade la métrica a `AnalysisReport` y a `service.analyze` (`src/radiografia/service.py`). La
interfaz no calcula nada: solo muestra lo que devuelve el servicio.

## 9. Comprobar y entregar
```
.venv\Scripts\ruff format .
.venv\Scripts\ruff check .
.venv\Scripts\python -m pytest -m "not validation"
.venv\Scripts\python -m pytest -m validation     # si hay datos en data/raw/
```
Rama propia, commit con lo que cambia y por qué, PR con el ejemplo calculado a mano y el
resultado de la validación (incluido lo que no cuadra).
