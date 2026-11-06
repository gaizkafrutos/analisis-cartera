# Herramientas parecidas: qué hacen y qué aprender de ellas

Revisión hecha el 6-nov-2026 a partir de sus páginas públicas (no se han probado con cuenta).
Sirve para no reinventar lo que ya existe, copiar buenas ideas sin copiar productos y ver
errores que conviene evitar.

## Qué hay

| Herramienta | Qué muestra | Datos | Notas |
|---|---|---|---|
| Morningstar Portfolio X-Ray | Regiones, 12 sectores, estilo, estadísticas, y "Stock Intersection": cada empresa que está en dos o más fondos, con su valor y su peso | Base de datos propia de Morningstar | La referencia histórica del look-through. La versión gratuita (Instant X-Ray) ya no está disponible según terceros; su página de Reino Unido redirige a un aviso de cambios en la suscripción. |
| NWCA Portfolio X-Ray (se presenta como sustituto gratuito) | Reparto antes y después de abrir los fondos, geografía por exposición económica (no domicilio), sectores GICS, solapamiento, TER ponderado frente a un índice pasivo con coste anual, 30 mayores posiciones | Varias fuentes (iShares, justETF, extraETF...), en caché 24 h | Entrada por ISIN e importe, sin registro. Sin riesgo ni escenarios. No dice qué hace con lo que no cubre. |
| PortfolioPilot | Look-through en donuts por país, sector y empresa, con vista en dinero o en riesgo; al pasar el ratón dice qué fondos aportan cada trozo; solapamiento; escenarios de crisis (2008, 2020) aparte | Ficheros regulatorios de EE. UU. | Solo EE. UU. y Canadá. Es un asesor registrado: su modelo es recomendar. |
| myetfjourney Portfolio X-Ray | Sectores, solapamiento, impacto de comisiones a 10-30 años (suponiendo un 8 % anual), beta ponderada, "huecos" sectoriales y una nota de diversificación de 1 a 10 | Ficheros de las gestoras, actualizados en junio de 2026 | Solo tickers de EE. UU. Aviso de "solo educativo". |
| Sharesight | Informe de exposición a lo que hay dentro de los ETFs | No lo dice | De pago por encima de 10 posiciones. |
| Vanguard (asesores) | Escenarios de estrés: 2008, ciclos de subidas de tipos, aranceles, choques hipotéticos; compara carteras lado a lado | Modelos propios | Solo para profesionales. |
| myfinancetools.io | Desglose por país y región de ETFs UCITS | No lo dice | Gratis con 2 ETFs. |

En español no aparece ninguna herramienta que junte solapamiento, país, divisa, costes y riesgo
para ETFs UCITS. Ese es el hueco de este proyecto.

## Ideas que encajan (y cómo se han usado)
1. **Comparar siempre con un índice neutro** (NWCA compara el TER con un índice pasivo;
   PortfolioPilot y Vanguard comparan escenarios). Ya era la regla del resumen; ahora también se
   ve en los gráficos de exposición (marca azul del MSCI ACWI) y en las caídas por episodio.
2. **Crisis con nombre en vez de una única máxima caída** (Vanguard, PortfolioPilot): aplicado
   con 2020 y 2022, más un perfil diario de caídas de todo el periodo.
3. **Qué fondos aportan cada empresa** (Morningstar "Stock Intersection", PortfolioPilot al pasar
   el ratón): ya se dice en las 10 mayores empresas ("en 2 de tus ETFs"). Pendiente: mostrar el
   peso que aporta cada ETF.
4. **Entrada por ISIN e importe, sin registro** (NWCA): igual que aquí.
5. **Fecha de los datos siempre visible**: ahora en la cartela de cada análisis.

## Errores que conviene no copiar
- **Notas o puntuaciones de diversificación** (myetfjourney, 1 a 10): resumen opaco, invita a
  "mejorar la nota" y se acerca a una recomendación. Aquí, cifras con su explicación.
- **Proyecciones con una rentabilidad supuesta** (impacto de comisiones al 8 % anual): convierte
  una hipótesis en un número que parece un hecho. Si algún día se muestra el efecto de las
  comisiones en el tiempo, que sea con varios escenarios y diciendo que son supuestos.
- **No decir qué queda fuera**: ninguna de las páginas revisadas explica qué hace con un fondo
  que no puede abrir. Aquí cada sección dice qué parte de la cartera cubre.
- **Geografía por domicilio presentada como exposición real**: NWCA dice usar exposición
  económica. Aquí el país es el domicilio de cada empresa y la limitación está escrita; obtener
  ingresos por región necesitaría otra fuente de datos.

## Fuentes
- [Morningstar Portfolio X-Ray (Reino Unido)](https://www.morningstar.co.uk/uk/xray/overview)
- [Free Morningstar X-Ray Replacement for European Investors](https://tianning-lab.github.io/free-morningstar-xray-replacement.html)
- [myetfjourney Portfolio X-Ray](https://myetfjourney.com/tools/portfolio-xray)
- [PortfolioPilot, look-through analysis](https://portfoliopilot.com/portfolio-management/look-through-analysis)
- [Sharesight ETF tracker](https://sharesight.com/eu/etf-tracker)
- [Vanguard, portfolio stress testing](https://advisors.vanguard.com/strategies/portfolio-strategies/portfolio-analysis/stress-testing)
- [myfinancetools.io, análisis de ETFs](https://myfinancetools.io/es/features/etf-analysis/)
- [Morningstar Canadá, "dangerous (portfolio) intersections"](https://morningstar.ca/ca/news/185439/caution-beware-of-dangerous-(portfolio)-intersections.aspx) (redirige a la portada; no se pudo leer)
