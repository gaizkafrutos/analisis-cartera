"""Returns on synthetic NAVs whose result is known by hand."""

from datetime import date

import pandas as pd
import pytest

from radiografia.analytics import returns as rt
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Replication
from radiografia.domain.metrics import MetricStatus
from radiografia.domain.portfolio import RawPosition
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio


def _s(values: dict[str, float]) -> pd.Series:
    return pd.Series({pd.Timestamp(k): v for k, v in values.items()})


def test_total_return_index_adds_distributions_on_ex_date():
    nav = _s({"2026-01-01": 100.0, "2026-01-02": 98.0, "2026-01-05": 99.0})
    dist = _s({"2026-01-02": 3.0})
    index = rt.total_return_index(nav, dist)
    # day 2: (98 + 3) / 100 = 1.01; day 3: 99 / 98
    assert index.tolist() == pytest.approx([1.0, 1.01, 1.01 * 99 / 98])
    # without distributions the NAV alone understates the return
    assert rt.total_return_index(nav).iloc[-1] == pytest.approx(0.99)


def test_distribution_on_a_non_nav_day_goes_to_the_next_nav_day():
    nav = _s({"2026-01-01": 100.0, "2026-01-05": 100.0})
    index = rt.total_return_index(nav, _s({"2026-01-03": 2.0}))
    assert index.iloc[-1] == pytest.approx(1.02)


def test_to_eur_uses_last_published_rate():
    usd = _s({"2025-09-30": 126.43, "2026-09-30": 145.71, "2026-10-01": 146.0})
    rates = _s({"2025-09-30": 1.1741, "2026-09-30": 1.1355})  # no rate on 1 Oct
    eur = rt.to_eur(usd, "USD", rates)
    assert eur.tolist() == pytest.approx([126.43 / 1.1741, 145.71 / 1.1355, 146.0 / 1.1355])
    # worked example of the explanation: 15.25 % in USD -> 19.17 % in EUR
    assert eur.iloc[1] / eur.iloc[0] - 1 == pytest.approx(0.1917, abs=5e-5)
    assert rt.to_eur(usd, "EUR", None) is usd


