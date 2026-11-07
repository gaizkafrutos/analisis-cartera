# Product

<!-- impeccable:product-schema 1 -->

> Escrito sin entrevista: el autor estaba ausente y pidió avanzar solo. Todo sale de `CLAUDE.md`,
> `README.md` y `AUDITORIA.md`; lo inferido va marcado con *(inferido)*.

## Platform

web

## Users
Inversores particulares en España que gestionan su propia cartera de ETFs UCITS en euros, con
poca formación financiera. Llegan con una lista de ETFs y lo que vale cada uno en su bróker, y
quieren saber qué tienen realmente. Muchos lo consultan en el móvil *(inferido de la regla de
diseño móvil)*. Público secundario: quien revisa el proyecto como muestra de trabajo (GitHub,
LinkedIn).

## Product Purpose
Responder a "¿qué tengo realmente?": abre cada ETF, suma lo que hay dentro y explica en lenguaje
claro dónde está el dinero (país, sector, divisa, empresas), cuánto se repite entre ETFs, cuánto
cuesta y cuánto se ha movido en el pasado. Éxito: el usuario entiende algo de su cartera que no
sabía, y entiende de dónde sale cada cifra.

## Positioning
Cada cifra lleva su explicación de una línea, su método, su periodo, su fecha de datos y la parte
de la cartera que cubre; lo que no se puede calcular sale como "no disponible", nunca estimado.
Validado contra lo que publica la propia gestora. Siempre comparado con un único punto neutro:
el mercado mundial de acciones (MSCI ACWI).

## Operating Context
Se usa una vez y de vez en cuando (al revisar la cartera, al pensar en comprar otro ETF), no a
diario *(inferido)*. Entrada: cartera de ejemplo, CSV exportado del bróker o formulario. Se
ejecuta en local: los datos de iShares no pueden mostrarse en una web pública sin permiso.

## Capabilities and Constraints
- Streamlit (Python) como interfaz; el motor está separado y la interfaz solo presenta.
- Universo cerrado de 18 ETFs (15 de iShares, uno de Xtrackers, Amundi y SPDR); los bonos no se abren.
- Gráficos con plotly. Sin almacenamiento de carteras ni analítica.
- Regulación (MiFID II): informativo; nunca recomienda comprar, vender ni productos concretos.
  Aviso de "no es asesoramiento" visible en cada sección de resultados.

## Brand Commitments
- Nombre: "Radiografía de cartera". Lema: "Qué tienes realmente en tu cartera de ETFs, explicado
  sin jerga."
- Todo en español, tuteo, frases cortas, sin jerga o con la jerga explicada.

## Evidence on Hand
Tres carteras de ejemplo (`examples/`), validación contra la gestora (`docs/VALIDACION.md`),
glosario con cifras reales (`docs/GLOSARIO.md`). No hay usuarios, testimonios ni métricas de uso:
no se deben inventar.

## Product Principles
1. Describir, nunca recomendar.
2. No inventar: un dato que falta se ve como que falta.
3. Cada cifra con su explicación y su letra pequeña a un clic.
4. Una sola referencia neutra para comparar: el mercado mundial.
5. Aprender es parte del producto.

## Accessibility & Inclusion
Legible en móvil (≥ 16 px de cuerpo, objetivos táctiles amplios); contraste AA; colores de los
gráficos distinguibles sin depender solo del tono *(inferido)*.
