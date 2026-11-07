"""Build the synthetic demo dataset in data/demo/ (committed: it contains no third-party data).

Everything here is invented: companies, funds, holdings, prices, issuer returns and the €STR.
It exists so the app can run in public (and the CI can test every section) without iShares data,
whose terms only allow personal use. The app labels it as fictitious on every screen.

What the generator does (fixed seed, so the files only change if this script changes):
    1. ~1,200 fictitious companies: country, sector, trading currency and a market cap drawn from a
       log-normal distribution (bigger for US and technology, like real indices).
    2. Eight fictitious ETFs that hold them by simple rules (all developed markets, the 500
       largest US companies, US technology...), weighted by market cap; two bond funds.
    3. Daily NAVs in EUR from a factor model: region factors (US, other developed, emerging),
       sector factors and bond factors, with two scripted stress periods in 2020 and 2022 so
       the crisis comparison has something to show. Each fund's return is its holdings-weighted
       mix of factors, minus its TER.
    4. "Issuer" 5-year returns for the tracking difference, and a synthetic €STR path.

Usage:
    python scripts/build_demo.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from radiografia.data.snapshots import (
    BREAKDOWNS_FILE,
    CHARACTERISTICS_FILE,
    DISTRIBUTIONS_FILE,
    ESTR_FILE,
    FX_FILE,
    HOLDINGS_FILE,
    MANIFEST_FILE,
    NAVS_FILE,
    PERFORMANCE_FILE,
)
from radiografia.data.universe import write_universe
from radiografia.domain.fund import (
    AssetClass,
    Fund,
    IncomeTreatment,
    Listing,
    Replication,
)
from radiografia.domain.isin import isin_check_digit

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo"
SEED = 2026
START, END = date(2015, 1, 2), date(2026, 11, 4)
PERFORMANCE_AS_OF = date(2026, 10, 31)
GENERATED_ON = date(2026, 11, 7)
PROVENANCE = "sintético: scripts/build_demo.py (semilla 2026)"
CASH_SECTOR = "Cash and/or Derivatives"
FUND_SIZE_EUR = 1e9

# country -> (region, trading currency, share of companies within its region)
DEVELOPED = {
    "United States": ("US", "USD", 0.60),
    "Japan": ("DEV", "JPY", 0.09),
    "United Kingdom": ("DEV", "GBP", 0.06),
    "Canada": ("DEV", "CAD", 0.04),
    "France": ("DEV", "EUR", 0.035),
    "Switzerland": ("DEV", "CHF", 0.03),
    "Germany": ("DEV", "EUR", 0.03),
    "Australia": ("DEV", "AUD", 0.03),
    "Netherlands": ("DEV", "EUR", 0.015),
    "Sweden": ("DEV", "SEK", 0.015),
    "Denmark": ("DEV", "DKK", 0.01),
    "Spain": ("DEV", "EUR", 0.015),
    "Italy": ("DEV", "EUR", 0.015),
}
EMERGING = {
    "China": ("EM", "HKD", 0.30),
    "India": ("EM", "INR", 0.22),
    "Taiwan": ("EM", "TWD", 0.18),
    "Korea (South)": ("EM", "KRW", 0.12),
    "Brazil": ("EM", "BRL", 0.07),
    "Saudi Arabia": ("EM", "SAR", 0.05),
    "South Africa": ("EM", "ZAR", 0.03),
    "Mexico": ("EM", "MXN", 0.03),
}
# sector -> (share of companies in the US, elsewhere, market-cap multiplier)
SECTORS = {
    "Information Technology": (0.22, 0.10, 2.6),
    "Financials": (0.13, 0.20, 1.0),
    "Health Care": (0.12, 0.10, 1.1),
    "Consumer Discretionary": (0.11, 0.11, 1.2),
    "Communication": (0.08, 0.07, 1.6),
    "Industrials": (0.12, 0.15, 0.9),
    "Consumer Staples": (0.06, 0.08, 0.9),
    "Energy": (0.04, 0.06, 0.9),
    "Materials": (0.04, 0.07, 0.7),
    "Utilities": (0.04, 0.03, 0.6),
    "Real Estate": (0.04, 0.03, 0.5),
}
SECTOR_VOL = {s: 0.06 for s in SECTORS} | {"Information Technology": 0.10, "Energy": 0.12}


def demo_isin(n: int) -> str:
    """'ZZ' is a user-assigned ISO code: no real security uses it, so these never collide."""
    first_11 = f"ZZDEMO{n:05d}"
    return first_11 + str(isin_check_digit(first_11))


def companies(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for region_map, count, cap_scale in ((DEVELOPED, 900, 1.0), (EMERGING, 300, 0.35)):
        countries = list(region_map)
        shares = np.array([region_map[c][2] for c in countries])
        picked = rng.choice(countries, size=count, p=shares / shares.sum())
        for country in picked:
            region, currency, _ = region_map[country]
            us = region == "US"
            sector_names = list(SECTORS)
            sector_shares = np.array([SECTORS[s][0 if us else 1] for s in sector_names])
            sector = rng.choice(sector_names, p=sector_shares / sector_shares.sum())
            size = rng.lognormal(mean=0.0, sigma=1.65)
            cap = size * cap_scale * SECTORS[sector][2] * (1.8 if us else 1.0)
            rows.append((country, region, currency, sector, cap))
    df = pd.DataFrame(rows, columns=["location", "region", "market_currency", "sector", "cap"])
    df = df.sort_values("cap", ascending=False, ignore_index=True)
    df["name"] = [f"Empresa ficticia {i + 1:04d}" for i in range(len(df))]
    df["ticker"] = [f"F{i + 1:04d}" for i in range(len(df))]
    return df


def cap_weights(caps: pd.Series, limit: float | None = None) -> pd.Series:
    weights = caps / caps.sum()
    if limit is None:
        return weights
    for _ in range(50):  # cap single names and spread the excess pro rata (like capped indices)
        over = weights > limit
        if not over.any():
            break
        excess = (weights[over] - limit).sum()
        weights[over] = limit
        weights[~over] += excess * weights[~over] / weights[~over].sum()
    return weights


def equity_holdings(isin: str, members: pd.DataFrame, limit: float | None = None) -> pd.DataFrame:
    weights = cap_weights(members["cap"], limit) * 0.996  # 0.4 % in cash, like a real ETF
    lines = members.assign(
        asset_class="Equity",
        exchange="Bolsa ficticia",
        market_value=(weights * FUND_SIZE_EUR).round(2),
    )
    cash = pd.DataFrame(
        [
            {
                "ticker": "EUR",
                "name": "EUR CASH",
                "sector": CASH_SECTOR,
                "asset_class": "Cash",
                "location": "-",
                "exchange": "-",
                "market_currency": "EUR",
                "market_value": round(0.004 * FUND_SIZE_EUR, 2),
            }
        ]
    )
    return _finish(isin, pd.concat([lines, cash], ignore_index=True))


def bond_holdings(
    isin: str, rng: np.random.Generator, currencies: dict[str, float]
) -> pd.DataFrame:
    n = 80
    picked = rng.choice(list(currencies), size=n, p=list(currencies.values()))
    sizes = rng.lognormal(0.0, 0.6, size=n)
    lines = pd.DataFrame(
        {
            "ticker": [f"B{isin[-4:]}{i:03d}" for i in range(n)],
            "name": [f"Bono ficticio {isin[-4:]}-{i:03d}" for i in range(n)],
            "sector": rng.choice(["Treasuries", "Corporates", "Government Related"], size=n),
            "asset_class": "Fixed Income",
            "location": "-",
            "exchange": "-",
            "market_currency": picked,
            "market_value": (sizes / sizes.sum() * 0.99 * FUND_SIZE_EUR).round(2),
        }
    )
    return _finish(isin, lines)


def _finish(isin: str, lines: pd.DataFrame) -> pd.DataFrame:
    lines = lines.assign(notional_value=lines["market_value"], isin=isin)
    lines["weight_published"] = (lines["market_value"] / lines["market_value"].sum()).round(4)
    columns = [
        "ticker",
        "name",
        "sector",
        "asset_class",
        "location",
        "exchange",
        "market_currency",
        "market_value",
        "notional_value",
        "weight_published",
        "isin",
    ]
    return lines[columns]


FUNDS = [
    # number, name, asset class, TER, hedged, benchmark description
    (1, "Demo Acciones Mundo Desarrollado", AssetClass.EQUITY, 0.0020, False),
    (2, "Demo Acciones EE. UU. 500", AssetClass.EQUITY, 0.0007, False),
    (3, "Demo 100 Grandes EE. UU.", AssetClass.EQUITY, 0.0030, False),
    (4, "Demo Tecnología EE. UU.", AssetClass.EQUITY, 0.0015, False),
    (5, "Demo Acciones Emergentes", AssetClass.EQUITY, 0.0018, False),
    (6, "Demo Bonos Gobierno Euro", AssetClass.FIXED_INCOME, 0.0009, False),
    (7, "Demo Bonos Globales (cubierto en EUR)", AssetClass.FIXED_INCOME, 0.0010, True),
    (8, "Demo Mercado Mundial", AssetClass.EQUITY, 0.0020, False),
]
BENCHMARK_NUMBER = 8


def build_holdings(rng: np.random.Generator, firms: pd.DataFrame) -> pd.DataFrame:
    base = ["ticker", "name", "sector", "location", "market_currency", "cap"]
    us = firms[firms["region"] == "US"]
    developed = firms[firms["region"] != "EM"]
    emerging = firms[firms["region"] == "EM"]
    largest_us = us.head(500)
    top_100 = us[us["sector"] != "Financials"].head(100)
    tech = us[us["sector"] == "Information Technology"]
    parts = [
        equity_holdings(demo_isin(1), developed[base]),
        equity_holdings(demo_isin(2), largest_us[base]),
        equity_holdings(demo_isin(3), top_100[base], limit=0.09),
        equity_holdings(demo_isin(4), tech[base], limit=0.20),
        equity_holdings(demo_isin(5), emerging[base]),
        bond_holdings(demo_isin(6), rng, {"EUR": 1.0}),
        bond_holdings(
            demo_isin(7), rng, {"USD": 0.45, "EUR": 0.25, "JPY": 0.12, "GBP": 0.08, "CNY": 0.10}
        ),
        equity_holdings(demo_isin(8), firms[base]),
    ]
    return pd.concat(parts, ignore_index=True)


def business_days() -> pd.DatetimeIndex:
    return pd.bdate_range(START, END)


def _scripted(days: pd.DatetimeIndex, windows: list[tuple[str, str, float]]) -> np.ndarray:
    """Extra daily log-return that moves a factor by `total` (a growth factor) over each window."""
    extra = np.zeros(len(days))
    for start, end, total in windows:
        mask = (days >= start) & (days <= end)
        extra[mask] += np.log(total) / mask.sum()
    return extra


def factor_returns(rng: np.random.Generator, days: pd.DatetimeIndex) -> pd.DataFrame:
    n = len(days)
    vol = np.full(n, 0.12 / np.sqrt(252))
    calm = (days >= "2017-01-01") & (days <= "2017-12-31")
    vol[calm] *= 0.6
    stress = (days >= "2020-02-20") & (days <= "2020-06-30")
    vol[stress] *= 2.0
    vol[(days >= "2022-01-01") & (days <= "2022-12-31")] *= 1.2
    market = (
        0.075 / 252
        + rng.normal(0.0, 1.0, n) * vol
        + _scripted(
            days,
            [
                ("2018-10-01", "2018-12-24", 0.86),
                ("2019-01-02", "2019-12-30", 1.18),
                ("2020-02-20", "2020-03-23", 0.70),
                ("2020-03-24", "2020-08-31", 1.38),
                ("2021-01-04", "2021-12-30", 1.15),
                ("2022-01-04", "2022-10-12", 0.89),
                ("2022-10-13", "2022-12-30", 1.06),
                ("2023-01-02", "2024-12-31", 1.30),
                ("2025-02-19", "2025-04-08", 0.86),
            ],
        )
    )
    factors = {
        "US": market + rng.normal(0.01 / 252, 0.05 / np.sqrt(252), n),
        "DEV": 0.9 * market + rng.normal(-0.015 / 252, 0.06 / np.sqrt(252), n),
        "EM": 1.0 * market + rng.normal(-0.02 / 252, 0.10 / np.sqrt(252), n),
    }
    tech_story = _scripted(
        days,
        [
            ("2020-02-20", "2020-08-31", 1.10),
            ("2022-01-04", "2022-10-12", 0.80),
            ("2023-01-02", "2024-12-31", 1.25),
        ],
    )
    for sector, sector_vol in SECTOR_VOL.items():
        noise = rng.normal(0.0, sector_vol / np.sqrt(252), n)
        factors[sector] = noise + (tech_story if sector == "Information Technology" else 0.0)
    rates = _scripted(
        days, [("2022-01-04", "2022-10-20", 0.84), ("2022-10-21", "2023-12-29", 1.06)]
    )
    factors["BOND_EUR"] = rng.normal(0.012 / 252, 0.045 / np.sqrt(252), n) + rates
    factors["BOND_GLOB"] = rng.normal(0.015 / 252, 0.035 / np.sqrt(252), n) + 0.8 * rates
    return pd.DataFrame(factors, index=days)


def fund_navs(
    rng: np.random.Generator, holdings: pd.DataFrame, factors: pd.DataFrame, regions: dict
) -> pd.DataFrame:
    rows = []
    for number, _, asset_class, ter, _ in FUNDS:
        isin = demo_isin(number)
        lines = holdings[holdings["isin"] == isin]
        weight = lines["market_value"] / lines["market_value"].sum()
        if asset_class is AssetClass.FIXED_INCOME:
            log_r = factors["BOND_EUR" if number == 6 else "BOND_GLOB"]
        else:
            stocks = lines["asset_class"] == "Equity"
            by_region = weight[stocks].groupby(lines.loc[stocks, "location"].map(regions)).sum()
            by_sector = weight[stocks].groupby(lines.loc[stocks, "sector"]).sum()
            log_r = sum(factors[r] * w for r, w in by_region.items()) + sum(
                factors[s] * w for s, w in by_sector.items()
            )
        log_r = log_r + rng.normal(0.0, 0.0004, len(factors)) - ter / 252
        nav = 100 * np.exp(np.cumsum(log_r))
        rows.append(pd.DataFrame({"isin": isin, "date": factors.index, "nav": nav.round(4)}))
    navs = pd.concat(rows, ignore_index=True)
    navs["currency"] = "EUR"
    return navs[["isin", "date", "nav", "currency"]]


def performance(rng: np.random.Generator, navs: pd.DataFrame) -> pd.DataFrame:
    """'Issuer' 5-year annualised returns: fund from its NAV, benchmark = fund + TER +/- noise."""
    end = pd.Timestamp(PERFORMANCE_AS_OF)
    start = end - pd.DateOffset(years=5)
    rows = []
    for number, _, _, ter, hedged in FUNDS:
        if hedged:
            continue  # the app does not show tracking difference for hedged classes
        series = navs[navs["isin"] == demo_isin(number)].set_index("date")["nav"]
        first, last = series.asof(start), series.asof(end)
        fund = (last / first) ** (1 / 5) - 1
        benchmark = fund + ter + rng.normal(0.0, 0.0006)
        rows.append(
            {
                "table": "Annualised",
                "as_of": end.date(),
                "period": "5y",
                "start": start.date(),
                "end": end.date(),
                "fund": round(fund, 4),
                "benchmark": round(benchmark, 4),
                "isin": demo_isin(number),
            }
        )
    return pd.DataFrame(rows)


def estr(days: pd.DatetimeIndex) -> pd.DataFrame:
    """Smooth invented short-rate path (% per year): negative, a fast rise, then a gentle fall."""
    anchors = pd.Series(
        {
            pd.Timestamp("2015-01-02"): -0.30,
            pd.Timestamp("2019-12-31"): -0.55,
            pd.Timestamp("2022-06-30"): -0.55,
            pd.Timestamp("2023-09-30"): 3.90,
            pd.Timestamp("2024-06-30"): 3.90,
            pd.Timestamp("2025-06-30"): 2.00,
            pd.Timestamp("2026-11-04"): 1.90,
        }
    )
    path = anchors.reindex(anchors.index.union(days)).interpolate("time").reindex(days)
    return pd.DataFrame({"date": days, "rate": path.round(3).to_numpy()})


def universe_rows() -> tuple[list[Fund], list[Listing]]:
    funds, listings = [], []
    for number, name, asset_class, ter, hedged in FUNDS:
        isin = demo_isin(number)
        funds.append(
            Fund(
                isin=isin,
                name=name,
                issuer="Demo (ficticio)",
                issuer_product_id=f"demo-{number}",
                asset_class=asset_class,
                asset_class_raw="Equity" if asset_class is AssetClass.EQUITY else "Fixed Income",
                benchmark=f"Índice ficticio {number}",
                ter=ter,
                share_class_currency="EUR",
                base_currency="USD" if hedged else "EUR",
                currency_hedged=hedged,
                income_treatment=IncomeTreatment.ACCUMULATING,
                replication=Replication.PHYSICAL,
                methodology="Replicated",
                domicile="Ficticio",
                fund_launch_date=START,
                share_class_launch_date=START,
                source_url=PROVENANCE,
                retrieved_on=GENERATED_ON,
            )
        )
        listings.append(
            Listing(isin=isin, exchange="Bolsa ficticia", ticker=f"DEMO{number}", currency="EUR")
        )
    return funds, listings


def build(out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write the demo universe and snapshot under `out_dir`; returns (holdings, navs)."""
    rng = np.random.default_rng(SEED)
    firms = companies(rng)
    regions = {c: v[0] for c, v in (DEVELOPED | EMERGING).items()}
    holdings = build_holdings(rng, firms)
    days = business_days()
    navs = fund_navs(rng, holdings, factor_returns(rng, days), regions)

    reference_dir = out_dir / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    write_universe(*universe_rows(), reference_dir)

    snapshot_dir = out_dir / "snapshots" / END.isoformat()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    manifest = (
        holdings.groupby("isin").size().rename("lines").reset_index().assign(holdings_as_of=END)
    )[["isin", "holdings_as_of", "lines"]]
    tables = {
        HOLDINGS_FILE: holdings,
        NAVS_FILE: navs,
        MANIFEST_FILE: manifest,
        PERFORMANCE_FILE: performance(rng, navs),
        ESTR_FILE: estr(days),
        BREAKDOWNS_FILE: _empty("section", "as_of", "label", "code", "weight", "isin"),
        DISTRIBUTIONS_FILE: _empty("ex_date", "amount", "currency", "isin"),
        FX_FILE: _empty("date", "currency", "rate"),
        CHARACTERISTICS_FILE: _empty("label", "value", "as_of", "isin"),
    }
    for name, table in tables.items():
        # LF on every platform and gzip without a timestamp: rebuilding gives the same bytes
        compression = {"method": "gzip", "mtime": 0} if name.endswith(".gz") else None
        table.to_csv(snapshot_dir / name, index=False, lineterminator="\n", compression=compression)
    return holdings, navs


def _empty(*columns: str) -> pd.DataFrame:
    """Header-only table: files the app reads but the demo has nothing for (FX, distributions)."""
    return pd.DataFrame(columns=list(columns))


def main() -> int:
    holdings, navs = build(DEMO_DIR)
    print(f"{holdings['isin'].nunique()} funds, {len(holdings)} holding lines, {len(navs)} NAVs")
    print(f"-> {DEMO_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
