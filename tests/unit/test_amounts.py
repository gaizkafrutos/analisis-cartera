import pytest

from radiografia.input.amounts import AmountParseError, AmountProblem, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1500", 1500.0),
        ("1.500", 1500.0),
        ("1.234,56", 1234.56),
        ("12,5", 12.5),
        ("1.234.567,89", 1234567.89),
        ("  1 000,00 € ", 1000.0),
        ("1\u00a0000 EUR", 1000.0),  # non-breaking space, as pasted from some brokers
        ("+250", 250.0),
    ],
)
def test_spanish_convention(raw, expected):
    assert parse_amount(raw, decimal_separator=",") == pytest.approx(expected)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1500", 1500.0),
        ("1,500", 1500.0),
        ("1,234.56", 1234.56),
        ("1500.5", 1500.5),
    ],
)
def test_international_convention(raw, expected):
    assert parse_amount(raw, decimal_separator=".") == pytest.approx(expected)


@pytest.mark.parametrize(
    ("raw", "decimal_separator", "problem"),
    [
        ("", ",", AmountProblem.EMPTY),
        ("€", ",", AmountProblem.EMPTY),
        ("abc", ",", AmountProblem.INVALID),
        ("1.23.4", ",", AmountProblem.INVALID),  # bad thousands grouping
        ("1234.567,8", ",", AmountProblem.INVALID),  # first group longer than 3 digits
        ("1,2,3", ",", AmountProblem.INVALID),  # two decimal separators
        ("12,", ",", AmountProblem.INVALID),
        ("1,500", ",", AmountProblem.AMBIGUOUS),  # 1.5 or 1500?
        ("1.500", ".", AmountProblem.AMBIGUOUS),
        ("1.234,567", ",", AmountProblem.TOO_MANY_DECIMALS),
        ("12,3456", ",", AmountProblem.TOO_MANY_DECIMALS),
        ("0", ",", AmountProblem.NON_POSITIVE),
        ("0,00", ",", AmountProblem.NON_POSITIVE),
        ("-100", ",", AmountProblem.NON_POSITIVE),
    ],
)
def test_problems(raw, decimal_separator, problem):
    with pytest.raises(AmountParseError) as exc_info:
        parse_amount(raw, decimal_separator=decimal_separator)
    assert exc_info.value.problem is problem


def test_rejects_unknown_decimal_separator():
    with pytest.raises(ValueError, match="decimal_separator"):
        parse_amount("1", decimal_separator=" ")
