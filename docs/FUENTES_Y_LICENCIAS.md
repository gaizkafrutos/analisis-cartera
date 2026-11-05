# Fuentes de datos y licencias

Revisión hecha el **5 de noviembre de 2026** (paso 0 del plan). No es asesoramiento jurídico:
resume lo que dicen los términos públicos de cada fuente en esa fecha. Revisar de nuevo antes de
publicar la app y cada vez que se añada una fuente.

## Resumen

| Fuente | Uso previsto | ¿Acceso técnico? | ¿Se puede mostrar en una web pública? | Decisión |
|---|---|---|---|---|
| Yahoo Finance (yfinance) | Precios | Sí, pero prohibido por sus términos | **No** | **Descartada** |
| iShares (BlackRock) | Posiciones, desgloses oficiales, NAV histórico | Sí, CSV y Excel públicos | **No sin autorización escrita** | Fuente principal; pedir permiso |
| Vanguard | Posiciones | Solo con botón en la web (Excel generado en el navegador), datos mensuales | **No sin autorización** | Aplazada |
| BCE | Tipos de cambio, €STR | Sí, API pública (caída el día de la revisión) | **Sí**, citando la fuente | Usar |
| Kenneth French | Factores (fase 3) | Sí, ZIP públicos | Sin licencia declarada | Decidir en fase 3 |

## Yahoo Finance / yfinance — descartada

**Qué dicen los términos** (Términos de servicio de Yahoo, versiones EE. UU. e Irlanda; página de
ayuda de Yahoo Finance sobre proveedores de datos):
- Prohíben acceder o extraer datos de sus servicios con medios automatizados (robots, scrapers)
  sin permiso previo. yfinance es exactamente eso.
- Prohíben reutilizar los servicios con fines comerciales y reproducir, distribuir o mostrar
  públicamente su contenido.
- La página de Yahoo Finance pide expresamente no redistribuir la información que muestra, y
  varios proveedores de datos (LSEG, OTC Markets) añaden sus propias prohibiciones.
- El README de yfinance recuerda que la API de Yahoo es solo para uso personal y remite a los
  términos de Yahoo; la licencia Apache de yfinance cubre el código, no los datos.

**Conclusión:** no se puede usar en la app pública, y su uso automatizado choca con los términos
incluso en local. Además el NAV del gestor es mejor dato (ver iShares). **No se usa yfinance.**

## iShares (BlackRock) — fuente principal, con permiso pendiente

**Qué hay disponible** (comprobado en el producto iShares Core MSCI World, ISIN IE00B4L5Y983):
- CSV de posiciones completas en
  `https://www.ishares.com/uk/individual/en/products/<id>/<slug>/latest-holdings.csv`.
  Responde a una petición HTTP normal (sin navegador). ~1.300 líneas.
  - Columnas: `Ticker, Name, Sector, Asset Class, Market Value, Weight (%), Notional Value,
    Shares, Price, Location, Exchange, Market Currency`. Cabecera con la fecha
    ("Fund Holdings as of").
  - **No trae ISIN.** La clave de cada empresa tiene que ser `Ticker + Exchange` (y el nombre
    como comprobación).
  - Alphabet aparece dos veces (`GOOGL` clase A y `GOOG` clase C): hace falta una tabla que
    agrupe clases de acciones por empresa.
  - Los futuros aparecen con peso 0 pero con valor nocional (exposición real vía derivados).
  - El fichero de la web alemana usa formato numérico alemán y sectores traducidos, y tenía otra
    fecha (04-nov frente a 03-nov en la web británica). **Usar siempre la web británica en
    inglés** y leer la fecha del propio fichero.
- Excel del producto (botón "Download" de la ficha) con hojas: `Holdings`, `Exposure Breakdowns`
  (sector y geografía oficiales), `Historical NAVs` (desde el lanzamiento, 2009 en este caso),
  `Performance Returns`, `Key Facts`, `Portfolio Characteristics`.
  - `Exposure Breakdowns` es justo lo que necesitamos para **validar** nuestro look-through.
  - `Historical NAVs` permite calcular rentabilidades sin Yahoo.
- Repartos de las clases de distribución: van como datos JSON dentro de la ficha web.

**Qué dicen los términos** (Términos y condiciones de iShares UK para inversores particulares,
fechados el 17 de octubre de 2016; la página española redirige a un directorio global):
- La web es para uso personal e interno, no comercial.
- Prohíben vender, copiar, publicar, distribuir, modificar, mostrar o reproducir su contenido, y
  cualquier copia de información o datos requiere aprobación previa de BlackRock Advisors (UK).
- No encontré una cláusula específica sobre acceso automatizado (la página se leyó parcialmente).

**Conclusión:** técnicamente es la mejor fuente posible (oficial, completa, diaria, con desgloses
para validar). Legalmente, **mostrar en una web pública datos derivados de iShares no está
cubierto por sus términos**. Mostrar solo agregados reduce la exposición, pero no la elimina.

## Vanguard — aplazada

- La ficha de los ETFs UCITS (p. ej. FTSE All-World, IE00BK5BQT80) tiene un botón "Download Fund
  Holdings Data" que genera un Excel en el navegador a partir de una API interna (GraphQL). No hay
  una URL estable de descarga.
