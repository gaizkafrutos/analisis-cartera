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

Se abre en http://localhost:8501 con una cartera de ejemplo ya cargada. También puedes subir un
CSV (formato de Excel en español o en inglés) o escribir la cartera a mano.

**Privacidad:** la cartera no se guarda ni se envía a ningún servicio; Streamlit tiene desactivado
el envío de estadísticas de uso (`.streamlit/config.toml`).
