import pytest

from radiografia.domain.isin import (
    IsinProblem,
    is_valid_isin,
    isin_check_digit,
    isin_problem,
    normalize_identifier,
)

# Real ISINs, check digits taken from the issuers' documents.
REAL_ISINS = [
    "IE00B4L5Y983",  # iShares Core MSCI World (Acc)
    "IE00BK5BQT80",  # Vanguard FTSE All-World (Acc)
    "IE00B3RBWM25",  # Vanguard FTSE All-World (Dist)
    "US0378331005",  # Apple Inc.
]


@pytest.mark.parametrize("isin", REAL_ISINS)
def test_real_isins_are_valid(isin):
    assert is_valid_isin(isin)


def test_worked_example_from_glossary():
    # IE00B4L5Y98 -> 1814001142153498 -> Luhn sum 57 -> (10 - 7) % 10 = 3
    assert isin_check_digit("IE00B4L5Y98") == 3


def test_check_digit_zero_case():
    # Luhn sum 60 is already a multiple of 10 -> check digit 0, not 10
    assert isin_check_digit("IE00BK5BQT8") == 0


@pytest.mark.parametrize("isin", REAL_ISINS)
def test_every_single_digit_typo_is_detected(isin):
    # Changing one digit character changes exactly one digit of the expanded string,
    # which Luhn always detects.
    for position, char in enumerate(isin[:11]):
        if not char.isdigit():
            continue
        for replacement in "0123456789":
            if replacement == char:
                continue
            typo = isin[:position] + replacement + isin[position + 1 :]
            assert not is_valid_isin(typo), typo


def test_known_limitation_09_90_transposition_is_not_detected():
    # Documented trap: Luhn cannot see a swap of adjacent "0" and "9".
    body = "XS000000090"
    swapped = "XS000000009"
    assert isin_check_digit(body) == isin_check_digit(swapped)
    assert is_valid_isin(body + str(isin_check_digit(body)))
    assert is_valid_isin(swapped + str(isin_check_digit(body)))


def test_normalize_identifier_removes_spaces_and_uppercases():
    assert normalize_identifier("  ie00 b4l5 y983\t") == "IE00B4L5Y983"


@pytest.mark.parametrize(
    ("isin", "problem"),
    [
        ("IE00B4L5Y98", IsinProblem.WRONG_LENGTH),
        ("IE00B4L5Y9833", IsinProblem.WRONG_LENGTH),
        ("1E00B4L5Y983", IsinProblem.BAD_COUNTRY_CODE),
        ("IE00B4L5Y-83", IsinProblem.BAD_CHARACTERS),
        ("IE00B4L5Y98X", IsinProblem.BAD_CHARACTERS),  # check digit must be a digit
        ("IE00B4L5Y984", IsinProblem.BAD_CHECK_DIGIT),
        ("IE00B4L5Y893", IsinProblem.BAD_CHECK_DIGIT),  # adjacent transposition 98 -> 89
    ],
)
def test_problems(isin, problem):
    assert isin_problem(isin) is problem


def test_check_digit_rejects_bad_input():
    with pytest.raises(ValueError, match="11 upper-case"):
        isin_check_digit("ie00b4l5y98")
