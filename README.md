# Radiografía de cartera

Analizador informativo de carteras de ETFs para inversores particulares en España: qué tienes
realmente (exposición, concentración, solapamiento, costes y riesgo histórico), explicado en
lenguaje claro.

> **No es asesoramiento de inversión.** No predice mercados ni recomienda operaciones.

**Estado:** en construcción. Por ahora solo ETFs UCITS; los fondos indexados no cotizados no
están incluidos.

## Ejecutarla en local

Requiere Python 3.12.

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\streamlit run app\streamlit_app.py
```

Se abre en http://localhost:8501 con una cartera de ejemplo ya cargada (hay tres: global
diversificada, muy concentrada y con fondos solapados). También puedes subir un CSV (formato de
Excel en español o en inglés) o escribir la cartera a mano.

Las secciones de exposición, concentración, solapamiento, rentabilidad y riesgo necesitan los
datos de las gestoras, que no están en el repositorio (ver `docs/FUENTES_Y_LICENCIAS.md`). Se
descargan en local con:

```bash
.venv\Scripts\python scripts\build_holdings.py
.venv\Scripts\python scripts\build_prices.py
```

Sin ellos, la app funciona igual pero esas secciones aparecen como "no disponible".

## Qué muestra

1. **Tu cartera:** ejemplo, CSV o formulario. Los errores (un ISIN con errata, un importe ambiguo)
   se señalan con su fila; los ETFs fuera del universo se marcan como no cubiertos con su peso.
2. **Lo esencial:** un resumen en lenguaje claro, una frase por tema.
3. **En detalle:** costes (TER, coste anual, diferencia con el índice), exposición por país,
   sector y divisa, concentración y solapamiento, y riesgo (volatilidad, máxima caída, VaR, beta,
   alpha con su rango). Cada cifra lleva su explicación de una línea y un desplegable con cómo se
   calcula, sus limitaciones y la fecha del dato.

**Privacidad:** la cartera no se guarda ni se envía a ningún servicio; Streamlit tiene desactivado
el envío de estadísticas de uso (`.streamlit/config.toml`).
