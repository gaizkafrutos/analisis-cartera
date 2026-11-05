"""Add price data to a snapshot: iShares NAV history, published returns and distributions,
plus ECB euro reference rates for every NAV currency other than EUR.

Reads the raw iShares files downloaded by build_holdings.py (same date directory) and downloads
the ECB rates, keeping the raw ECB CSVs in data/raw/ecb/<date>/. Writes into
data/snapshots/<date>/ (git-ignored).

Usage:
    python scripts/build_prices.py                  # latest raw iShares download
    python scripts/build_prices.py --raw-date 2026-11-06
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from radiografia.data.snapshots import SNAPSHOTS_DIR, write_prices
from radiografia.data.sources import ecb, ishares, ishares_prices
from radiografia.data.universe import load_universe

ROOT = Path(__file__).resolve().parents[1]
ISHARES_RAW = ROOT / "data" / "raw" / "ishares"
ECB_RAW = ROOT / "data" / "raw" / "ecb"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-date", help="date directory of the iShares raw download")
    args = parser.parse_args()
    raw_dirs = sorted(p for p in ISHARES_RAW.glob("*") if p.is_dir())
    raw_dir = ISHARES_RAW / args.raw_date if args.raw_date else raw_dirs[-1]

    navs, performance, distributions, failures = [], [], [], []
    for fund in sorted(load_universe().funds.values(), key=lambda f: f.isin):
        pid = fund.issuer_product_id
        try:
            workbook = (raw_dir / f"{pid}.xls").read_bytes()
            page = (raw_dir / f"{pid}.html").read_text(encoding="utf-8")
            currency = ishares_prices.nav_currency(ishares.read_worksheet(workbook, "Fund Header"))
            nav = ishares_prices.parse_historical_navs(
                ishares.read_worksheet(workbook, "Historical NAVs")
            )
            perf = ishares_prices.parse_performance_returns(
                ishares.read_worksheet(workbook, "Performance Returns")
            )
            dist = ishares_prices.parse_distributions(page)
        except Exception as exc:
            failures.append(f"{fund.isin} ({pid}): {exc}")
            continue
        if not dist.empty and set(dist["currency"].dropna()) - {currency}:
            failures.append(f"{fund.isin}: distributions not in NAV currency {currency}")
            continue
        navs.append(
            pd.DataFrame(
                {"isin": fund.isin, "date": nav.index, "nav": nav.to_numpy(), "currency": currency}
            )
        )
        performance.append(perf.assign(isin=fund.isin))
        distributions.append(dist.assign(isin=fund.isin))
        print(
            f"ok  {fund.isin}  {currency}  NAV "
            f"{nav.index.min():%Y-%m-%d}..{nav.index.max():%Y-%m-%d}"
            f"  ({len(nav)})  distributions {len(dist)}"
        )

    if failures:
        print("\nNot written. Failures:\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1

    navs_df = pd.concat(navs, ignore_index=True)
    currencies = sorted(set(navs_df["currency"]) - {"EUR"})
    start, end = navs_df["date"].min().date(), date.fromisoformat(raw_dir.name)
    ecb_dir = ECB_RAW / raw_dir.name
    ecb_dir.mkdir(parents=True, exist_ok=True)
    fx = []
    for currency in currencies:
        path = ecb_dir / f"EXR_{currency}.csv"
        if not path.exists():
            path.write_text(ecb.fetch_exr_csv(currency, start, end), encoding="utf-8")
        rates = ecb.parse_exr_csv(path.read_text(encoding="utf-8"))
        fx.append(
            pd.DataFrame({"date": rates.index, "currency": currency, "rate": rates.to_numpy()})
        )
        print(f"ECB {currency}/EUR  {rates.index.min():%Y-%m-%d}..{rates.index.max():%Y-%m-%d}")

    target = SNAPSHOTS_DIR / raw_dir.name
    write_prices(
        target,
        navs_df,
        pd.concat(performance, ignore_index=True),
        pd.concat(distributions, ignore_index=True),
        pd.concat(fx, ignore_index=True)
        if fx
        else pd.DataFrame(columns=["date", "currency", "rate"]),
    )
    print(f"\nprices -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