def test_common_window_starts_at_the_youngest_and_fills_holidays():
    old = _s({"2026-01-01": 100.0, "2026-01-02": 110.0, "2026-01-05": 121.0})
    young = _s({"2026-01-02": 50.0, "2026-01-05": 55.0, "2026-01-06": 60.5})
    frame = rt.common_window_returns({"old": old, "young": young})
    assert frame.index.tolist() == [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")]
    assert frame["old"].tolist() == pytest.approx([0.10, 0.0])  # no NAV on 6 Jan -> 0 %
    assert frame["young"].tolist() == pytest.approx([0.10, 0.10])


def test_annualised_return():
    # value doubles in exactly two years of 365.25 days -> sqrt(2) - 1 per year
    start = pd.Timestamp("2020-01-01")
    end = start + pd.Timedelta(days=round(2 * 365.25))
    r = pd.Series([1.0], index=[end])
    assert rt.annualised_return(r, start) == pytest.approx(2**0.5 - 1, rel=1e-3)


EUR_FUND, USD_FUND, DIST_FUND = "IE00B4K48X80", "IE00B4L5Y983", "IE00B4WXJJ64"


def _fund(isin, income=IncomeTreatment.ACCUMULATING, currency="EUR"):
    return Fund(
        isin=isin,
        name=f"Fund {isin}",
        issuer="iShares",
        issuer_product_id="1",
        asset_class=AssetClass.EQUITY,
        asset_class_raw="Equity",
        benchmark="Index",
        ter=0.002,
        share_class_currency=currency,
        base_currency=currency,
        currency_hedged=False,
        income_treatment=income,
        replication=Replication.PHYSICAL,
        methodology="Replicated",
        domicile="Ireland",
        fund_launch_date=date(2010, 1, 1),
        share_class_launch_date=None,
        source_url="https://example.org",
        retrieved_on=date(2026, 11, 5),
    )


FUNDS = {
    EUR_FUND: _fund(EUR_FUND),
    USD_FUND: _fund(USD_FUND, currency="USD"),
    DIST_FUND: _fund(DIST_FUND, IncomeTreatment.DISTRIBUTING),
}


def _navs(rows):
    return pd.DataFrame(rows, columns=["isin", "date", "nav", "currency"]).assign(
        date=lambda d: pd.to_datetime(d["date"])
    )


NAVS = _navs(
    [
        (EUR_FUND, "2020-01-01", 100.0, "EUR"),
        (EUR_FUND, "2021-01-01", 110.0, "EUR"),
        (EUR_FUND, "2022-01-01", 121.0, "EUR"),
        (USD_FUND, "2020-01-01", 100.0, "USD"),
        (USD_FUND, "2021-01-01", 100.0, "USD"),
        (USD_FUND, "2022-01-01", 100.0, "USD"),
        (DIST_FUND, "2020-01-01", 100.0, "EUR"),
        (DIST_FUND, "2022-01-01", 100.0, "EUR"),
    ]
)
FX = pd.DataFrame(
    {
        "date": pd.to_datetime(["2020-01-01", "2021-01-01", "2022-01-01"]),
        "currency": "USD",
        "rate": [1.0, 1.0, 1.25],  # USD per EUR: the dollar loses 20 % in 2021
    }
)


def _portfolio(*rows):
    index = UniverseIndex(isins=frozenset(FUNDS))
    return build_portfolio(
        [RawPosition(identifier=i, amount_eur=a) for i, a in rows], index
    ).portfolio


def test_portfolio_with_constant_weights():
    result, series = rt.compute_returns(
        _portfolio((EUR_FUND, 5000), (USD_FUND, 5000)), FUNDS, NAVS, None, FX
    )
    # 2020-21: 0.5 x 10 % + 0.5 x 0 % = 5 %; 2021-22: 0.5 x 10 % + 0.5 x (1/1.25 - 1) = -5 %
    assert series.returns.tolist() == pytest.approx([0.05, -0.05])
    growth = 1.05 * 0.95
    years = (pd.Timestamp("2022-01-01") - pd.Timestamp("2020-01-01")).days / 365.25
    metric = result.annualised_return
    assert metric.value == pytest.approx(growth ** (1 / years) - 1)
    assert metric.status is MetricStatus.AVAILABLE
    assert (metric.window_start, metric.window_end) == (date(2020, 1, 1), date(2022, 1, 1))
    assert rt.WARNING_FX_TIMING in metric.warnings
    assert rt.WARNING_SHORT_HISTORY in metric.warnings  # 2 years < 3


def test_distributing_fund_without_distributions_is_not_covered():
    result, series = rt.compute_returns(
        _portfolio((EUR_FUND, 8000), (DIST_FUND, 2000)), FUNDS, NAVS, None, None
    )
    (uncovered,) = result.uncovered
    assert uncovered.reason is rt.ReturnsUncoveredReason.DISTRIBUTIONS_NOT_AVAILABLE
    assert result.annualised_return.status is MetricStatus.PARTIAL
    assert result.annualised_return.coverage.covered_weight == pytest.approx(0.8)
    assert series.weights == {EUR_FUND: pytest.approx(1.0)}  # re-scaled to the covered part


def test_usd_fund_without_ecb_rates_is_not_covered_never_assumed_eur():
    result, _ = rt.compute_returns(_portfolio((USD_FUND, 1000)), FUNDS, NAVS, None, None)
    assert result.annualised_return.status is MetricStatus.NOT_AVAILABLE
    assert result.uncovered[0].reason is rt.ReturnsUncoveredReason.NAV_NOT_AVAILABLE


def test_less_than_a_year_is_not_annualised():
    short = _navs([(EUR_FUND, "2026-01-01", 100.0, "EUR"), (EUR_FUND, "2026-06-01", 110.0, "EUR")])
    result, _ = rt.compute_returns(_portfolio((EUR_FUND, 1000)), FUNDS, short, None, None)
    assert result.annualised_return.value is None
    assert rt.WARNING_TOO_SHORT_TO_ANNUALISE in result.annualised_return.warnings


def test_no_price_data_means_not_available():
    result, series = rt.compute_returns(_portfolio((EUR_FUND, 1000)), FUNDS, None, None, None)
    assert series is None
    assert result.annualised_return.status is MetricStatus.NOT_AVAILABLE


def test_window_is_limited_by_the_youngest_fund():
    young = _navs(
        [
            *NAVS[NAVS["isin"] == EUR_FUND].itertuples(index=False),
            (USD_FUND, "2021-01-01", 100.0, "USD"),
            (USD_FUND, "2022-01-01", 100.0, "USD"),
        ]
    )
    result, _ = rt.compute_returns(
        _portfolio((EUR_FUND, 5000), (USD_FUND, 5000)), FUNDS, young, None, FX
    )
    assert result.annualised_return.window_start == date(2021, 1, 1)
    assert result.limited_by == FUNDS[USD_FUND].name


def test_trailing_window_uses_the_last_five_years():
    index = pd.date_range("2015-01-01", "2025-12-31", freq="D")
    returns = pd.Series(0.0, index=index)
    returns[returns.index > pd.Timestamp("2020-12-31")] = 0.0001
    recent, base = rt.trailing_window(returns, pd.Timestamp("2014-12-31"), 5)
    assert base == pd.Timestamp("2020-12-31")
    assert recent.index[0] == pd.Timestamp("2021-01-01")
    years = (recent.index[-1] - base).days / rt.DAYS_PER_YEAR
    assert rt.annualised_return(recent, base) == pytest.approx(1.0001 ** (len(recent) / years) - 1)


def test_trailing_window_with_short_history_is_the_whole_series():
    returns = pd.Series(0.001, index=pd.date_range("2023-01-02", periods=500, freq="B"))
    start = pd.Timestamp("2023-01-01")
    recent, base = rt.trailing_window(returns, start, 5)
    assert base == start
    assert len(recent) == len(returns)
