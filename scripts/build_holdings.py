"""Download iShares holdings and exposure breakdowns for every fund in the universe.

For each fund: product page (to find the holdings CSV link), holdings CSV and product workbook.
Raw files go to data/raw/ishares/<date>/ (reused if present); the normalised snapshot goes to
data/snapshots/<date>/. Both are git-ignored (licence: personal use only).

Usage:
    python scripts/build_holdings.py                 # download today's files and build
    python scripts/build_holdings.py --from-raw DIR  # rebuild a snapshot from a previous download
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

from radiografia.data.snapshots import SNAPSHOTS_DIR, write_snapshot
from radiografia.data.sources import ishares, ishares_holdings
from radiografia.data.universe import REFERENCE_DIR, load_universe

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "ishares"
PAUSE_SECONDS = 2.0


def _get(path: Path, url: str, offline: bool) -> bytes:
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(path)
    data = ishares.fetch(url)
    path.write_bytes(data)
    time.sleep(PAUSE_SECONDS)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-raw", type=Path, help="reuse a previous download directory")
    args = parser.parse_args()
    offline = args.from_raw is not None
    raw_dir = args.from_raw or RAW_DIR / date.today().isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)

    universe = load_universe()
    with (REFERENCE_DIR / "universe_seed.csv").open(encoding="utf-8", newline="") as handle:
        paths = {row["product_id"]: row["product_path"] for row in csv.DictReader(handle)}

    holdings, breakdowns, manifest, failures = [], [], [], []
    for fund in sorted(universe.funds.values(), key=lambda f: f.isin):
        pid = fund.issuer_product_id
        try:
            page = _get(raw_dir / f"{pid}.html", ishares.product_page_url(paths[pid]), offline)
            csv_url = ishares_holdings.holdings_csv_url(page.decode("utf-8"))
            csv_bytes = _get(raw_dir / f"{pid}_holdings.csv", csv_url, offline)
            workbook = _get(raw_dir / f"{pid}.xls", ishares.workbook_url(pid), offline)

            parsed = ishares_holdings.parse_holdings_csv(csv_bytes.decode("utf-8-sig"))
            exposure = ishares_holdings.parse_exposure_breakdowns(
                ishares.read_worksheet(workbook, "Exposure Breakdowns")
            )
        except Exception as exc:  # report every failing fund, then stop without writing
            failures.append(f"{fund.isin} ({pid}): {exc}")
            continue

        holdings.append(parsed.holdings.assign(isin=fund.isin))
        breakdowns.append(exposure.assign(isin=fund.isin))
        manifest.append(
            {"isin": fund.isin, "holdings_as_of": parsed.as_of, "lines": len(parsed.holdings)}
        )
        sections = ", ".join(
            f"{s} {d:%d-%b}" for s, d in exposure.groupby("section")["as_of"].first().items()
        )
        print(
            f"ok  {fund.isin}  {len(parsed.holdings):>6} lines  as of {parsed.as_of}  |  {sections}"
        )

    if failures:
        print("\nNot written. Failures:\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    target = SNAPSHOTS_DIR / raw_dir.name
    write_snapshot(
        target,
        pd.concat(holdings, ignore_index=True),
        pd.concat(breakdowns, ignore_index=True),
        pd.DataFrame(manifest),
    )
    print(f"\nsnapshot -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
