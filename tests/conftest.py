"""Shared test setup.

Without RADIOGRAFIA_DATA the app picks real data when a local snapshot exists and the demo when it
does not, so the same test would see different data on a laptop with snapshots and in CI. Every
test starts from "real" (with or without snapshot, as each test expects); tests of the demo, the
SEC mode, the user's files or the automatic default set or clear the variable themselves.

The variable is set for the whole session (module-scoped fixtures, such as the validation
tests' snapshot, are created before function-scoped ones) and again before every test (some
tests run app/demo.py, which changes it for the process).
"""

import pytest

from radiografia.data.datasets import DATASET_ENV


@pytest.fixture(autouse=True, scope="session")
def _real_data_for_the_session():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(DATASET_ENV, "real")
        yield


@pytest.fixture(autouse=True)
def _real_data_by_default(monkeypatch):
    monkeypatch.setenv(DATASET_ENV, "real")
