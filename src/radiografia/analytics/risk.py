"""Risk of the portfolio's EUR return series (current weights held constant, see `returns`).

Metrics and windows (decided with the author, see docs/METODOLOGIA.md and AUDITORIA.md):
    - Drawdowns in fixed episodes (calendar years 2020 and 2022) for the portfolio and for the
      reference index, so different portfolios are compared on the same events. Added after the
      audit: the whole-window maximum drawdown ranked a concentrated tech portfolio as less risky
      than the MSCI World because its worst episode was 2020, not 2022.
    - Drawdown profile: daily distance below the previous peak of the portfolio and of the
      reference index, both measured from the start of the portfolio's window (for the chart
      that puts the episodes in context).
    - Volatility: standard deviation of weekly returns x sqrt(52), last 5 years.
    - Maximum drawdown: worst fall from a previous peak, daily, whole available window; with the
      peak, trough and recovery dates.
    - Historical VaR 95 % at 1 day: the loss exceeded on 5 % of days, last 5 years; plus the
      expected shortfall (average loss on those days).
    - Beta and alpha: OLS of weekly portfolio excess returns on weekly benchmark excess returns
      (iShares MSCI ACWI in EUR), over the €STR, last 5 years. Alpha annualised (x 52) with a
      95 % interval from the regression standard error.

Assumptions and limitations:
    - Weekly returns use Friday closes (W-FRI); the first, partial week is dropped.
    - Annualising volatility with sqrt(52) assumes independent weeks.
    - The alpha interval assumes independent, equally variable residuals; with autocorrelation it
      would be wider. It uses the normal approximation (z = 1.96), fine for 52+ weeks.
    - Risk-free weekly return = €STR (% per year) / 100 / 52, last published rate in each week.
    - The window only contains the history of the data: it does not include crises before the
      youngest ETF existed (e.g. 2008 if the window starts in 2009).
"""

from __future__ import annotations

from datetime import date
from statistics import NormalDist

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from radiografia.analytics.returns import DAYS_PER_YEAR, PortfolioSeries
from radiografia.domain.metrics import Coverage, Interval, MetricResult, MetricStatus, Unit

VOLATILITY = "volatility"
MAX_DRAWDOWN = "max_drawdown"
VAR_95_1D = "var_95_1d"
EXPECTED_SHORTFALL_95_1D = "expected_shortfall_95_1d"
BETA = "beta"
ALPHA = "alpha"
EPISODE_DRAWDOWNS = "episode_drawdowns"

WINDOW_YEARS = 5
MIN_YEARS = 1.0
SHORT_YEARS = 3.0
VAR_LEVEL = 0.95
CONFIDENCE = 0.95
WEEKS_PER_YEAR = 52
MIN_WEEKS_FOR_REGRESSION = 52
MIN_EQUITY_SHARE_FOR_BETA = 0.8

WARNING_SHORT_RISK_HISTORY = "short_risk_history"
WARNING_HISTORY_EXCLUDES_OLDER_CRISES = "history_excludes_older_crises"
WARNING_VAR_IS_NOT_MAX_LOSS = "var_is_not_max_loss"
WARNING_LOW_EQUITY_SHARE_FOR_BETA = "low_equity_share_for_beta"
WARNING_LOW_R_SQUARED = "low_r_squared"
WARNING_ALPHA_IS_NOT_SKILL = "alpha_is_not_skill"
WARNING_ALPHA_INTERVAL_INCLUDES_ZERO = "alpha_interval_includes_zero"
WARNING_VOLATILITY_SYMMETRIC = "volatility_symmetric"
LOW_R_SQUARED = 0.8


class EpisodeDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    start: date
    end: date


EPISODE_DEFINITIONS = (
    EpisodeDefinition(
        key="2020", label="2020 (covid)", start=date(2020, 1, 1), end=date(2020, 12, 31)
    ),
    EpisodeDefinition(
        key="2022",
        label="2022 (inflación y subida de tipos)",
        start=date(2022, 1, 1),
        end=date(2022, 12, 31),
    ),
)


