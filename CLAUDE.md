# CLAUDE.md — Radiografía de cartera

## Qué es
Aplicación web informativa para inversores particulares en España que gestionan su propia
cartera de ETFs UCITS (divisa base EUR). Responde a "¿qué tengo realmente?": exposición,
concentración tras look-through, solapamiento, costes y riesgo histórico, con un resumen en
lenguaje claro.

**No** predice mercados, **no** recomienda operaciones ni productos. Es informativa (MiFID II):
cada resultado lleva un aviso visible de que no es asesoramiento.

Proyecto personal con dos fines: aprender finanzas de inversión y servir de muestra pública
(GitHub + LinkedIn) de análisis de datos, producto e IA.

**Alcance del MVP: solo ETFs.** Los fondos indexados no cotizados (muy usados en España por el
régimen de traspasos) quedan fuera; el README debe decirlo con claridad.

## Cómo trabajamos (obligatorio)
- El autor es estudiante de Computación e IA con poca base financiera. Objetivo: entender, no
  solo que funcione.
- **Antes de implementar cada métrica**: explicar en pocas líneas qué mide, cómo se calcula,
  qué decisión ayuda a tomar y sus trampas habituales. Después, implementar.
- Cada concepto explicado se añade o actualiza en `docs/GLOSARIO.md`.
- Si una petición contiene un error de concepto financiero, corregirlo explícitamente antes de
  seguir.
- Motor primero, pero con una pantalla mínima de Streamlit en cuanto funcione la primera métrica
  (costes), para ver el flujo completo pronto y tener material visual de avance.
- No avanzar al siguiente paso del plan sin acuerdo del autor.

## Orden de construcción
Estado: pasos 0 a 13 hechos (MVP completo y auditado, ver AUDITORIA.md). Despliegue público en espera de permiso de BlackRock (solo local).

0. **Licencias y disponibilidad de fuentes** (antes de cualquier commit con datos reales):
   - Revisar términos de Yahoo/yfinance, iShares (BlackRock), Vanguard, BCE y Kenneth French:
     ¿se pueden mostrar sus datos (en bruto o agregados) en una web pública?
   - Verificar si Vanguard publica posiciones de sus ETFs UCITS en formato descargable.
   - Decidir cómo obtiene los datos la app desplegada (ver "Datos en el despliegue").
   - Resultado en `docs/FUENTES_Y_LICENCIAS.md`.
1. Esqueleto: `pyproject`, `uv`, `ruff`, `pytest`, CI, `.gitignore`, glosario vacío.
2. Entrada de cartera: CSV/formulario, validación de ISIN (dígito de control), importes → pesos.
3. Universo inicial de ~15 ETFs de **iShares** (metadatos transcritos con fuente y fecha).
4. **Costes**: TER ponderado y coste anual en €.
5. **Pantalla mínima de Streamlit**: subir cartera → costes. Solo presentación.
6. Ingesta de posiciones de iShares + validación contra los desgloses publicados por la gestora.
7. Look-through, exposiciones (geografía, sector, divisa), concentración, solapamiento.
8. Rentabilidades en EUR a partir del NAV histórico de iShares convertido con tipos del BCE,
   validadas contra la hoja `Performance Returns` del propio gestor.
9. Riesgo: volatilidad, máxima caída, VaR histórico; después beta y alpha con intervalo.
10. Resumen en lenguaje claro (plantillas) y avisos.
11. Interfaz completa con flujo guiado, revisada en móvil.
12. Tres carteras de ejemplo de extremo a extremo (concentrada, global, solapada), README con
    capturas/GIF, despliegue.
13. `AUDITORIA.md`.

Ampliaciones condicionadas: Vanguard solo si el paso 0 confirma posiciones descargables; otras
gestoras (Xtrackers, Amundi) solo si sus ficheros son usables. Universo hasta 50-100 ETFs cuando
el flujo con 15 funcione.

## Fases del producto
1. **MVP (en curso)**: lo anterior.
2. Escenarios condicionales con rangos de incertidumbre (nunca una cifra única).
3. Backtest en crisis (2000-02, 2008, 2020, 2022) con índices o factores proxy.
4. Informe PDF.

No implementar 2-4 todavía, pero no cerrar puertas (ver "Puntos de extensión").

## Arquitectura
```
fuentes externas ──► scripts/ (ingesta) ──► snapshots normalizados con fecha (fuera de git)
                                                         │
                       src/radiografia/                  ▼
   domain/      modelos (pydantic): Portfolio, Position, Fund, MetricResult, AnalysisReport;
                ISIN; UniverseIndex
   input/       lectura y validación de la cartera del usuario (CSV/formulario), pura, sin I/O
   data/        adaptadores por fuente + repositorio que lee snapshots
   analytics/   cálculos puros (pandas/numpy), sin I/O
   reporting/   textos, explicaciones, avisos y resumen en lenguaje claro
   service.py   analyze(portfolio) -> AnalysisReport   ← único punto de entrada
                                                         │
   app/ (Streamlit) ── solo presentación ────────────────┘   (futuro: FastAPI llama a service.py)
```

