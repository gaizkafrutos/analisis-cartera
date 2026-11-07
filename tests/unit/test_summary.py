"""Plain-language summary on synthetic data (no snapshot needed)."""

from datetime import date

import pandas as pd
import pytest

from radiografia import service
from radiografia.analytics.costs import compute_costs
from radiografia.analytics.lookthrough import compute_lookthrough
from radiografia.analytics.returns import compute_returns
from radiografia.analytics.risk import compute_risk
from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Replication
from radiografia.domain.portfolio import RawPosition
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio
from radiografia.reporting import summary as sm
from radiografia.reporting.texts import DISCLAIMER

FORBIDDEN = ("deberías", "debes", "recomend", "te conviene", "compra ", "vende ", "cámbiate")

US, BONDS = "IE00B5BMR087", "IE00B4WXJJ64"


def _fund(isin, asset_class):
    return Fund(
        isin=isin,
        name=f"iShares Fund {isin} UCITS ETF",
        issuer="iShares",
        issuer_product_id="1",
        asset_class=asset_class,
        asset_class_raw=asset_class.value,
        benchmark="Index",
        ter=0.001,
        share_class_currency="USD",
        base_currency="USD",
        currency_hedged=False,
        income_treatment=IncomeTreatment.ACCUMULATING,
        replication=Replication.PHYSICAL,
        methodology="Replicated",
        domicile="Ireland",
        fund_launch_date=date(2010, 1, 1),
        share_class_launch_date=None,
        source_url="https://example.org",
        retrieved_on=date(2026, 11, 5),
    )


FUNDS = {US: _fund(US, AssetClass.EQUITY), BONDS: _fund(BONDS, AssetClass.FIXED_INCOME)}
HOLDINGS = pd.DataFrame(
    [
        (US, "APPLE", "Information Technology", "Equity", "United States", "USD", 60.0),
        (US, "MICROSOFT", "Information Technology", "Equity", "United States", "USD", 40.0),
        (US, "EUR CASH", "Cash and/or Derivatives", "Cash", "Germany", "EUR", -0.01),
        (BONDS, "BUND", "Treasuries", "Fixed Income", "Germany", "EUR", 100.0),
    ],
    columns=[
        "isin",
        "name",
        "sector",
        "asset_class",
        "location",
        "market_currency",
        "market_value",
    ],
)
AS_OF = {US: date(2026, 11, 4), BONDS: date(2026, 11, 4)}


def _summary(*rows):
    index = UniverseIndex(isins=frozenset(FUNDS))
    portfolio = build_portfolio(
        [RawPosition(identifier=i, amount_eur=a) for i, a in rows], index
    ).portfolio
    lookthrough = compute_lookthrough(portfolio, FUNDS, HOLDINGS, AS_OF)
    returns, series = compute_returns(portfolio, FUNDS, None, None, None)
    risk = compute_risk(series, portfolio.total_eur, None, None, None, 1.0)
    costs = compute_costs(portfolio, FUNDS)
    names = {isin: f.name for isin, f in FUNDS.items()}
    return sm.build_summary(portfolio, costs, lookthrough, returns, risk, names)


def _texts(summary):
    return {point.topic: point.text for point in summary.points}


def test_only_available_facts_appear():
    texts = _texts(_summary((US, 10000)))
    # no price data -> no risk, market or returns points; no bonds -> no asset mix
    assert set(texts) == {sm.Topic.COSTS, sm.Topic.GEOGRAPHY, sm.Topic.CURRENCY,
                          sm.Topic.CONCENTRATION}  # fmt: skip
    assert "10,00 € al año" in texts[sm.Topic.COSTS]  # 10,000 x 0.10 %


def test_negligible_euro_share_is_not_shown_as_minus_zero():
    texts = _texts(_summary((US, 10000)))
    assert "-0" not in texts[sm.Topic.CURRENCY]
    assert "Prácticamente nada está en euros" in texts[sm.Topic.CURRENCY]


def test_country_ending_in_a_period_is_not_followed_by_another():
    text = _texts(_summary((US, 10000)))[sm.Topic.GEOGRAPHY]
    assert "EE. UU.." not in text and text.endswith(".")


def test_asset_mix_is_relative_to_the_analysed_part():
    texts = _texts(_summary((US, 4000), (BONDS, 6000)))
    assert "un 40 % es renta variable" in texts[sm.Topic.ASSET_MIX]
    assert "un 60 % renta fija" in texts[sm.Topic.ASSET_MIX]


def test_coverage_point_names_what_is_left_out():
    texts = _texts(_summary((US, 9000), ("IE00BK5BQT80", 1000)))
    assert "90,0 %" in texts[sm.Topic.COVERAGE]
    assert "IE00BK5BQT80" in texts[sm.Topic.COVERAGE]


def test_concentration_uses_title_case_and_counts():
    text = _texts(_summary((US, 10000)))[sm.Topic.CONCENTRATION]
    assert "la mayor es Apple, con el 60,0 %" in text
    assert "Tienes 2 empresas" in text


@pytest.mark.parametrize("rows", [[(US, 10000)], [(US, 4000), (BONDS, 6000)]])
def test_language_never_recommends(rows):
    summary = _summary(*rows)
    for point in summary.points:
        lowered = point.text.lower()
        assert not [word for word in FORBIDDEN if word in lowered], point.text
    assert summary.disclaimer == DISCLAIMER


def test_service_without_snapshot_still_summarises_costs():
    rows = [RawPosition(identifier="EUNL", amount_eur=1000)]
    report = service.analyze(service.read_portfolio_rows(rows).portfolio, snapshot=None)
    assert [p.topic for p in report.summary.points] == [sm.Topic.COSTS]


def _risk_with_episodes(portfolio_2020, portfolio_2022, reference=(-0.34, -0.16)):
    from radiografia.analytics.risk import EPISODE_DEFINITIONS, EpisodeDrawdown

    values = (portfolio_2020, portfolio_2022)
    episodes = tuple(
        EpisodeDrawdown(
            key=e.key, label=e.label, start=e.start, end=e.end, portfolio=p, reference=r
        )
        for e, p, r in zip(EPISODE_DEFINITIONS, values, reference, strict=True)
    )
    empty = compute_risk(None, 10000, None, None, None, 1.0)
    return empty.model_copy(update={"episodes": episodes})


def test_risk_point_compares_each_episode_with_the_market():
    point = sm.risk_point(_risk_with_episodes(-0.307, -0.285))
    assert point.topic is sm.Topic.RISK
    assert "en 2020 (covid) la cartera habría llegado a caer un 30,7 %" in point.text
    assert "frente a un 34,0 % del mercado mundial" in point.text
    assert "en 2022 (inflación y subida de tipos), un 28,5 %, frente a un 16,0 %" in point.text


def test_risk_point_skips_episodes_without_portfolio_data():
    point = sm.risk_point(_risk_with_episodes(None, -0.20))
    assert "2020" not in point.text
    assert "en 2022 (inflación y subida de tipos) la cartera habría llegado a caer" in point.text


def test_summary_leaves_out_var_alpha_and_simulated_return():
    assert "returns" not in {topic.value for topic in sm.Topic}
    risk = _risk_with_episodes(-0.30, -0.20)
    texts = sm.risk_point(risk).text
    assert "1 de cada 20" not in texts  # VaR
