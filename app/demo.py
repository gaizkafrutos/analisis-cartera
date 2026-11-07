"""Public demo: the same app on the synthetic data in data/demo/ (no third-party data).

This is the entry point for the public deployment (Streamlit Community Cloud, main file
`app/demo.py`, dependencies from requirements.txt). Locally:

    .venv\\Scripts\\streamlit run app\\demo.py
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

os.environ["RADIOGRAFIA_DATA"] = "demo"
runpy.run_path(str(APP_DIR / "streamlit_app.py"), run_name="__main__")