- Posiciones **a cierre de mes** (el 5 de noviembre mostraba datos a 30 de septiembre): unas
  5 semanas de retraso frente a datos diarios en iShares.
- La tabla visible solo muestra las 10 primeras posiciones y no tiene ISIN, SEDOL ni ticker. No
  descargué el Excel, así que sus columnas están sin verificar.
- Términos (vanguard.co.uk e ie.vanguard): licencia para uso personal, informativo y no
  comercial; prohíben copiar, distribuir, reproducir y publicar sus datos.

**Conclusión:** mismo problema legal que iShares, más difícil de automatizar y con datos más
antiguos. Se queda fuera del MVP, como acordamos.

## BCE — usar

- Política de reutilización de estadísticas del SEBC: acceso y reutilización gratuitos, también
  con fines comerciales, siempre que se cite la fuente (p. ej. "Fuente: estadísticas del BCE") y
  no se modifiquen los datos. Si se transforman (p. ej. convertir NAV a euros), hay que decirlo.
- Los tipos de cambio de referencia del euro se publican con fines informativos y el BCE
  desaconseja usarlos para transacciones. Encaja con una herramienta informativa.
- Series en uso: `EXR` (tipos de cambio diarios, desde el paso 8). `EST` (€STR, desde el paso 9) como tipo sin riesgo para beta y alpha.
- En la app se cita "Fuente: BCE" y se indica que los valores se convierten a euros.
- **Aviso técnico:** la API (`data-api.ecb.europa.eu`) devolvía errores 500/503 el día de la
  revisión. Hay que cachear y mostrar "no disponible" si falla, nunca inventar el dato.

## Kenneth French Data Library — fase 3

- La página tiene un aviso de copyright de Fama y French y **no declara ninguna licencia** ni
  condiciones de reutilización.
- Los datos se construyen a partir de CRSP y Compustat (EE. UU.) y de MSCI y Bloomberg
  (internacional), que son bases de datos con licencia propia.
- Uso académico muy extendido citando la fuente, pero sin permiso explícito para redistribuir.
  Para la fase 3: usar solo para calcular resultados, citar, no publicar los ficheros en bruto,
  y reconsiderar si hace falta pedir permiso.

## Otros
- Los nombres de sectores son la clasificación GICS (marca de MSCI y S&P) y los nombres de
  índices son marcas de sus proveedores. Se usan solo para identificar; citarlo en el README.

## Decisión sobre los datos de la app desplegada

Con lo anterior, la arquitectura de datos queda así:
- **Posiciones, desgloses y NAV:** iShares. **Divisas y tipo libre de riesgo:** BCE.
- **Rentabilidades a partir del NAV del gestor** convertido a euros con el tipo del BCE, no a
  partir del precio de mercado. Supuestos a documentar: el NAV puede diferir algo del precio de
  bolsa (prima/descuento); el NAV se calcula al cierre de EE. UU. y el tipo del BCE se fija a las
  14:15 CET, lo que añade ruido diario (otra razón para usar datos semanales en beta y alpha);
  los ETFs de distribución necesitan sus dividendos para tener rentabilidad total, así que se
  prefieren clases de acumulación en el universo.
- **Índice de referencia:** NAV del iShares MSCI ACWI UCITS ETF, de la misma fuente.
- **Repositorio:** sin datos reales (ya en `.gitignore`).

Queda un punto que no es técnico, sino de permiso, y lo decide el autor:
1. **Pedir autorización escrita a BlackRock** para un proyecto educativo, gratuito y no comercial
   que muestra solo resultados agregados, sin redistribuir sus ficheros. Es la opción limpia.
2. Mientras no haya respuesta (o si es negativa): **código público, datos no**. Cada persona
   ejecuta la app en local y descarga ella misma los datos para su uso personal. La muestra en
   LinkedIn se hace con capturas y un vídeo de la app en local. La URL pública queda en espera.
3. No recomendado: publicar igualmente con datos de iShares confiando en que mostrar solo
   agregados sea tolerado. Contradice lo que dicen sus términos.

## Fuentes consultadas (5-nov-2026)
- Yahoo, Términos de servicio: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html y
  https://legal.yahoo.com/ie/en/yahoo/terms/otos/index.html
- Yahoo Finance, proveedores de datos: https://help.yahoo.com/kb/finance-for-web/SLN2310.html
- yfinance README: https://github.com/ranaroussi/yfinance
- iShares UK, términos: https://www.ishares.com/uk/individual/en/compliance/terms-and-conditions
- iShares Core MSCI World (ficha y CSV):
  https://www.ishares.com/uk/individual/en/products/251882/ishares-msci-world-ucits-etf-acc-fund
- Vanguard UK, ficha FTSE All-World:
  https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating
- Vanguard UK, términos: https://www.vanguard.co.uk/professional/terms-and-conditions
- Vanguard Irlanda, términos: https://www.ie.vanguard/terms-and-conditions
- BCE, política de uso: https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html
- BCE, aviso legal: https://www.ecb.europa.eu/services/disclaimer/html/index.en.html
- BCE, tipos de referencia: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- Kenneth French Data Library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
