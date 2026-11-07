"""After a deployment changes the package's files, the app loads the new code.

Runs in a separate Python process: dropping the package from sys.modules inside the test run
would leave other tests holding objects of the old modules.
"""

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

SCRIPT = """
import sys
import radiografia
from radiografia.reload import refresh_if_changed
from radiografia.reporting import presentation as before

assert refresh_if_changed() is False          # first call records the files' stamp
assert refresh_if_changed() is False          # nothing changed
radiografia._source_stamp -= 1                # as if a deployment had touched a file
assert refresh_if_changed() is True
from radiografia.reporting import presentation as after
assert after is not before                    # the package was imported again
assert sys.modules["radiografia"]._source_stamp > 0
print("ok")
"""


def test_changed_files_are_imported_again():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