class EpisodeDrawdown(BaseModel):
    """Worst fall from a previous peak inside the episode (value at the episode start = peak)."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    start: date
    end: date
    portfolio: float | None
    """None if the portfolio has no data for the whole episode (never estimated)."""
    reference: float | None


class ProfilePoint(BaseModel):
    """Distance below the previous peak on one day (-0.2 = 20 % below it)."""

    model_config = ConfigDict(frozen=True)

    day: date
    portfolio: float
    reference: float | None


class Drawdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    peak: date
    trough: date
    recovered: date | None
    """First date back at the previous peak; None if not recovered by the end of the data."""


class RiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    volatility: MetricResult
    max_drawdown: MetricResult
    drawdown: Drawdown | None
    var_95_1d: MetricResult
    var_95_1d_eur: float | None
    """VaR applied to the covered amount of the portfolio, in EUR."""
    expected_shortfall_95_1d: MetricResult
    beta: MetricResult
    alpha: MetricResult
    r_squared: float | None
    benchmark_name: str | None
    episodes: tuple[EpisodeDrawdown, ...] = ()
    profile: tuple[ProfilePoint, ...] = ()


# --- pure building blocks ---------------------------------------------------------------------


def growth_index(daily: pd.Series, start: pd.Timestamp) -> pd.Series:
    """Value of 1 EUR invested at `start` (value 1 on `start`, then compounding `daily`)."""
    values = (1 + daily).cumprod()
    return pd.concat([pd.Series([1.0], index=[start]), values])


def weekly_returns(daily: pd.Series, start: pd.Timestamp) -> pd.Series:
    weekly = growth_index(daily, start).resample("W-FRI").last()
    return _real_last_day(weekly.pct_change().dropna().iloc[1:], daily)  # first week is partial


def _real_last_day(weekly: pd.Series | pd.DataFrame, daily: pd.Series):
    """Weekly series are labelled with the week's Friday; if the data stop earlier in the last
    week (e.g. on a Wednesday), relabel that week with the last real date so no window reports
    a date after the data."""
    if len(weekly) and weekly.index[-1] > daily.index[-1]:
        weekly = weekly.rename(index={weekly.index[-1]: daily.index[-1]})
    return weekly


def trailing(series: pd.Series, years: int) -> pd.Series:
    return series[series.index > series.index[-1] - pd.DateOffset(years=years)]


def annualised_volatility(returns: pd.Series, periods_per_year: int) -> float:
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(daily: pd.Series, start: pd.Timestamp) -> tuple[float, Drawdown]:
    values = growth_index(daily, start)
    drawdowns = values / values.cummax() - 1
    trough = drawdowns.idxmin()
    peak = values.loc[:trough].idxmax()
    after = values.loc[trough:]
    back = after[after >= values.loc[peak]]
    recovered = back.index[0].date() if len(back) else None
    return float(drawdowns.min()), Drawdown(
        peak=peak.date(), trough=trough.date(), recovered=recovered
    )


def drawdown_in_period(values: pd.Series, start: date, end: date) -> float | None:
    """Worst drawdown of a value series inside [start, end].

    The last value on or before `start` is the starting peak. None if the series does not
    cover the whole period (starts after `start` or ends before `end`).
    """
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if values.empty or values.index[0] > first or values.index[-1] < last:
        return None
    base = values.loc[:first]
    window = values.loc[first:last]
    path = pd.concat([base.iloc[-1:], window]) if len(base) else window
    return float((path / path.cummax() - 1).min())


def episode_drawdowns(
    portfolio_values: pd.Series | None, reference_values: pd.Series | None
) -> tuple[EpisodeDrawdown, ...]:
    def dd(values: pd.Series | None, episode: EpisodeDefinition) -> float | None:
        return None if values is None else drawdown_in_period(values, episode.start, episode.end)

    return tuple(
        EpisodeDrawdown(
            key=e.key,
            label=e.label,
            start=e.start,
            end=e.end,
            portfolio=dd(portfolio_values, e),
            reference=dd(reference_values, e),
        )
        for e in EPISODE_DEFINITIONS
    )


def drawdown_profile(
    portfolio_values: pd.Series, reference_values: pd.Series | None
) -> tuple[ProfilePoint, ...]:
    """Daily drawdown of the portfolio and of the reference over the same dates.

    Daily, like the episodes, so the chart shows the same depths as the episode figures. The
    reference's peak is taken from the portfolio's first date on, so both start at 0.
    """
    values = portfolio_values.dropna()
    portfolio = values / values.cummax() - 1
    reference = None
    if reference_values is not None and not reference_values.empty:
        ref = reference_values.sort_index().loc[values.index[0] :]
        ref = ref.reindex(ref.index.union(values.index)).ffill().reindex(values.index)
        reference = ref / ref.cummax() - 1
    return tuple(
        ProfilePoint(
            day=day.date(),
            portfolio=float(portfolio[day]),
            reference=(
                float(reference[day])
                if reference is not None and pd.notna(reference[day])
                else None
            ),
        )
        for day in values.index
    )


def historical_var(daily: pd.Series, level: float = VAR_LEVEL) -> tuple[float, float]:
    """(VaR, expected shortfall) as positive loss fractions at `level` (linear interpolation)."""
    threshold = float(np.quantile(daily, 1 - level))
    tail = daily[daily <= threshold]
    return -threshold, float(-tail.mean())


class OlsFit(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha: float
    beta: float
    se_alpha: float
    se_beta: float
    r_squared: float
    n: int


def ols(y: pd.Series, x: pd.Series) -> OlsFit:
    """y = alpha + beta * x + e, with classical standard errors."""
    design = np.column_stack([np.ones(len(x)), x.to_numpy()])
    target = y.to_numpy()
    coef, *_ = np.linalg.lstsq(design, target, rcond=None)
    residuals = target - design @ coef
    n, k = design.shape
    variance = residuals @ residuals / (n - k)
    covariance = variance * np.linalg.inv(design.T @ design)
    total = (target - target.mean()) @ (target - target.mean())
    return OlsFit(
        alpha=float(coef[0]),
        beta=float(coef[1]),
        se_alpha=float(np.sqrt(covariance[0, 0])),
        se_beta=float(np.sqrt(covariance[1, 1])),
        r_squared=float(1 - residuals @ residuals / total),
        n=n,
    )


# --- metric assembly --------------------------------------------------------------------------


def _metric(key, value, unit, coverage, status, start, end, n, warnings, interval=None):
    available = value is not None and status is not MetricStatus.NOT_AVAILABLE
    return MetricResult(
        key=key,
        value=value if available else None,
        unit=unit,
        status=status if available else MetricStatus.NOT_AVAILABLE,
        coverage=coverage,
        interval=interval if available else None,
        window_start=start,
        window_end=end,
        observations=n,
        warnings=tuple(warnings),
    )


def _not_available(key: str, unit: Unit, coverage: Coverage) -> MetricResult:
    return MetricResult(
        key=key, value=None, unit=unit, status=MetricStatus.NOT_AVAILABLE, coverage=coverage
    )


def compute_risk(
    series: PortfolioSeries | None,
    total_eur: float,
    benchmark_index: pd.Series | None,
    benchmark_name: str | None,
    estr: pd.Series | None,
    equity_share: float,
) -> RiskResult:
    """Risk metrics of the covered part of the portfolio.

    `equity_share`: share of equity ETFs within the covered part (beta warning below 80 %).
    `estr`: €STR in % per year by date. `benchmark_index`: EUR total-return index of the
    benchmark ETF.
    """
    covered = series.covered_weight if series else 0.0
    coverage = Coverage(
        covered_weight=covered,
        covered_amount_eur=covered * total_eur,
        not_covered_amount_eur=(1 - covered) * total_eur,
    )
    keys = [
        (VOLATILITY, Unit.FRACTION),
        (MAX_DRAWDOWN, Unit.FRACTION),
        (VAR_95_1D, Unit.FRACTION),
        (EXPECTED_SHORTFALL_95_1D, Unit.FRACTION),
        (BETA, Unit.RATIO),
        (ALPHA, Unit.FRACTION),
    ]
    empty = {key: _not_available(key, unit, coverage) for key, unit in keys}
    if series is None or series.returns.empty:
        return RiskResult(
            volatility=empty[VOLATILITY],
            max_drawdown=empty[MAX_DRAWDOWN],
            drawdown=None,
            var_95_1d=empty[VAR_95_1D],
            var_95_1d_eur=None,
            expected_shortfall_95_1d=empty[EXPECTED_SHORTFALL_95_1D],
            beta=empty[BETA],
            alpha=empty[ALPHA],
            r_squared=None,
            benchmark_name=None,
        )

    daily = series.returns
    start = pd.Timestamp(series.window_start)
    years = (daily.index[-1] - start).days / DAYS_PER_YEAR
    status = MetricStatus.PARTIAL if covered < 1 - 1e-12 else MetricStatus.AVAILABLE
    if years < MIN_YEARS:
        status = MetricStatus.NOT_AVAILABLE
    short = [WARNING_SHORT_RISK_HISTORY] if years < SHORT_YEARS else []

    # volatility (weekly, last 5 years)
    weekly = trailing(weekly_returns(daily, start), WINDOW_YEARS)
    volatility = _metric(
        VOLATILITY,
        annualised_volatility(weekly, WEEKS_PER_YEAR) if len(weekly) > 1 else None,
        Unit.FRACTION,
        coverage,
        status,
        weekly.index[0].date() if len(weekly) else None,
        weekly.index[-1].date() if len(weekly) else None,
        len(weekly),
        [*short, WARNING_VOLATILITY_SYMMETRIC],
    )

    # maximum drawdown (daily, whole window)
    depth, drawdown = max_drawdown(daily, start)
    mdd = _metric(
        MAX_DRAWDOWN,
        depth,
        Unit.FRACTION,
        coverage,
        status,
        series.window_start,
        series.window_end,
        len(daily),
        [*short, WARNING_HISTORY_EXCLUDES_OLDER_CRISES],
    )

    # historical VaR and expected shortfall (daily, last 5 years)
    recent = trailing(daily, WINDOW_YEARS)
    var, shortfall = historical_var(recent)
    var_window = (recent.index[0].date(), recent.index[-1].date(), len(recent))
    var_metric = _metric(
        VAR_95_1D,
        var,
        Unit.FRACTION,
        coverage,
        status,
        *var_window,
        [*short, WARNING_VAR_IS_NOT_MAX_LOSS],
    )
    es_metric = _metric(
        EXPECTED_SHORTFALL_95_1D, shortfall, Unit.FRACTION, coverage, status, *var_window, short
    )

    beta, alpha, r_squared = _beta_alpha(
        daily, start, benchmark_index, estr, coverage, status, short, equity_share
    )
    available = status is not MetricStatus.NOT_AVAILABLE
    values = growth_index(daily, start)
    episodes = episode_drawdowns(values, benchmark_index) if available else ()
    profile = drawdown_profile(values, benchmark_index) if available else ()
    return RiskResult(
        volatility=volatility,
        max_drawdown=mdd,
        drawdown=drawdown if status is not MetricStatus.NOT_AVAILABLE else None,
        var_95_1d=var_metric,
        var_95_1d_eur=var * coverage.covered_amount_eur if var_metric.value is not None else None,
        expected_shortfall_95_1d=es_metric,
        beta=beta,
        alpha=alpha,
        r_squared=r_squared,
        benchmark_name=benchmark_name if beta.value is not None else None,
        episodes=episodes,
        profile=profile,
    )


def _beta_alpha(daily, start, benchmark_index, estr, coverage, status, short, equity_share):
    unavailable = (
        _not_available(BETA, Unit.RATIO, coverage),
        _not_available(ALPHA, Unit.FRACTION, coverage),
        None,
    )
    if benchmark_index is None or estr is None or estr.empty:
        return unavailable

    portfolio_weekly = growth_index(daily, start).resample("W-FRI").last()
    benchmark_weekly = benchmark_index.resample("W-FRI").last()
    weekly = (
        pd.concat([portfolio_weekly, benchmark_weekly], axis=1, keys=["p", "b"], sort=True)
        .dropna()
        .pct_change()
        .dropna()
        .iloc[1:]
    )
    rate = estr.sort_index().reindex(weekly.index, method="ffill")
    weekly = weekly.assign(rf=rate / 100 / WEEKS_PER_YEAR).dropna()
    weekly = trailing(_real_last_day(weekly, daily), WINDOW_YEARS)
    if len(weekly) < MIN_WEEKS_FOR_REGRESSION:
        return unavailable

    fit = ols(weekly["p"] - weekly["rf"], weekly["b"] - weekly["rf"])
    z = NormalDist().inv_cdf(0.5 + CONFIDENCE / 2)
    window = (weekly.index[0].date(), weekly.index[-1].date(), fit.n)

    beta_warnings = list(short)
    if equity_share < MIN_EQUITY_SHARE_FOR_BETA:
        beta_warnings.append(WARNING_LOW_EQUITY_SHARE_FOR_BETA)
    if fit.r_squared < LOW_R_SQUARED:
        beta_warnings.append(WARNING_LOW_R_SQUARED)
    beta = _metric(
        BETA,
        fit.beta,
        Unit.RATIO,
        coverage,
        status,
        *window,
        beta_warnings,
        Interval(
            low=fit.beta - z * fit.se_beta, high=fit.beta + z * fit.se_beta, confidence=CONFIDENCE
        ),
    )

    if equity_share < MIN_EQUITY_SHARE_FOR_BETA:
        # Against an equity index, a mostly-bond portfolio shows a large, "significant" alpha
        # that is only the bond part (e.g. -2.95 % a year for 40 % equity on 4-nov-2026). A
        # non-expert would read it as underperformance, so alpha is not shown at all.
        alpha = MetricResult(
            key=ALPHA,
            value=None,
            unit=Unit.FRACTION,
            status=MetricStatus.NOT_AVAILABLE,
            coverage=coverage,
            warnings=(WARNING_LOW_EQUITY_SHARE_FOR_BETA,),
        )
        return beta, alpha, fit.r_squared

    alpha_year = fit.alpha * WEEKS_PER_YEAR
    half_width = z * fit.se_alpha * WEEKS_PER_YEAR
    interval = Interval(
        low=alpha_year - half_width, high=alpha_year + half_width, confidence=CONFIDENCE
    )
    alpha_warnings = [*beta_warnings, WARNING_ALPHA_IS_NOT_SKILL]
    if interval.low <= 0 <= interval.high:
        alpha_warnings.append(WARNING_ALPHA_INTERVAL_INCLUDES_ZERO)
    alpha = _metric(
        ALPHA, alpha_year, Unit.FRACTION, coverage, status, *window, alpha_warnings, interval
    )
    return beta, alpha, fit.r_squared