### Reglas de arquitectura
- **La interfaz no contiene lógica de análisis.** `app/` solo llama a `service.analyze()` y pinta
  el `AnalysisReport`. Si en `app/` aparece un cálculo, se mueve al motor. Esto vale también
  para la pantalla mínima del paso 5.
- `analytics/` son funciones puras: entran DataFrames/modelos, salen resultados. Sin red, sin
  ficheros, sin Streamlit. Esto es lo que se testea.
- `AnalysisReport` es serializable a JSON (pydantic) para poder exponerlo por FastAPI o generar
  un PDF (fase 4) sin tocar el motor.
- Cada métrica devuelve un `MetricResult` con: valor, unidad, intervalo de incertidumbre
  (opcional), ventana temporal y nº de observaciones, **cobertura** (% de la cartera con datos
  para ese cálculo y % "no cubierto" con motivo), avisos/limitaciones y la clave de su
  explicación.
- Los textos para el usuario (explicación de una línea, metodología, limitaciones) viven en un
  único sitio en `reporting/` y se reutilizan en UI y documentación.
- El acceso a datos va a través de snapshots normalizados (`data/snapshots.py`): cada fuente es
  un script de `scripts/` que escribe ese formato, y el motor solo lee snapshots. Así se cambia
  de fuente según lo que permitan las licencias. Las interfaces `PriceSource` y
  `HoldingsSource` no existen todavía: crearlas cuando haya una segunda fuente real.

## Renta fija (alcance reducido en el MVP)
- Todo ETF se clasifica por tipo de activo: renta variable, renta fija, otros.
- Las métricas de look-through (concentración, solapamiento, sector, geografía por empresa) solo
  se calculan para renta variable. La renta fija aparece como "no cubierto" con el porcentaje de
  cartera afectado.
- Las métricas basadas en precios (volatilidad, máxima caída, VaR, beta) sí incluyen la renta
  fija, porque solo necesitan la serie del ETF.
- Duración, calidad crediticia y desglose de emisores: fuera del MVP.

## Reglas de datos (no negociables)
- **No inventar datos ni composiciones.** Si falta algo: valor `None`, estado `no_disponible` y
  motivo. Nunca rellenar con supuestos silenciosos.
- Todo dato de referencia lleva **procedencia**: fuente y fecha (`source`, `as_of`).
- El TER y demás metadatos del universo se transcriben de documentos oficiales del gestor
  (KID/factsheet) con columna de fuente y fecha.
- Las exposiciones calculadas se contrastan con las que publica cada gestor. Si no cuadran
  dentro de la tolerancia documentada, **se informa**; no se amplía la tolerancia para que pase.
- ETFs de réplica sintética (swap): su fichero de posiciones es la cesta de colateral, no la
  exposición real. No usar ese fichero para look-through; marcarlo como no cubierto.

## Qué va al repositorio
- **Sí**: código, scripts de ingesta, `data/reference/universe.csv` (metadatos transcritos con
  fuente), fixtures **pequeñas o sintéticas** para tests, carteras de ejemplo, documentación.
- **No** (en `.gitignore`): snapshots reales de posiciones y precios (`data/raw/`,
  `data/snapshots/`). Un dato subido a un repo público queda en el historial de git aunque se
  borre después.
- Revisar `git status` antes de cada commit que toque `data/`.

## Fuentes de datos (paso 0 hecho, ver `docs/FUENTES_Y_LICENCIAS.md`)
- **iShares** (web británica en inglés): CSV `latest-holdings.csv` de posiciones y Excel de la
  ficha (hojas `Holdings`, `Exposure Breakdowns`, `Historical NAVs`, `Performance Returns`).
  - Sin ISIN: clave de empresa = `Ticker + Exchange`; tabla propia para agrupar clases de
    acciones (Alphabet `GOOGL`/`GOOG`). Futuros con peso 0 y nocional ≠ 0.
  - `Exposure Breakdowns` es la referencia oficial para validar el look-through.
  - `Key Facts` alimenta el universo; `Portfolio Characteristics` publica volatilidad y beta a
    3 años, útiles para validar el paso 9.
  - Posiciones: `latest-holdings.csv` (trae país y bolsa; la hoja `Holdings` del Excel no).
    Pesos por valor de mercado: la columna de peso publicada está redondeada a 0,01 %.
  - Resultados de la validación y discrepancias conocidas: `docs/VALIDACION.md`.
  - Rarezas conocidas del Excel (`&` sin escapar, `€` corrupto, etiquetas que varían): ver
    `docs/METODOLOGIA.md`, "Universo de fondos".
