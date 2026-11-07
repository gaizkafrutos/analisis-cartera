"""Import the package's current code after a deployment updates its files in place.

Streamlit re-runs the app script on every interaction but keeps already imported modules in
memory. Streamlit Community Cloud pulls each new commit into the running app without
restarting it, so after an update the new script met the old package and failed (ImportError
of a new function, 7-nov-2026). The app calls `refresh_if_changed()` before importing anything
else from the package: if any of its source files changed since it was imported, the package
is dropped from `sys.modules` and the imports that follow load the new code.

Changes to `.streamlit/config.toml` still need a restart ("Reboot app"), see docs/DESPLIEGUE.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = "radiografia"
_STAMP = "_source_stamp"


def source_stamp(root: Path | None = None) -> float:
    """Latest modification time of the package's Python files."""
    root = root or Path(__file__).resolve().parent
    return max(path.stat().st_mtime for path in root.rglob("*.py"))


def refresh_if_changed() -> bool:
    """Drop the package from memory if its files changed since import. True if it did."""
    package = sys.modules[PACKAGE]
    stamp = source_stamp()
    previous = getattr(package, _STAMP, None)
    if previous is None:
        setattr(package, _STAMP, stamp)
        return False
    if previous == stamp:
        return False
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
        del sys.modules[name]
    fresh = __import__(PACKAGE)
    setattr(fresh, _STAMP, stamp)
    return True
