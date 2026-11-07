"""Which data the app runs on: real (iShares + ECB, local), public (SEC twins) or the demo.

- real: iShares files downloaded by each user for personal use (git-ignored), exact.
- public: the same UCITS universe, but each ETF's composition is that of the US ETF tracking the
  same index, from SEC Form N-PORT (public data, committed in data/public/). Approximate and
  labelled as such; lets the app show real data in public (iShares only allows personal use).
- demo: synthetic data built by scripts/build_demo.py (data/demo/), for tests and as fallback.

The choice is made with the environment variable RADIOGRAFIA_DATA ("real" by default); app/public.py
and app/demo.py set it.

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
    PUBLIC = "public"


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

PUBLIC = Dataset(
    key=DatasetKey.PUBLIC,
    reference_dir=REFERENCE_DIR,  # the same UCITS universe as the real data
    snapshots_dir=ROOT / "data" / "public" / "snapshots",
    examples_dir=ROOT / "examples",
    benchmark_isin="IE00B6R52259",  # MSCI ACWI, through its US twin (scripts/build_public.py)
)

DATASETS = {dataset.key: dataset for dataset in (REAL, DEMO, PUBLIC)}


def current_dataset() -> Dataset:
    """The dataset selected by RADIOGRAFIA_DATA; unknown values are an error, not a fallback."""
    raw = os.environ.get(DATASET_ENV, DatasetKey.REAL).strip().lower()
    try:
        return DATASETS[DatasetKey(raw)]
    except ValueError:
        valid = ", ".join(key.value for key in DatasetKey)
        raise ValueError(f"{DATASET_ENV}={raw!r} is not valid (use one of: {valid})") from None
