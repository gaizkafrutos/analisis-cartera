# Despliegue de la demo y comprobaciones antes de publicar

La web pública sirve **solo la demo** (`app/demo.py`): datos sintéticos de `data/demo/` y la
opción de subir tus propios ficheros de la gestora, que se leen en memoria. Nunca descarga nada
mientras se usa y no contiene datos de terceros. Los datos reales (iShares descargados con los
scripts, modo SEC) solo se usan en local. Motivo en
[FUENTES_Y_LICENCIAS.md](FUENTES_Y_LICENCIAS.md).

## Qué usa el despliegue

| Fichero | Para qué |
|---|---|
| `app/demo.py` | Punto de entrada: fija `RADIOGRAFIA_DATA=demo` y ejecuta la app |
| `requirements.txt` | Dependencias de ejecución (las mismas que `pyproject.toml`; un test lo comprueba) |
| `.streamlit/config.toml` | Tema, fuentes servidas desde `app/static`, subidas hasta 10 MB, sin estadísticas de uso |
| `data/demo/` | Datos sintéticos (regenerables con `scripts/build_demo.py`) |
| `data/reference/` | Universo de 18 ETFs (para el modo de ficheros subidos) |

No hace falta ningún secreto ni variable de entorno.

## Pasos (Streamlit Community Cloud, gratuito)

**La app ya existe** en [radiografia-cartera.streamlit.app](https://radiografia-cartera.streamlit.app)
y se redepliega sola cada vez que cambia `main`. Tras fusionar una PR:

1. Abre la URL y espera a que termine de arrancar (la primera carga tras un cambio tarda uno o
   dos minutos).
2. Comprueba: el sello «Demo · datos ficticios»; que «¿Con qué datos?» ofrece solo «Demo con
   datos ficticios» y «Tus ficheros de la gestora» (nunca «Tus datos locales»); que se abre
   «Acerca de los datos» al final de la página; y una cartera de ejemplo hasta la pestaña Riesgo.
3. Si algo falla: en [share.streamlit.io](https://share.streamlit.io), menú ⋮ de la app →
   «Reboot» la reinicia; «Manage app» (abajo a la derecha en la propia web) muestra el registro.

**Reiniciar tras ciertos cambios.** Streamlit Cloud aplica cada commit sin reiniciar la app.
Desde el 7-nov-2026 la app vuelve a cargar el paquete `radiografia` si sus ficheros cambian
(`src/radiografia/reload.py`); antes de eso, un cambio del paquete dejó la web con un
`ImportError` hasta reiniciarla. Los cambios de `.streamlit/config.toml` (por ejemplo, el límite
de subida) y de `requirements.txt` siguen necesitando «Reboot».

**Si hubiera que crearla de nuevo:**

1. Entra en [share.streamlit.io](https://share.streamlit.io) con la cuenta de GitHub.
2. «Create app» → «Deploy a public app from GitHub».
3. Repositorio `gaizkafrutos/analisis-cartera`, rama `main`, fichero principal `app/demo.py`.
4. «App URL»: `radiografia-cartera` (si está libre).
5. «Advanced settings»: Python **3.12**; sin secretos.
6. «Deploy». Después, el paso 2 de arriba.

**Privacidad en la web:** los ficheros que sube un visitante se procesan en los servidores de
Streamlit Community Cloud, en memoria y solo durante su sesión; la app no los guarda ni los envía
a ningún otro servicio. El alojamiento se rige por las condiciones de Streamlit.

## Lista de comprobación antes de publicar

Revisada el 7-nov-2026 sobre todo el historial de git (57 commits, todas las ramas).

| Comprobación | Resultado |
|---|---|
| Datos reales en el historial (`data/raw/`, `data/snapshots/`, ficheros de posiciones o Excel de gestoras) | Ninguno; `.gitignore` los excluye. Única excepción conocida: las capturas antiguas de abajo |
| Capturas con datos de iShares | Los commits `1691ae7` y `cdab091` (6-nov-2026) tienen capturas y GIF hechos con datos de iShares; desde `c2574fb` las capturas son de la demo. **Decisión del autor:** dejarlas en el historial o reescribirlo |
| Claves, contraseñas, tokens | Ninguno en el historial; la app no necesita secretos |
| Rutas locales del ordenador | Ninguna en el historial |
| `.env` | No existe; añadido a `.gitignore` por si se usa para `SEC_USER_AGENT` |
| `git status` antes del commit que toque `data/` | Revisar siempre; `data/public/` (SEC) y `data/demo/` sí van al repositorio |
| Licencias y avisos | MIT en `LICENSE`; README, "Licencia": no cubre datos de terceros; aviso de procedencia de las cifras de iShares; Barlow con su OFL |
| Correos en los commits | Hay commits con dos direcciones personales del autor y con la `noreply` de GitHub; los nuevos usan la `noreply`. Cambiar los antiguos exige reescribir el historial: decisión del autor |
| Aviso de no asesoramiento | Visible en cada sección de resultados y en el resumen |
