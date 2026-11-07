"""Which data the app runs on.

- real: iShares files downloaded by each user for personal use (git-ignored), exact.
- upload: the same universe, with holdings taken only from the iShares files the user uploads in
  the session (kept in memory, never stored); no prices, so no risk section.
- public ("modo SEC"): the same universe, but each ETF's composition is that of the US ETF
  tracking the same index, from SEC Form N-PORT (public data, committed in data/public/).
  Approximate and labelled as such.
- demo: synthetic data built by scripts/build_demo.py (data/demo/), for tests and the public URL.

Default: the environment variable RADIOGRAFIA_DATA if set (app/demo.py and app/public.py set it);
otherwise real when a local snapshot exists and the demo when it does not, so a fresh clone or a
deployment without data opens on the demo instead of an empty analysis. In the app, each session
can switch between the selectable datasets (`selectable`).

User-facing labels for each dataset live in reporting/texts.py (DATASET_TEXTS).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from radiografia.data.snapshots import SNAPSHOTS_DIR, latest_snapshot_dir
from radiografia.data.universe import REFERENCE_DIR

ROOT = Path(__file__).resolve().parents[3]
DATASET_ENV = "RADIOGRAFIA_DATA"


class DatasetKey(StrEnum):
    REAL = "real"
    DEMO = "demo"
    PUBLIC = "public"
    UPLOAD = "upload"


@dataclass(frozen=True)
class Dataset:
    key: DatasetKey
    reference_dir: Path
    snapshots_dir: Path | None
    """None: no stored snapshot (the upload dataset builds one in memory per session)."""
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

UPLOAD = Dataset(
    key=DatasetKey.UPLOAD,
    reference_dir=REFERENCE_DIR,  # the same universe: names, TER and asset class of each ETF
    snapshots_dir=None,
    examples_dir=ROOT / "examples",
    benchmark_isin="IE00B6R52259",  # only compared with if the user uploads its file too
)

DATASETS = {dataset.key: dataset for dataset in (REAL, DEMO, PUBLIC, UPLOAD)}


def has_snapshot(dataset: Dataset) -> bool:
    root = dataset.snapshots_dir
    return root is not None and latest_snapshot_dir(root) is not None


def current_dataset() -> Dataset:
    """RADIOGRAFIA_DATA if set (unknown values are an error, not a fallback); otherwise real with
    a local snapshot and the demo without one."""
    raw = os.environ.get(DATASET_ENV, "").strip().lower()
    if not raw:
        return REAL if has_snapshot(REAL) else DEMO
    try:
        return DATASETS[DatasetKey(raw)]
    except ValueError:
        valid = ", ".join(key.value for key in DatasetKey)
        raise ValueError(f"{DATASET_ENV}={raw!r} is not valid (use one of: {valid})") from None


def selectable(initial: Dataset) -> tuple[Dataset, ...]:
    """Datasets a session can switch to: the initial one first, local real data when present,
    the demo and the user's own files. The SEC mode is offered only where it was chosen
    (app/public.py): the public URL serves the demo."""
    options = [initial]
    if has_snapshot(REAL):
        options.append(REAL)
    options += [DEMO, UPLOAD]
    return tuple(dict.fromkeys(options))
