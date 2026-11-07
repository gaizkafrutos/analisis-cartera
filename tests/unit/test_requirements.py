"""requirements.txt (public demo deployment) lists exactly the runtime dependencies of pyproject."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_requirements_match_pyproject():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    requirements = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    assert sorted(requirements) == sorted(pyproject["project"]["dependencies"])
