# Diseño: la cartera como hoja de mapa topográfico

La interfaz toma la gramática de una hoja del Mapa Topográfico Nacional (IGN, 1:50.000): cada
cifra es un elemento medido, el margen de la hoja dice con qué escala, en qué fecha y con qué
fuentes, y lo que no se ha podido medir aparece rayado, nunca dibujado. Encaja con la regla de
producto de no inventar datos y de enseñar siempre de dónde sale cada número.

Rechaza el tablero oscuro de fintech (tarjetas, acentos neón): la herramienta se usa para
entender con calma, no para vigilar cotizaciones.

## Dónde vive
- `.streamlit/config.toml`: colores del tema, fuentes y tamaños de Streamlit.
- `app/style.css`: lo que el tema no alcanza (cabecera, cartela, leyenda, pestañas, rayado).
- `app/streamlit_app.py`: colores de los gráficos (constantes al principio) y el SVG de curvas de
  nivel de la cabecera, generado en código.
- `app/static/fonts/`: Barlow, autoalojada (SIL Open Font License, `OFL.txt`). La app no pide
  nada a Google Fonts ni a ningún otro servicio mientras se usa.

## Tintas
| Papel | Uso | Valor |
|---|---|---|
| Papel | fondo | `#FCFCFA` |
| Margen | fondos secundarios, bandas de episodios | `#F1EFEA` |
| Planimetría | texto, reglas | `#1C1F22` |
| Texto secundario | notas, etiquetas | `#565B60` (contraste 6,6:1) |
| Curva de nivel (siena) | **tu cartera** en todos los gráficos; acento | `#B5542A` |
| Hidrografía (azul) | **mercado mundial** (MSCI ACWI) en todos los gráficos; enlaces | `#2A6FB0` |
| Vegetación (verde) | reservado para "cubierto" | `#3C7A3B` |
| Carretera (rojo) | solo problemas: errores, partes sin datos (rayado) | `#C62E2E` |
| Regla suave | separadores | `#D9D5CC` |

La pareja siena/azul es fija: el lector aprende una vez que naranja es lo suyo y azul el mercado.

## Tipografía
- **Barlow Condensed** 600-700: títulos y cifras grandes (rotulación de mapa y señalética).
- **Barlow Semi Condensed** 600: etiquetas en mayúsculas con espaciado (rótulos de la cartela,
  métricas, pestañas) y cifras de los gráficos.
- **Barlow** 400-600: texto. Cifras tabulares (`tabular-nums`) donde se comparan números.

## Piezas
- **Cabecera**: título grande condensado, lema y curvas de nivel (cada quinta más gruesa, como
  las curvas maestras); se trazan una vez al cargar salvo con movimiento reducido. Doble regla
  debajo, como el filete de una hoja.
- **Cartela**: el bloque de título de la hoja analizada. Importe, posiciones, barra de
  "analizado" (tinta sólida + rayado rojo para la parte sin datos), fechas, referencia y fuentes.
- **Leyenda**: el resumen, una entrada por tema con su icono (Material Symbols, incluidos en
  Streamlit) y reglas finas entre entradas.
- **Gráficos de exposición**: barra siena para tu cartera y una marca azul vertical para el
  mercado mundial en la misma escala; la cifra siempre después de la barra o la marca.
- **Perfil de caídas** (pestaña Riesgo): cuánto estaba cada día por debajo de su máximo, tu
  cartera con relleno siena y el mercado en línea azul, con 2020 y 2022 sombreados. Lectura
  unificada al pasar el dedo o el ratón.
- **No disponible**: aviso con rayado diagonal, la convención del terreno sin cartografiar.
- **Pestañas**: rótulos de hoja; subrayado propio en siena.

## Reglas
- Sin tarjetas ni sombras: reglas finas y dobles, como en papel.
- El rojo nunca decora: solo errores y partes que faltan.
- El aviso de "no es asesoramiento" se mantiene visible en cada sección (como nota de margen).
- Móvil: columna única; la cartela pasa a etiquetas sobre valores por debajo de 520 px.

## Pendiente
- Las capturas del README son del diseño anterior.
- Revisión de diseño hecha en el propio hilo (dos rondas de capturas en escritorio y móvil); no
  hubo revisor independiente.
