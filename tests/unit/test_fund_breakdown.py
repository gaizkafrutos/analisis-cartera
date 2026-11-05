"""Fund breakdown on synthetic holdings whose result is known by hand."""

import pandas as pd
import pytest

from radiografia.analytics.fund_breakdown import (
    CASH_LABEL,
    compare_with_published,
    fund_breakdown,
    holding_weights,
)


def _holdings(rows):
    return pd.DataFrame(rows, columns=["name", "sector", "asset_class", "location", "market_value"])


HOLDINGS = _holdings(
    [
        ("A", "Information Technology", "Equity", "United States", 500.0),
        ("B", "Financials", "Equity", "United States", 200.0),
        ("C", "Financials", "Equity", "Japan", 150.0),
        ("D", "Industrials", "Equity", "Germany", 100.0),
        ("CASH", "Cash and/or Derivatives", "Cash", "United States", 40.0),
        ("MMF", "Cash and/or Derivatives", "Money Market", "Ireland", 10.0),
        ("FUT", "Cash and/or Derivatives", "Futures", "-", 0.0),
    ]
)


def test_weights_come_from_market_value():
    assert holding_weights(HOLDINGS).tolist() == pytest.approx(
        [0.50, 0.20, 0.15, 0.10, 0.04, 0.01, 0.0]
    )


def test_breakdown_by_sector_and_country_with_cash_bucket():
    assert fund_breakdown(HOLDINGS, "sector").to_dict() == pytest.approx(
        {"Information Technology": 0.50, "Financials": 0.35, "Industrials": 0.10, CASH_LABEL: 0.05}
    )
    # USD cash is not "United States" exposure: it goes to the cash bucket, as the issuer does
    assert fund_breakdown(HOLDINGS, "location").to_dict() == pytest.approx(
        {"United States": 0.70, "Japan": 0.15, "Germany": 0.10, CASH_LABEL: 0.05}
    )


def test_breakdown_sums_to_one():
    assert fund_breakdown(HOLDINGS, "location").sum() == pytest.approx(1.0)


def test_comparison_with_other_bucket():
    published = pd.DataFrame(
        {
            "label": ["United States", "Japan", "Other", CASH_LABEL],
            "weight": [0.70, 0.15, 0.10, 0.05],
        }
    )
    comparison = compare_with_published(fund_breakdown(HOLDINGS, "location"), published)
    assert comparison["computed"].tolist() == pytest.approx([0.70, 0.15, 0.10, 0.05])
    assert comparison["difference"].abs().max() == pytest.approx(0.0)


def test_label_missing_from_holdings_counts_as_zero():
    published = pd.DataFrame({"label": ["France"], "weight": [0.02]})
    comparison = compare_with_published(fund_breakdown(HOLDINGS, "location"), published)
    assert comparison.loc[0, "computed"] == 0.0
    assert comparison.loc[0, "difference"] == pytest.approx(-0.02)


def test_zero_value_fund_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        holding_weights(_holdings([("A", "X", "Equity", "US", 0.0)]))
