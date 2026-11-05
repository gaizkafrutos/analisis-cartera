import pytest

from radiografia.domain.portfolio import (
    CoverageStatus,
    IdentifierKind,
    InputErrorCode,
    NotCoveredReason,
    RawPosition,
)
from radiografia.domain.universe import UniverseIndex
from radiografia.input import build_portfolio, portfolio_from_csv

WORLD = "IE00B4L5Y983"
ALL_WORLD_ACC = "IE00BK5BQT80"
ALL_WORLD_DIST = "IE00B3RBWM25"  # valid ISIN, deliberately left out of the test universe

UNIVERSE = UniverseIndex(
    isins=frozenset({WORLD, ALL_WORLD_ACC}),
    tickers={
        "EUNL": frozenset({WORLD}),
        "IWDA": frozenset({WORLD}),
        "VWCE": frozenset({ALL_WORLD_ACC}),
        "XYZ": frozenset({WORLD, ALL_WORLD_ACC}),  # synthetic ambiguous ticker
    },
)


def _raw(*rows):
    return [RawPosition(identifier=i, amount_eur=a) for i, a in rows]


def test_weights_are_amount_over_total():
    # 6000 / 3000 / 1000 of 10000 -> 0.6 / 0.3 / 0.1
    result = build_portfolio(
        _raw((WORLD, 6000), (ALL_WORLD_ACC, 3000), (ALL_WORLD_DIST, 1000)), UNIVERSE
    )
    assert result.ok and not result.errors
    portfolio = result.portfolio
    assert portfolio.total_eur == pytest.approx(10000)
    assert [p.weight for p in portfolio.positions] == pytest.approx([0.6, 0.3, 0.1])
    assert sum(p.weight for p in portfolio.positions) == pytest.approx(1.0)


def test_valid_isin_outside_universe_is_not_covered_not_an_error():
    result = build_portfolio(_raw((WORLD, 6000), (ALL_WORLD_DIST, 4000)), UNIVERSE)
    outside = result.portfolio.positions[1]
    assert outside.coverage is CoverageStatus.NOT_COVERED
    assert outside.not_covered_reason is NotCoveredReason.OUTSIDE_UNIVERSE
    assert result.portfolio.covered_weight == pytest.approx(0.6)
    assert result.portfolio.not_covered_weight == pytest.approx(0.4)


def test_ticker_resolution():
    result = build_portfolio(
        _raw(("vwce", 100), ("EUNL.DE", 100), ("ZZZZ", 100), ("XYZ", 100)), UNIVERSE
    )
    vwce, eunl, unknown, ambiguous = result.portfolio.positions
    assert (vwce.kind, vwce.isin, vwce.coverage) == (
        IdentifierKind.TICKER,
        ALL_WORLD_ACC,
        CoverageStatus.COVERED,
    )
    assert eunl.isin == WORLD  # exchange suffix stripped when the full ticker is unknown
    assert unknown.isin is None
    assert unknown.not_covered_reason is NotCoveredReason.UNKNOWN_TICKER
    assert ambiguous.isin is None
    assert ambiguous.not_covered_reason is NotCoveredReason.AMBIGUOUS_TICKER


def test_same_fund_on_several_rows_is_merged():
    # ISIN, a ticker of the same fund, and the ISIN again in lower case with spaces.
    result = build_portfolio(
        [
            RawPosition(identifier=WORLD, amount_eur=1000, row=2),
            RawPosition(identifier="IWDA", amount_eur=500, row=3),
            RawPosition(identifier="ie00 b4l5 y983", amount_eur=500, row=4),
            RawPosition(identifier=ALL_WORLD_ACC, amount_eur=2000, row=5),
        ],
        UNIVERSE,
    )
    world, all_world = result.portfolio.positions
    assert world.amount_eur == pytest.approx(2000)
    assert world.identifiers == (WORLD, "IWDA")
    assert world.rows == (2, 3, 4)
    assert world.weight == pytest.approx(0.5)
    assert all_world.weight == pytest.approx(0.5)


def test_unresolved_tickers_are_kept_apart():
    result = build_portfolio(_raw(("ZZZZ", 100), ("YYYY", 100)), UNIVERSE)
    assert len(result.portfolio.positions) == 2
    assert result.portfolio.covered_weight == 0


@pytest.mark.parametrize(
    ("identifier", "code"),
    [
        ("IE00B4L5Y984", InputErrorCode.ISIN_BAD_CHECK_DIGIT),
        ("IE00B4L5Y98", InputErrorCode.ISIN_WRONG_LENGTH),  # missing char: not a ticker
        ("12345678901X", InputErrorCode.ISIN_BAD_COUNTRY_CODE),
        ("IE00B4L5Y9_3", InputErrorCode.ISIN_BAD_CHARACTERS),
        ("VW CE!", InputErrorCode.INVALID_IDENTIFIER),
    ],
)
def test_identifier_errors_block_the_portfolio(identifier, code):
    result = build_portfolio(_raw((WORLD, 100), (identifier, 100)), UNIVERSE)
    assert result.portfolio is None
    assert [(e.code, e.row) for e in result.errors] == [(code, 2)]


@pytest.mark.parametrize("amount", [0.0, -1.0, float("nan"), float("inf")])
def test_form_amount_must_be_positive_and_finite(amount):
    result = build_portfolio(_raw((WORLD, amount)), UNIVERSE)
    assert [e.code for e in result.errors] == [InputErrorCode.NON_POSITIVE_AMOUNT]


def test_empty_portfolio():
    result = build_portfolio([], UNIVERSE)
    assert [e.code for e in result.errors] == [InputErrorCode.EMPTY_PORTFOLIO]


def test_csv_end_to_end():
    text = f"identificador;importe_eur\n{WORLD};6.000\nVWCE;3.000,00\n{ALL_WORLD_DIST};1000\n"
    result = portfolio_from_csv(text.encode("utf-8"), UNIVERSE)
    assert result.ok
    assert [p.weight for p in result.portfolio.positions] == pytest.approx([0.6, 0.3, 0.1])
    assert result.portfolio.not_covered_weight == pytest.approx(0.1)


def test_csv_reading_and_validation_errors_are_reported_together_by_line():
    text = f"isin;importe\n{WORLD};1,500\nIE00B4L5Y984;100\n"
    result = portfolio_from_csv(text, UNIVERSE)
    assert result.portfolio is None
    assert [(e.code, e.row) for e in result.errors] == [
        (InputErrorCode.AMBIGUOUS_AMOUNT, 2),
        (InputErrorCode.ISIN_BAD_CHECK_DIGIT, 3),
    ]


def test_report_is_json_serializable():
    result = build_portfolio(_raw((WORLD, 6000), (ALL_WORLD_DIST, 4000)), UNIVERSE)
    data = result.portfolio.model_dump(mode="json")
    assert data["not_covered_weight"] == pytest.approx(0.4)
    assert data["positions"][1]["not_covered_reason"] == "outside_universe"
