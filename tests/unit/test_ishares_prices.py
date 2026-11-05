"""NAV, published-returns, distribution and ECB parsers on small synthetic inputs."""

from datetime import date

import pandas as pd
import pytest

from radiografia.data.sources import ecb
from radiografia.data.sources.ishares import IsharesFormatError
from radiografia.data.sources.ishares_prices import (
    nav_currency,
    parse_distributions,
    parse_historical_navs,
    parse_performance_returns,
)


def test_nav_currency_from_fund_header():
    rows = [["iShares X"], [""], ["NAV as of 04/Nov/2026"], ["USD 1,616.72"], []]
    assert nav_currency(rows) == "USD"
    with pytest.raises(IsharesFormatError):
        nav_currency([["iShares X"]])


def test_historical_navs_sorted_oldest_first():
    rows = [["Historical NAVs"], ["04/Nov/2026", "146.38"], ["03/Nov/2026", "1,144.24"], []]
    navs = parse_historical_navs(rows)
    assert list(navs.index) == [pd.Timestamp("2026-11-03"), pd.Timestamp("2026-11-04")]
    assert navs.tolist() == [1144.24, 146.38]


PERFORMANCE_ROWS = [
    ["Discrete", "as of", "30/Sept/2026"],
    [],
    ["From 30-Sept-2024 To \n30-Sept-2025", "From 30-Sept-2025 To \n30-Sept-2026"],
    ["Total Return (%)", "17.28", "15.25"],
    ["Benchmark (%)", "17.25", "15.24"],
    [],
    ["Annualised"],
    ["as of", "31/Oct/2026"],
    [],
    ["1y", "5y", "10y"],
    ["Total Return (%)", "12.13", "10.56", "-"],
    ["Benchmark (%)", "12.11", "10.49", "-"],
    [],
    ["Cumulative"],
    ["as of", "31/Oct/2026"],
    ["Incept."],
    ["Total Return (%)", "1,616.72"],
    ["Benchmark (%)", "1,600.00"],
]


def test_performance_returns():
    perf = parse_performance_returns(PERFORMANCE_ROWS)
    discrete = perf[perf["table"] == "Discrete"]
    assert discrete["start"].tolist() == [date(2024, 9, 30), date(2025, 9, 30)]
    assert discrete["end"].tolist() == [date(2025, 9, 30), date(2026, 9, 30)]
    assert discrete["fund"].tolist() == pytest.approx([0.1728, 0.1525])
    annualised = perf[perf["table"] == "Annualised"].set_index("period")
    assert annualised.loc["5y", "fund"] == pytest.approx(0.1056)
    assert annualised.loc["5y", "as_of"] == date(2026, 10, 31)
    assert pd.isna(annualised.loc["10y", "fund"])  # '-' is not available, never 0
    cumulative = perf[perf["table"] == "Cumulative"]
    assert cumulative["fund"].iloc[0] == pytest.approx(16.1672)  # thousands separator


DISTRIBUTIONS_HTML = (
    "<script>var d = {&quot;a&quot;:{&quot;formattedValue&quot;:[&quot;16/Jul/2026&quot;],"
    "&quot;label&quot;:&quot;Ex-Date&quot;,&quot;value&quot;:[20260716,20260115]},"
    "&quot;b&quot;:{&quot;label&quot;:&quot;Total Distribution&quot;,"
    "&quot;prefix&quot;:[&quot;EUR &quot;,&quot;EUR &quot;],"
    "&quot;value&quot;:[&quot;1.4093&quot;,&quot;1.418&quot;]}};</script>"
)


def test_distributions_from_page_json():
    dist = parse_distributions(DISTRIBUTIONS_HTML)
    assert dist["ex_date"].tolist() == [pd.Timestamp("2026-01-15"), pd.Timestamp("2026-07-16")]
    assert dist["amount"].tolist() == [1.418, 1.4093]
    assert set(dist["currency"]) == {"EUR"}


def test_accumulating_page_has_no_distributions():
    assert parse_distributions("<html>no data</html>").empty


def test_ecb_csv():
    text = (
        "KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE\n"
        "EXR.D.USD.EUR.SP00.A,D,USD,2026-09-30,1.1355\n"
        "EXR.D.USD.EUR.SP00.A,D,USD,2025-09-30,1.1741\n"
    )
    rates = ecb.parse_exr_csv(text)
    assert rates.index.tolist() == [pd.Timestamp("2025-09-30"), pd.Timestamp("2026-09-30")]
    assert rates.tolist() == [1.1741, 1.1355]
    with pytest.raises(ecb.EcbFormatError):
        ecb.parse_exr_csv("<html>Service Unavailable</html>")
