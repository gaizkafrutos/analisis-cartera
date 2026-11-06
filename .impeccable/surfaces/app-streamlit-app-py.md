---
version: 1
slug: "app-streamlit-app-py"
primary_target: "app/streamlit_app.py"
related_targets: []
---

# Surface brief: app/streamlit_app.py

Scope: the whole Streamlit app (input, summary, detail tabs). Mode: Operate.
Audience: Spanish self-directed ETF investors with little finance background, often on a phone.
Job: enter a portfolio, read what it really holds, follow any figure to its method and source.
Constraints: Streamlit widgets (styled through theme + one CSS layer), plotly charts, no external
requests at runtime (fonts self-hosted), MiFID disclaimer visible in every results section.
Unattended run: the author was away; direction taken from the roll without a decision round.

## Direction contract

THESIS: The portfolio as a surveyed map sheet (IGN 1:50.000 tradition): every figure is a
measured feature with its scale, date and source in the sheet margin, and what could not be
surveyed is hatched, never drawn in. Refuses the default dark fintech dashboard of cards and
neon accents.

OWN-WORLD: White map paper, black planimetry ink for text, contour sienna for "tu cartera",
hydrography blue for "mercado mundial", vegetation green only for "cubierto", road red reserved
for problems (errors, not covered). Hairline rules, condensed signage lettering for headings and
labels, tabular figures, diagonal hatch for unsurveyed (not covered) parts.

STORY: The visitor reads the sheet title cartouche (what, when, from where), the legend (the
plain summary), then zooms into each sheet (tabs). They believe the figures because the margin
always says how they were measured and what is missing.

FIRST VIEWPORT: Masthead with a contour-line band drawn as hairlines; large condensed title left,
cartouche box right (escala = portfolio total, fecha de datos, fuentes, cobertura bar with hatch).
Input controls directly below, primary action is choosing/entering the portfolio.

FORM: Topographic map sheet; candidate 6 of 7 on the ordered list; seed key 9d076f18. Raises:
from the gate board, one alert colour reserved for change/problem states and tabular figures;
from the one-size timetable, rank carried by weight, case and rule more than size; from the metro
tiles, chrome deleted so type and rule are the interface. Signature interaction: the risk tab's
"perfil" (elevation-profile style chart of distance below the previous peak, portfolio vs world
market, 2020 and 2022 shaded) with a unified hover reading both values on a date.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
