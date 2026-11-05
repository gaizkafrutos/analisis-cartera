"""Breakdown of one fund's holdings by sector or country, and comparison with the issuer's figures.

Weights are computed from market value, not taken from the issuer's 'Weight (%)' column:
    weight_i = market_value_i / sum(market_value of every line of the fund)
The published weights are rounded to 0.01 %: in a fund with thousands of small positions most of
them show 0.00 and the column sums to far less than 100 % (76 % for the Global Aggregate Bond
ETF on 4-nov-2026). Market values are not rounded.

Assumptions and limitations:
    - Cash, money-market funds and derivatives are kept as one 'Cash and/or Derivatives' bucket,
      as the issuer does in its own breakdowns.
    - Futures have a market value of 0 (their exposure is the notional value), so the small
      exposure they add on top of cash is not counted. Issuers use them to keep cash invested.
    - Geography is the country the issuer assigns to each company (mostly its domicile), not
      where it earns its revenue.
"""

from __future__ import annotations

import pandas as pd

CASH_LABEL = "Cash and/or Derivatives"
OTHER_LABEL = "Other"
_CASH_LIKE_ASSET_CLASSES = {
    "Cash",
    "Money Market",
    "Cash Collateral and Margins",
    "FX",
    "Futures",
    "Forwards",
}


def holding_weights(holdings: pd.DataFrame) -> pd.Series:
    """Market-value weight of each line of one fund (sums to 1)."""
    total = holdings["market_value"].sum()
    if not total > 0:
        raise ValueError("fund market value must be positive")
    return holdings["market_value"].fillna(0.0) / total


def is_cash_like(holdings: pd.DataFrame) -> pd.Series:
    return holdings["asset_class"].isin(_CASH_LIKE_ASSET_CLASSES) | (
        holdings["sector"] == CASH_LABEL
    )


def fund_breakdown(holdings: pd.DataFrame, by: str) -> pd.Series:
    """Weights by `by` ('sector' or 'location'), cash-like lines in their own bucket."""
    labels = holdings[by].where(~is_cash_like(holdings), CASH_LABEL)
    weights = holding_weights(holdings).groupby(labels).sum()
    return weights.sort_values(ascending=False)


def compare_with_published(computed: pd.Series, published: pd.DataFrame) -> pd.DataFrame:
    """Side by side: label, published weight, computed weight, difference (computed - published).

    The issuer lists the largest countries and groups the rest as 'Other'; our 'Other' is
    everything not listed by name.
    """
    named = published.loc[published["label"] != OTHER_LABEL, "label"]
    rows = []
    for label, weight in zip(published["label"], published["weight"], strict=True):
        if label == OTHER_LABEL:
            value = float(computed.drop(labels=list(named), errors="ignore").sum())
        else:
            value = float(computed.get(label, 0.0))
        rows.append({"label": label, "published": weight, "computed": value})
    comparison = pd.DataFrame(rows, columns=["label", "published", "computed"])
    comparison["difference"] = comparison["computed"] - comparison["published"]
    return comparison
