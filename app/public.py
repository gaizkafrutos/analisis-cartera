"""SEC mode: the app on real, public data that may be redistributed (data/public/).

Each UCITS ETF's composition is that of the US ETF tracking the same index, from SEC Form N-PORT
(public data, see docs/FUENTES_Y_LICENCIAS.md). The public URL serves the synthetic demo
(`app/demo.py`); this mode runs locally:

    .venv\\Scripts\\streamlit run app\\public.py
"""

import os
import runpy
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

try:
    import radiografia  # noqa: F401  (installed with pip install -e . when run locally)
except ModuleNotFoundError:
    # the deployment installs only requirements.txt: use the package from the repository
    sys.path.insert(0, str(APP_DIR.parent / "src"))

os.environ["RADIOGRAFIA_DATA"] = "public"
runpy.run_path(str(APP_DIR / "streamlit_app.py"), run_name="__main__")