- **BCE**: tipos de cambio (`EXR`) y €STR (`EST`). Citar "Fuente: BCE" e indicar que los datos
  se transforman. La API puede fallar: cachear y marcar "no disponible".
- **yfinance descartado**: los términos de Yahoo prohíben el acceso automatizado y la
  redistribución. Las rentabilidades salen del NAV del gestor.
- **Vanguard aplazado**: posiciones mensuales, sin URL estable, mismos límites legales.
- **Kenneth French**: sin licencia declarada; decidir en la fase 3.

## Datos en el despliegue (pendiente de permiso)
Los términos de iShares limitan su web a uso personal y no comercial y piden autorización
previa para reproducir o mostrar sus datos. Hasta tener autorización escrita de BlackRock:
código público, datos no; la app se ejecuta en local y cada usuario descarga los datos.

## Skills, conectores y herramientas externas
- No instalar skills, conectores ni MCP de terceros en el proyecto sin decisión del autor. Si
  alguno ayudaría, proponerlo indicando nombre, autor y qué hace; el autor decide tras leer su
  `SKILL.md`.
- Ninguna skill genérica prevalece sobre este archivo: lenguaje sin recomendaciones, no inventar
  datos e ingesta offline se mantienen siempre.
- Descartado cualquier MCP o herramienta que consulte Yahoo/yfinance (ver
  `docs/FUENTES_Y_LICENCIAS.md`).
- Skill propia `nueva-metrica` (`.claude/skills/nueva-metrica/SKILL.md`): úsala para cada
  métrica nueva. Solo ordena los pasos; las reglas siguen siendo las de este archivo.

## Privacidad
- Las carteras de usuario **no se guardan**: ni en disco, ni en base de datos, ni en logs, ni en
  analítica. Todo se procesa en memoria dentro de la sesión.
- No se envían datos de la cartera a servicios externos.

## Regulación y lenguaje
- Nunca "deberías", "te recomendamos", "vende/compra". Describir hechos de la cartera.
- No nombrar productos alternativos concretos (sería acercarse a una recomendación).
- Aviso de "no es asesoramiento" visible en cada sección de resultados y en el resumen.

## Tests
- Cada cálculo tiene tests con datos sintéticos cuyo resultado se conoce a mano.
- Tests de validación contra datos publicados por el gestor (exposiciones, rentabilidades
  anuales de factsheet), con tolerancia documentada y justificada. Si dependen de snapshots
  reales (fuera de git), se marcan y se saltan cuando no están disponibles.
- Tests de extremo a extremo con las carteras de ejemplo de `examples/`.
- Los tests no dependen de la red.
- La interfaz se prueba sin navegador con `streamlit.testing.v1.AppTest` (`tests/e2e/test_app.py`).
  AppTest no puede escribir en `st.data_editor`: el formulario se prueba fijando
  `session_state["form_rows"]`, que es lo que guarda el botón "Analizar".
- Streamlit solo recarga el script de la app: tras cambiar el paquete `radiografia`, reiniciar el
  servidor.

## Convenciones
- Python 3.12, `pyproject.toml` estándar, layout `src/`, entorno `.venv` con `pip` (compatible
  con `uv` si se instala). `ruff` (lint + formato), `pytest`.
- Dependencias de ejecución solo cuando un paso las necesita; no añadir librerías "por si acaso".
- Identificadores, docstrings y comentarios en inglés. Interfaz, `docs/` y glosario en español.
- Pesos internos como fracciones (0–1); porcentajes solo en presentación.
- Todo en EUR. Rentabilidades simples para agregar activos en la cartera.
- Supuestos de cada métrica (frecuencia, anualización, ventana, rebalanceo) documentados en el
  docstring y en `docs/METODOLOGIA.md`.

## Puntos de extensión (fases 2-4)
- Un snapshot de precios con otro origen permite añadir índices largos o factores (Kenneth
  French) en la fase 3.
- `MetricResult` ya admite intervalos: los escenarios (fase 2) usan la misma estructura.
- `AnalysisReport` serializable → PDF (fase 4) y API (FastAPI).

