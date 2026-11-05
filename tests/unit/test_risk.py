"""Risk metrics on synthetic series whose result is known by hand."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from radiografia.analytics import risk as rk
from radiografia.analytics.returns import PortfolioSeries
from radiografia.domain.metrics import MetricStatus


def _days(values, start="2020-01-01", freq="B"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq))


def test_max_drawdown_with_dates():
    # values: 1 -> 1.1 -> 0.88 -> 0.792 -> 1.1088
    daily = _days([0.10, -0.20, -0.10, 0.40], start="2020-01-02")
    depth, dd = rk.max_drawdown(daily, pd.Timestamp("2020-01-01"))
    assert depth == pytest.approx(0.792 / 1.1 - 1)  # -28 %
    assert (dd.peak, dd.trough, dd.recovered) == (
        date(2020, 1, 2),
        date(2020, 1, 6),
        date(2020, 1, 7),
    )


def test_drawdown_not_recovered():
    daily = _days([0.10, -0.50], start="2020-01-02")
    _, dd = rk.max_drawdown(daily, pd.Timestamp("2020-01-01"))
    assert dd.recovered is None


def test_historical_var_and_expected_shortfall():
    # 100 days: five losses of 1 %..5 % and 95 flat days
    daily = _days([-0.05, -0.04, -0.03, -0.02, -0.01] + [0.0] * 95)
    var, shortfall = rk.historical_var(daily, 0.95)
    # 5th percentile with linear interpolation: between -1 % (5th value) and 0 % -> -0.05 %
    assert var == pytest.approx(0.0005)
    assert shortfall == pytest.approx(0.03)  # mean of the five losses


def test_volatility_of_alternating_weeks():
    weekly = _days([0.02, -0.02] * 26, freq="W-FRI")
    expected = 0.02 * np.sqrt(52 / 51) * np.sqrt(52)  # sample std of +-2 %, annualised
    assert rk.annualised_volatility(weekly, 52) == pytest.approx(expected)


def test_ols_recovers_known_line():
    x = pd.Series(np.linspace(-0.05, 0.05, 60))
    fit = rk.ols(0.001 + 1.5 * x, x)
    assert (fit.alpha, fit.beta, fit.r_squared) == (
        pytest.approx(0.001),
        pytest.approx(1.5),
        pytest.approx(1.0),
    )
    assert fit.se_beta == pytest.approx(0.0, abs=1e-12)


# --- compute_risk with a portfolio that is exactly 1.5x the benchmark plus a weekly alpha ----
WEEKS = 260
rng = np.random.default_rng(7)
BENCH_WEEKLY = pd.Series(
    rng.normal(0.002, 0.02, WEEKS), index=pd.date_range("2021-01-08", periods=WEEKS, freq="W-FRI")
)
START = pd.Timestamp("2021-01-01")  # a Friday: first value of both indices


def _series(returns, covered=1.0, start=START):
    return PortfolioSeries(
        returns=returns,
        fund_returns=pd.DataFrame({"x": returns}),
        weights={"x": 1.0},
        covered_weight=covered,
        window_start=start.date(),
        window_end=returns.index[-1].date(),
        limited_by=None,
        nav_currencies=frozenset({"EUR"}),
    )


def _benchmark_index():
    return pd.concat([pd.Series([1.0], index=[START]), (1 + BENCH_WEEKLY).cumprod()])


ESTR_ZERO = pd.Series([0.0], index=[pd.Timestamp("2019-10-01")])


def test_beta_and_alpha_exact():
    portfolio = 0.001 + 1.5 * BENCH_WEEKLY  # one observation per week (Fridays)
    result = rk.compute_risk(
        _series(portfolio), 10000, _benchmark_index(), "ACWI", ESTR_ZERO, equity_share=1.0
    )
    assert result.beta.value == pytest.approx(1.5)
    assert result.alpha.value == pytest.approx(0.001 * 52)
    assert result.r_squared == pytest.approx(1.0)
    assert result.alpha.interval.low == pytest.approx(result.alpha.interval.high, abs=1e-9)
    assert result.beta.observations == WEEKS - 1  # first, partial week dropped
    assert result.benchmark_name == "ACWI"


def test_noisy_alpha_has_an_interval_that_includes_zero():
    noise = pd.Series(rng.normal(0, 0.01, WEEKS), index=BENCH_WEEKLY.index)
    result = rk.compute_risk(
        _series(BENCH_WEEKLY + noise), 10000, _benchmark_index(), "ACWI", ESTR_ZERO, 1.0
    )
    interval = result.alpha.interval
    assert interval.low < 0 < interval.high
    assert rk.WARNING_ALPHA_INTERVAL_INCLUDES_ZERO in result.alpha.warnings
    assert rk.WARNING_ALPHA_IS_NOT_SKILL in result.alpha.warnings
    assert interval.low < result.alpha.value < interval.high


def test_risk_free_rate_is_subtracted():
    # portfolio = benchmark: with any risk-free rate, beta 1 and alpha 0
    estr = pd.Series([3.0], index=[pd.Timestamp("2019-10-01")])
    result = rk.compute_risk(_series(BENCH_WEEKLY), 10000, _benchmark_index(), "ACWI", estr, 1.0)
    assert result.beta.value == pytest.approx(1.0)
    assert result.alpha.value == pytest.approx(0.0, abs=1e-12)


def test_mostly_bonds_shows_beta_with_warning_and_no_alpha():
    result = rk.compute_risk(
        _series(0.5 * BENCH_WEEKLY), 10000, _benchmark_index(), "ACWI", ESTR_ZERO, 0.4
    )
    assert result.beta.value == pytest.approx(0.5)
    assert rk.WARNING_LOW_EQUITY_SHARE_FOR_BETA in result.beta.warnings
    assert result.alpha.status is MetricStatus.NOT_AVAILABLE
    assert result.alpha.value is None


def test_var_in_euros_and_partial_coverage():
    result = rk.compute_risk(
        _series(BENCH_WEEKLY, covered=0.8), 10000, _benchmark_index(), "ACWI", ESTR_ZERO, 1.0
    )
    assert result.var_95_1d.status is MetricStatus.PARTIAL
    assert result.var_95_1d_eur == pytest.approx(result.var_95_1d.value * 8000)


def test_less_than_a_year_is_not_available():
    short = BENCH_WEEKLY.iloc[:30]
    result = rk.compute_risk(_series(short), 10000, _benchmark_index(), "ACWI", ESTR_ZERO, 1.0)
    for metric in (result.volatility, result.max_drawdown, result.var_95_1d, result.beta):
        assert metric.status is MetricStatus.NOT_AVAILABLE
    assert result.drawdown is None


def test_without_benchmark_or_rates_beta_is_not_available():
    result = rk.compute_risk(_series(BENCH_WEEKLY), 10000, None, None, None, 1.0)
    assert result.beta.status is MetricStatus.NOT_AVAILABLE
    assert result.volatility.status is MetricStatus.AVAILABLE


def test_no_series_means_everything_not_available():
    result = rk.compute_risk(None, 10000, None, None, None, 0.0)
    assert result.volatility.status is MetricStatus.NOT_AVAILABLE
    assert result.var_95_1d_eur is None
