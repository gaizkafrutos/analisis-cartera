"""Build data/reference/universe.csv and listings.csv from official iShares documents.

For each fund in data/reference/universe_seed.csv this downloads the product page (listings,
hedged flag) and the product workbook (Key Facts), keeps the raw files in data/raw/ (git-ignored,
reused by later ingestion steps) and writes the reference CSVs.

Usage:
    python scripts/build_universe.py                 # download and build
    python scripts/build_universe.py --from-raw DIR  # rebuild from a previous download, offline

Polite access: one request at a time with a pause in between.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

from radiografia.data.sources import ishares
from radiografia.data.universe import REFERENCE_DIR, write_universe

ROOT = Path(__file__).resolve().parents[1]
SEED_FILE = REFERENCE_DIR / "universe_seed.csv"
RAW_DIR = ROOT / "data" / "raw" / "ishares"
PAUSE_SECONDS = 2.0


def _download(product_id: str, product_path: str, target: Path) -> None:
    page = target / f"{product_id}.html"
    workbook = target / f"{product_id}.xls"
    if not page.exists():
        page.write_bytes(ishares.fetch(ishares.product_page_url(product_path)))
        time.sleep(PAUSE_SECONDS)
    if not workbook.exists():
        workbook.write_bytes(ishares.fetch(ishares.workbook_url(product_id)))
        time.sleep(PAUSE_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-raw", type=Path, help="reuse a previous download directory")
    args = parser.parse_args()

    raw_dir = args.from_raw or RAW_DIR / date.today().isoformat()
    retrieved_on = date.fromisoformat(raw_dir.name)
    raw_dir.mkdir(parents=True, exist_ok=True)

    with SEED_FILE.open(encoding="utf-8", newline="") as handle:
        seed = [row for row in csv.DictReader(handle) if row["issuer"] == ishares.ISSUER]

    funds, listings, failures = [], [], []
    for row in seed:
        product_id, product_path = row["product_id"], row["product_path"]
        try:
            if args.from_raw is None:
                _download(product_id, product_path, raw_dir)
            html = (raw_dir / f"{product_id}.html").read_text(encoding="utf-8")
            workbook = (raw_dir / f"{product_id}.xls").read_bytes()
            key_facts = ishares.parse_key_facts(ishares.read_worksheet(workbook, "Key Facts"))
            fund = ishares.fund_from_documents(
                key_facts=key_facts,
                page_title=ishares.parse_page_title(html),
                product_id=product_id,
                product_path=product_path,
                retrieved_on=retrieved_on,
            )
        except Exception as exc:  # report every failing fund, then stop without writing
            failures.append(f"{product_id}: {exc}")
            continue
        funds.append(fund)
        listings.extend(ishares.parse_listings(html, fund.isin))
        print(f"ok  {fund.isin}  {fund.ter:.4%}  {fund.name}")

    if failures:
        print("\nNot written. Failures:\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    write_universe(funds, listings, REFERENCE_DIR)
    print(f"\n{len(funds)} funds, {len(listings)} listings -> {REFERENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
