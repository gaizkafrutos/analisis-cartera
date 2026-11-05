"""ISIN (ISO 6166) normalisation and check-digit validation.

An ISIN has 12 characters:
    - 2 letters: country code. For a fund it is the fund's domicile (IE, LU...), not where it
      invests or trades.
    - 9 alphanumeric characters: national code.
    - 1 digit: check digit, computed with the Luhn algorithm over the "letter-expanded" first 11
      characters (A=10, B=11 ... Z=35; digits stay as they are).

Limitations (also in docs/GLOSARIO.md):
    - A correct check digit only proves the code is well formed, not that the security exists.
    - Luhn catches every single-digit error and most adjacent transpositions, but not all
      ("09" <-> "90" goes undetected).
    - The country code is checked to be two letters, not against the ISO 3166 list (ISINs also
      use non-country prefixes such as XS).
"""

from __future__ import annotations

import re
from enum import StrEnum

ISIN_LENGTH = 12

_BODY_11 = re.compile(r"[A-Z0-9]{11}")
_COUNTRY = re.compile(r"[A-Z]{2}")
_NATIONAL_AND_CHECK = re.compile(r"[A-Z0-9]{9}[0-9]")


class IsinProblem(StrEnum):
    """Why a string is not a well-formed ISIN (first problem found, in this order)."""

    WRONG_LENGTH = "wrong_length"
    BAD_COUNTRY_CODE = "bad_country_code"
    BAD_CHARACTERS = "bad_characters"
    BAD_CHECK_DIGIT = "bad_check_digit"


def normalize_identifier(raw: str) -> str:
    """Upper-case and drop all whitespace: users often paste ISINs as 'ie00 b4l5 y983'."""
    return "".join(raw.split()).upper()


def _letter_expanded(first_11: str) -> str:
    """Replace each character by its ISIN value: '0'-'9' -> 0-9, 'A' -> 10 ... 'Z' -> 35.

    `int(char, 36)` is exactly that mapping (base 36 uses 0-9 then A-Z).
    """
    return "".join(str(int(char, 36)) for char in first_11)


def isin_check_digit(first_11: str) -> int:
    """Return the check digit for the first 11 characters of an ISIN.

    Steps: expand letters to numbers, then Luhn: starting from the rightmost digit, double every
    second digit (the rightmost one included, because the check digit will be appended to its
    right); if doubling gives more than 9, subtract 9; add everything up. The check digit is what
    brings the total to a multiple of 10.

    >>> isin_check_digit("IE00B4L5Y98")
    3
    """
    if not _BODY_11.fullmatch(first_11):
        raise ValueError(f"expected 11 upper-case ASCII letters or digits, got {first_11!r}")
    total = 0
    for position, char in enumerate(reversed(_letter_expanded(first_11))):
        value = int(char)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (10 - total % 10) % 10


def isin_problem(isin: str) -> IsinProblem | None:
    """Return None if `isin` (already normalised) is a well-formed ISIN, else the problem."""
    if len(isin) != ISIN_LENGTH:
        return IsinProblem.WRONG_LENGTH
    if not _COUNTRY.fullmatch(isin[:2]):
        return IsinProblem.BAD_COUNTRY_CODE
    if not _NATIONAL_AND_CHECK.fullmatch(isin[2:]):
        return IsinProblem.BAD_CHARACTERS
    if isin_check_digit(isin[:11]) != int(isin[11]):
        return IsinProblem.BAD_CHECK_DIGIT
    return None


def is_valid_isin(isin: str) -> bool:
    """True if `isin` (already normalised) is a well-formed ISIN with a correct check digit."""
    return isin_problem(isin) is None