## Decisiones
| Tema | Decisión | Estado |
|---|---|---|
| Nombre | Radiografía de cartera (paquete `radiografia`) | tomada |
| Interfaz MVP | Streamlit; motor independiente listo para FastAPI | tomada |
| Flujo de la interfaz | 1. Tu cartera → 2. Lo esencial (resumen) → 3. En detalle (pestañas Costes, Exposición, Concentración, Riesgo); listas en vez de tablas anchas; gráficos de barras plotly | tomada |
| Diseño visual | Hoja de mapa topográfico (`DESIGN.md`): papel claro, siena = tu cartera, azul = mercado mundial, rojo solo para problemas, rayado = sin datos; fuente Barlow autoalojada (OFL), sin peticiones externas | tomada sin el autor (6-nov-2026), revisable |
| Productos | Solo ETFs UCITS en el MVP; fondos indexados fuera (indicarlo en README) | tomada |
| Gestoras | iShares primero; Vanguard solo si publica posiciones UCITS descargables | tomada |
| Universo | ~15 ETFs para el flujo completo; ampliar a 50-100 después | tomada |
| Renta fija | Clasificación por tipo de activo; look-through solo renta variable; resto "no cubierto" con % | tomada |
| Índice de referencia | MSCI ACWI vía ETF que lo replica en EUR (MSCI World como alternativa) | tomada |
| Resumen | Plantillas deterministas a partir de resultados calculados; solo frases con dato disponible; comparación solo con el MSCI ACWI | tomada |
| Riesgo histórico | Pesos actuales constantes aplicados al pasado (no es la rentabilidad real del usuario) | tomada |
| Beta/alpha | Semanales, 5 años, frente al iShares MSCI ACWI en EUR, sobre el €STR (BCE); alpha con intervalo al 95 % | tomada |
| Alpha con poca renta variable | Si la renta variable es < 80 % de la parte cubierta, el alpha no se muestra (sería engañoso) | tomada |
| Ventanas de riesgo | 5 años para volatilidad, VaR, beta y alpha; toda la historia para la máxima caída | tomada |
| Caídas para comparar | Episodios fijos 2020 y 2022 junto al MSCI ACWI; la máxima caída de toda la ventana, el VaR y el alpha quedan en "otras medidas técnicas" y fuera del resumen (AUDITORIA.md) | tomada |
| VaR | Histórico, 95 %, 1 día, con pérdida esperada en la cola | tomada |
| Divisa de clases cubiertas | 100 % en la divisa de cobertura (supuesto avisado; las posiciones no permiten calcularla) | tomada |
| Tracking difference | Dato de la gestora a 5 años; no se muestra en clases cubiertas | tomada |
| Rentabilidad histórica | Solo como contexto en riesgo, simulada, últimos 5 años (misma ventana para todas las carteras), con aviso; nunca proyectada ni en el resumen | tomada |
| Renta fija en divisa | Se incluye en la exposición por divisa; no en empresas, país ni sector | tomada |
| Datos reales en git | No: snapshots en `.gitignore`; solo fixtures pequeñas/sintéticas | tomada |
| Precios/rentabilidades | NAV de iShares + tipos de cambio del BCE; yfinance descartado | tomada |
| Datos en el despliegue | Pedir autorización a BlackRock; mientras tanto, solo ejecución local | pendiente del autor |
| Licencia del código | MIT (`LICENSE`); no cubre datos de terceros (sección "Licencia" del README) | tomada (6-nov-2026) |
| Cifras de iShares en README y docs | Se mantienen como ejemplos puntuales, con aviso de procedencia y fecha en cada documento; nada de tablas completas de posiciones | tomada (6-nov-2026) |
| Repositorio | GitHub privado hasta decidir licencia y datos | tomada |
| Entrada: ISIN fuera del universo | ISIN válido pero desconocido no es error: "no cubierto" con su % de cartera | tomada |
| Entrada: ISIN inválido | Formato o dígito de control incorrecto = error que el usuario debe corregir | tomada |
| Entrada: importe | Valor de mercado actual en EUR (no precio de compra); la interfaz lo dice | tomada |

## Diseño
Ver `DESIGN.md` (tintas, tipografía, piezas) y `PRODUCT.md` (contexto de producto para las
herramientas de diseño). Los colores se repiten en `.streamlit/config.toml`, `app/style.css` y las
constantes de `app/streamlit_app.py`: si cambia uno, cambian los tres.

## Comandos (Windows; en Linux/macOS usar `.venv/bin/`)
```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff check .
.venv\Scripts\ruff format .
.venv\Scripts\python -m pytest -m "not validation"   # lo mismo que la CI
.venv\Scripts\python -m pytest -m validation         # requiere snapshots reales locales
.venv\Scripts\streamlit run app\streamlit_app.py      # app en http://localhost:8501
.venv\Scripts\python scripts\build_universe.py        # descarga iShares y regenera data/reference
.venv\Scripts\python scripts\build_universe.py --from-raw data\raw\ishares\AAAA-MM-DD  # sin red
.venv\Scripts\python scripts\build_holdings.py        # posiciones + desgloses -> data/snapshots/
.venv\Scripts\python scripts\build_prices.py          # NAV, repartos, rentabilidades, BCE
.venv\Scripts\python -m pytest -m validation -rsx     # validación contra el gestor (VALIDACION.md)
```
Tras regenerar el universo, revisar el diff de `data/reference/` antes de hacer commit (un cambio
de TER es un cambio real del gestor y se menciona en el commit).
