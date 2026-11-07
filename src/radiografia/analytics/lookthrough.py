"""Look-through: open every ETF and add up what is inside, weighted by the portfolio.

    weight of X in the portfolio = sum over ETFs (weight of the ETF x weight of X inside the ETF)

where X is a company, a country, a sector or a currency. Results are fractions of the covered
part of the portfolio; `coverage` says how much of the whole portfolio that is.

What is covered (CLAUDE.md, "Renta fija"):
    - Companies, countries, sectors, concentration and overlap: equity ETFs of the universe with
      physical replication and holdings in the local snapshot.
    - Currency: the same equity ETFs plus fixed-income ETFs with holdings, and currency-hedged
      fixed-income classes even without holdings (their currency is the hedge currency).
    - Sector: only funds whose holdings report a sector (SEC N-PORT files do not).
    - Everything else is reported as not covered, with its weight and reason. Never guessed.

Assumptions and limitations (also in docs/METODOLOGIA.md):
    - Holdings are a dated snapshot (`data_as_of`); funds trade and rebalance afterwards.
    - Holding weights come from market value (see fund_breakdown). Futures count as 0.
    - Cash, money-market funds and derivatives form one 'Cash and/or Derivatives' bucket for
      country and sector; for currency each line counts in its own currency.
    - Currency-hedged share classes count 100 % in their hedge currency (share class currency,
      or base currency when the issuer does not publish it). This follows the fund's stated
      objective, not its holdings: the holdings file shows the hedging forwards only at their
      net value, not the amount they hedge.
    - Currency is the currency each security trades in, not where the company earns revenue.
    - Country is the one the issuer assigns (mostly domicile), not where the company sells.
    - Share classes of one company are merged by name ('ALPHABET CLASS A' / 'CLASS C' ->
      'ALPHABET') within the same country. Reliable inside one issuer's files only.
    - Public dataset: a fund's holdings may be those of a US 'twin' ETF tracking the same
      index (SEC N-PORT). Each such fund is listed in `proxies` and every result says so.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Mapping
from datetime import date
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, ConfigDict

from radiografia.analytics.company_names import PREFERRED_ISSUER, company_keys
from radiografia.analytics.fund_breakdown import CASH_LABEL, holding_weights, is_cash_like
from radiografia.domain.fund import AssetClass, Fund, Replication
from radiografia.domain.metrics import (
    BreakdownItem,
    BreakdownResult,
    Coverage,
    MetricResult,
    MetricStatus,
    Unit,
)
from radiografia.domain.portfolio import CoverageStatus, Portfolio

GEOGRAPHY = "geography"
SECTOR = "sector"
CURRENCY = "currency"
TOP10_WEIGHT = "top10_weight"
EFFECTIVE_COMPANIES = "effective_companies"
SHARED_COMPANIES_WEIGHT = "shared_companies_weight"

TOP_COMPANIES = 10

WARNING_COUNTRY_IS_DOMICILE = "country_is_domicile"
WARNING_CURRENCY_IS_TRADING_CURRENCY = "currency_is_trading_currency"
WARNING_HEDGED_CLASSES_ASSUMED = "hedged_classes_assumed"
WARNING_LOOKTHROUGH_PARTIAL = "lookthrough_partial_coverage"
WARNING_HOLDINGS_ARE_A_SNAPSHOT = "holdings_are_a_snapshot"
WARNING_CONCENTRATION_IS_DESCRIPTIVE = "concentration_is_descriptive"
WARNING_OVERLAP_IS_NOT_A_PROBLEM_BY_ITSELF = "overlap_is_not_a_problem_by_itself"
WARNING_HOLDINGS_FROM_TWIN = "holdings_from_twin"
WARNING_SECTOR_NOT_PUBLISHED = "sector_not_published"

_SHARE_CLASS_SUFFIX = re.compile(r"\s+CLASS\s+[A-Z]$")


class UncoveredReason(StrEnum):
    OUTSIDE_UNIVERSE = "outside_universe"
    FIXED_INCOME_NOT_LOOKED_THROUGH = "fixed_income_not_looked_through"
    OTHER_ASSET_CLASS = "other_asset_class"
    SYNTHETIC_REPLICATION = "synthetic_replication"
    HOLDINGS_NOT_AVAILABLE = "holdings_not_available"


class UncoveredPosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    weight: float
    """Fraction of the whole portfolio."""
    reason: UncoveredReason
    in_currency_breakdown: bool


class CompanyExposure(BaseModel):
    model_config = ConfigDict(frozen=True)

    company: str
    country: str
    weight: float
    """Fraction of the covered (equity) part of the portfolio."""
    fund_isins: tuple[str, ...]


class OverlapPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    isin_a: str
    isin_b: str
    overlap: float
    """Sum over companies of min(weight in A, weight in B), with weights inside each fund."""


class ProxyNote(BaseModel):
    """A UCITS ETF whose composition is approximated by a US ETF tracking the same index."""

    model_config = ConfigDict(frozen=True)

    isin: str
    fund_name: str
    ucits_index: str
    us_ticker: str
    us_name: str
    us_index: str
    exact_index: bool
    note: str | None = None
    holdings_as_of: date


class LookThroughResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    geography: BreakdownResult
    sector: BreakdownResult
    currency: BreakdownResult
    top_companies: tuple[CompanyExposure, ...]
    top10_weight: MetricResult
    effective_companies: MetricResult
    shared_companies_weight: MetricResult
    shared_companies_count: int
    companies_count: int = 0
    """Distinct companies held through the equity ETFs (share classes merged)."""
    overlaps: tuple[OverlapPair, ...]
    uncovered: tuple[UncoveredPosition, ...]
    proxies: tuple[ProxyNote, ...] = ()
    """Funds of this portfolio whose holdings come from a US twin ETF (public dataset)."""
    asset_mix: dict[str, float] = {}
    """Share of the recognised part of the portfolio by the funds' asset class (equity,
    fixed_income, other), from the universe: it does not depend on having holdings files."""


def company_key(name: str) -> str:
    """'ALPHABET CLASS A' -> 'ALPHABET'. Merges share classes of the same company."""
    return _SHARE_CLASS_SUFFIX.sub("", name.strip())


def _classify(fund: Fund | None, has_holdings: bool) -> tuple[bool, bool, UncoveredReason | None]:
    """(equity look-through?, currency?, reason when not equity-covered)."""
    if fund is None:
        return False, False, UncoveredReason.OUTSIDE_UNIVERSE
    if fund.replication is Replication.SYNTHETIC:
        return False, False, UncoveredReason.SYNTHETIC_REPLICATION
    if not has_holdings and fund.asset_class is AssetClass.FIXED_INCOME and fund.currency_hedged:
        return False, True, UncoveredReason.FIXED_INCOME_NOT_LOOKED_THROUGH
    if not has_holdings:
        return False, False, UncoveredReason.HOLDINGS_NOT_AVAILABLE
    if fund.asset_class is AssetClass.EQUITY:
        return True, True, None
    if fund.asset_class is AssetClass.FIXED_INCOME:
        return False, True, UncoveredReason.FIXED_INCOME_NOT_LOOKED_THROUGH
    return False, False, UncoveredReason.OTHER_ASSET_CLASS


def _status(covered_weight: float) -> MetricStatus:
    if covered_weight <= 0:
        return MetricStatus.NOT_AVAILABLE
    return MetricStatus.AVAILABLE if covered_weight >= 1 - 1e-12 else MetricStatus.PARTIAL


def _coverage(portfolio: Portfolio, covered_weight: float) -> Coverage:
    covered_amount = covered_weight * portfolio.total_eur
    return Coverage(
        covered_weight=covered_weight,
        covered_amount_eur=covered_amount,
        not_covered_amount_eur=portfolio.total_eur - covered_amount,
    )


def _breakdown(
    key: str,
    exposures: pd.Series,
    portfolio: Portfolio,
    covered_weight: float,
    data_as_of: date | None,
    warnings: list[str],
) -> BreakdownResult:
    status = _status(covered_weight)
    items: tuple[BreakdownItem, ...] = ()
    if status is not MetricStatus.NOT_AVAILABLE:
        normalised = (exposures / exposures.sum()).sort_values(ascending=False)
        items = tuple(BreakdownItem(label=str(k), weight=float(v)) for k, v in normalised.items())
    if status is MetricStatus.PARTIAL:
        warnings = [*warnings, WARNING_LOOKTHROUGH_PARTIAL]
    return BreakdownResult(
        key=key,
        items=items,
        status=status,
        coverage=_coverage(portfolio, covered_weight),
        data_as_of=data_as_of if items else None,
        warnings=tuple(warnings) if items else (),
    )


def _metric(
    key: str,
    value: float | None,
    unit: Unit,
    portfolio: Portfolio,
    covered_weight: float,
    data_as_of: date | None,
    warnings: list[str],
) -> MetricResult:
    status = _status(covered_weight) if value is not None else MetricStatus.NOT_AVAILABLE
    if status is MetricStatus.PARTIAL:
        warnings = [*warnings, WARNING_LOOKTHROUGH_PARTIAL]
    available = status is not MetricStatus.NOT_AVAILABLE
    return MetricResult(
        key=key,
        value=value if available else None,
        unit=unit,
        status=status,
        coverage=_coverage(portfolio, covered_weight if available else 0.0),
        data_as_of=data_as_of if available else None,
        warnings=tuple(warnings) if available else (),
    )


def compute_lookthrough(
    portfolio: Portfolio,
    funds: Mapping[str, Fund],
    holdings: pd.DataFrame | None,
    holdings_as_of: Mapping[str, date],
    proxies: Mapping[str, ProxyNote] | None = None,
) -> LookThroughResult:
    """`holdings`: snapshot holdings of all funds (column `isin`); None if there is no snapshot.

    `proxies`: funds whose holdings are those of a US twin ETF (public dataset only).
    """
    proxies = proxies or {}
    available = set(holdings["isin"].unique()) if holdings is not None else set()

    equity_lines, currency_lines, uncovered, used_proxies = [], [], [], []
    equity_weight = currency_weight = sector_weight = 0.0
    hedged_used = False
    dates: list[date] = []
    mix: dict[str, float] = {}

    for position in portfolio.positions:
        fund = funds.get(position.isin) if position.isin else None
        if position.coverage is not CoverageStatus.COVERED:
            fund = None
        if fund is not None:
            mix[fund.asset_class.value] = mix.get(fund.asset_class.value, 0.0) + position.weight
        equity, currency, reason = _classify(fund, position.isin in available)
        if reason is not None:
            uncovered.append(
                UncoveredPosition(
                    label=fund.name if fund else " / ".join(position.identifiers),
                    weight=position.weight,
                    reason=reason,
                    in_currency_breakdown=currency,
                )
            )
        if not (equity or currency):
            continue

        if position.isin in available:
            lines = holdings[holdings["isin"] == position.isin].copy()
            lines["w"] = holding_weights(lines) * position.weight
            lines["issuer"] = fund.issuer
            dates.append(holdings_as_of[position.isin])
            if position.isin in proxies:
                used_proxies.append(proxies[position.isin])

        if currency:
            currency_weight += position.weight
            if fund.currency_hedged:
                hedged_used = True
                hedge_currency = fund.share_class_currency or fund.base_currency
                currency_lines.append(pd.Series({hedge_currency: position.weight}))
            else:
                currency_lines.append(lines.groupby("market_currency")["w"].sum())
        if equity:
            equity_weight += position.weight
            equity_lines.append(lines)
            if lines["sector"].notna().any():
                sector_weight += position.weight

    data_as_of = min(dates) if dates else None

    if equity_lines:
        eq = _same_company_across_issuers(pd.concat(equity_lines, ignore_index=True))
        equity_lines = [lines for _, lines in eq.groupby("isin", sort=False)]
        cash = is_cash_like(eq)
        country = eq["location"].where(~cash, CASH_LABEL)
        sector = eq["sector"].where(~cash, CASH_LABEL)
        geography_series = eq["w"].groupby(country).sum()
        # funds that publish no sector at all are left out of the sector breakdown
        with_sector = eq.groupby("isin")["sector"].transform(lambda s: s.notna().any())
        sector_series = eq.loc[with_sector, "w"].groupby(sector[with_sector]).sum()
        companies = eq[~cash].assign(company=eq.loc[~cash, "name"].map(company_key))
    else:
        geography_series = sector_series = pd.Series(dtype=float)
        companies = pd.DataFrame(columns=["company", "location", "w", "isin"])
    currency_series = (
        pd.concat(currency_lines).groupby(level=0).sum()
        if currency_lines
        else pd.Series(dtype=float)
    )

    snapshot_warning = [WARNING_HOLDINGS_ARE_A_SNAPSHOT]
    if used_proxies:
        snapshot_warning.append(WARNING_HOLDINGS_FROM_TWIN)
    sector_warnings = list(snapshot_warning)
    if sector_weight < equity_weight - 1e-12:
        sector_warnings.append(WARNING_SECTOR_NOT_PUBLISHED)
    currency_warnings = [*snapshot_warning, WARNING_CURRENCY_IS_TRADING_CURRENCY]
    if hedged_used:
        currency_warnings.append(WARNING_HEDGED_CLASSES_ASSUMED)

    top, top10, effective, shared_weight, shared_count = _concentration(companies, equity_weight)
    common = (portfolio, equity_weight, data_as_of)
    return LookThroughResult(
        geography=_breakdown(
            GEOGRAPHY,
            geography_series,
            *common,
            [*snapshot_warning, WARNING_COUNTRY_IS_DOMICILE],
        ),
        sector=_breakdown(
            SECTOR, sector_series, portfolio, sector_weight, data_as_of, sector_warnings
        ),
        currency=_breakdown(
            CURRENCY, currency_series, portfolio, currency_weight, data_as_of, currency_warnings
        ),
        top_companies=top,
        top10_weight=_metric(
            TOP10_WEIGHT,
            top10,
            Unit.FRACTION,
            *common,
            [*snapshot_warning, WARNING_CONCENTRATION_IS_DESCRIPTIVE],
        ),
        effective_companies=_metric(
            EFFECTIVE_COMPANIES,
            effective,
            Unit.RATIO,
            *common,
            [*snapshot_warning, WARNING_CONCENTRATION_IS_DESCRIPTIVE],
        ),
        shared_companies_weight=_metric(
            SHARED_COMPANIES_WEIGHT,
            shared_weight,
            Unit.FRACTION,
            *common,
            [*snapshot_warning, WARNING_OVERLAP_IS_NOT_A_PROBLEM_BY_ITSELF],
        ),
        shared_companies_count=shared_count,
        companies_count=0
        if companies.empty
        else companies.groupby(["company", "location"]).ngroups,
        overlaps=_overlaps(equity_lines),
        uncovered=tuple(uncovered),
        proxies=tuple(dict.fromkeys(used_proxies)),
        asset_mix={k: v / sum(mix.values()) for k, v in mix.items()} if mix else {},
    )


def _same_company_across_issuers(eq: pd.DataFrame) -> pd.DataFrame:
    """When the portfolio mixes issuers, give each company one name and one country in every
    fund (rules in analytics/company_names.py); with a single issuer, lines are unchanged."""
    if eq["issuer"].nunique() <= 1:  # noqa: PD101
        return eq
    stocks = ~is_cash_like(eq)
    lines = eq[stocks]
    keys = company_keys(lines)
    preferred = (lines["issuer"] == PREFERRED_ISSUER).astype(int)
    representative = (
        lines.assign(key=keys, preferred=preferred)
        .sort_values(["preferred", "w"], ascending=False)
        .drop_duplicates("key")
        .set_index("key")
    )
    eq = eq.copy()
    eq.loc[stocks, "name"] = keys.map(representative["name"]).to_numpy()
    country = keys.str.rsplit("|", n=1).str[1]
    eq.loc[stocks, "location"] = country.where(country != "-", None).to_numpy()
    return eq


def _concentration(
    companies: pd.DataFrame, equity_weight: float
) -> tuple[tuple[CompanyExposure, ...], float | None, float | None, float | None, int]:
    """Top companies, top-10 weight, effective number (1/HHI), weight and count of shared ones."""
    if companies.empty or equity_weight <= 0:
        return (), None, None, None, 0
    keys = ["company", "location"]
    # vectorised aggregation (a per-company Python lambda took ~0.1 s for 4,000 companies);
    # the list of funds is only built for the companies that are shown
    grouped = companies.groupby(keys).agg(w=("w", "sum"), funds=("isin", "nunique"))
    grouped["w"] = grouped["w"] / equity_weight
    grouped = grouped.sort_values("w", ascending=False)

    head = grouped.head(TOP_COMPANIES)
    in_head = companies.set_index(keys).index.isin(head.index)
    isins = companies[in_head].groupby(keys)["isin"].unique()
    top = tuple(
        CompanyExposure(
            company=name,
            country=country,
            weight=float(row.w),
            fund_isins=tuple(sorted(isins[(name, country)])),
        )
        for (name, country), row in head.iterrows()
    )
    shares = grouped["w"] / grouped["w"].sum()
    effective = float(1.0 / (shares**2).sum())
    shared = grouped[grouped["funds"] > 1]
    return (
        top,
        float(grouped["w"].head(TOP_COMPANIES).sum()),
        effective,
        float(shared["w"].sum()),
        len(shared),
    )


def _overlaps(equity_lines: list[pd.DataFrame]) -> tuple[OverlapPair, ...]:
    """Pairwise overlap using each fund's own company weights (cash excluded, not rescaled)."""
    per_fund = {}
    for lines in equity_lines:
        isin = lines["isin"].iloc[0]
        weights = holding_weights(lines)
        stocks = ~is_cash_like(lines)
        keys = lines.loc[stocks, "name"].map(company_key) + "|" + lines.loc[stocks, "location"]
        per_fund[isin] = weights[stocks].groupby(keys).sum()
    pairs = []
    for a, b in itertools.combinations(sorted(per_fund), 2):
        joined = pd.concat([per_fund[a], per_fund[b]], axis=1).fillna(0.0)
        pairs.append(OverlapPair(isin_a=a, isin_b=b, overlap=float(joined.min(axis=1).sum())))
    return tuple(sorted(pairs, key=lambda p: -p.overlap))
