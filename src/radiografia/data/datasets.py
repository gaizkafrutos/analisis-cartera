"""Which data the app runs on: the real one (iShares + ECB, downloaded locally) or the demo.

The demo is synthetic data built by scripts/build_demo.py and committed in data/demo/. It lets
the app run in public without third-party data (iShares only allows personal use). The choice is
made with the environment variable RADIOGRAFIA_DATA ("real" by default, "demo"); app/demo.py sets
it for the public deployment.

User-facing labels for each dataset live in reporting/texts.py (DATASET_TEXTS).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from radiografia.data.snapshots import SNAPSHOTS_DIR
from radiografia.data.universe import REFERENCE_DIR

ROOT = Path(__file__).resolve().parents[3]
DATASET_ENV = "RADIOGRAFIA_DATA"


class DatasetKey(StrEnum):
    REAL = "real"
    DEMO = "demo"


@dataclass(frozen=True)
class Dataset:
    key: DatasetKey
    reference_dir: Path
    snapshots_dir: Path
    examples_dir: Path
    benchmark_isin: str
    """ETF used as the world equity market: crisis comparison, beta and exposure marks."""

    @property
    def is_demo(self) -> bool:
        return self.key is DatasetKey.DEMO


REAL = Dataset(
    key=DatasetKey.REAL,
    reference_dir=REFERENCE_DIR,
    snapshots_dir=SNAPSHOTS_DIR,
    examples_dir=ROOT / "examples",
    benchmark_isin="IE00B6R52259",  # iShares MSCI ACWI UCITS ETF (decision in CLAUDE.md)
)

DEMO = Dataset(
    key=DatasetKey.DEMO,
    reference_dir=ROOT / "data" / "demo" / "reference",
    snapshots_dir=ROOT / "data" / "demo" / "snapshots",
    examples_dir=ROOT / "examples" / "demo",
    benchmark_isin="ZZDEMO000086",  # "Demo Mercado Mundial" (fictitious), see build_demo.py
)

DATASETS = {dataset.key: dataset for dataset in (REAL, DEMO)}


def current_dataset() -> Dataset:
    """The dataset selected by RADIOGRAFIA_DATA; unknown values are an error, not a fallback."""
    raw = os.environ.get(DATASET_ENV, DatasetKey.REAL).strip().lower()
    try:
        return DATASETS[DatasetKey(raw)]
    except ValueError:
        valid = ", ".join(key.value for key in DatasetKey)
        raise ValueError(f"{DATASET_ENV}={raw!r} is not valid (use one of: {valid})") from None
