"""Parse EUR amounts written either the Spanish way (1.234,56) or the international way (1,234.56).

The caller says which character is the decimal separator (the CSV reader infers it from the
column delimiter). Rules:
    - Currency marks (EUR, €) and spaces are ignored.
    - Thousands separators must form proper groups of three digits.
    - At most 2 decimals (euro cents). Exactly 3 digits after the decimal separator with no
      thousands separator ("1.500" in an international file) is rejected as ambiguous: it is far
      more likely to be a thousands separator than an amount with tenths of a cent.
    - The amount must be strictly positive.
Nothing is guessed: anything else is an error the user must fix.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum

_DIGITS = re.compile(r"[0-9]+")
_CURRENCY = re.compile(r"eur|€", re.IGNORECASE)


class AmountProblem(StrEnum):
    EMPTY = "empty"
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
    TOO_MANY_DECIMALS = "too_many_decimals"
    NON_POSITIVE = "non_positive"


class AmountParseError(ValueError):
    def __init__(self, problem: AmountProblem, raw: str) -> None:
        super().__init__(f"{problem.value}: {raw!r}")
        self.problem = problem
        self.raw = raw


def parse_amount(raw: str, decimal_separator: str) -> float:
    """Parse `raw` as a positive EUR amount. Raises AmountParseError."""
    if decimal_separator not in {",", "."}:
        raise ValueError("decimal_separator must be ',' or '.'")
    thousands_separator = "." if decimal_separator == "," else ","

    text = "".join(_CURRENCY.sub("", raw).split())
    if not text:
        raise AmountParseError(AmountProblem.EMPTY, raw)

    negative = text.startswith("-")
    if text[0] in "+-":
        text = text[1:]

    if text.count(decimal_separator) > 1:
        raise AmountParseError(AmountProblem.INVALID, raw)
    integer_part, has_decimal, fraction = text.partition(decimal_separator)
    if has_decimal and not _DIGITS.fullmatch(fraction):
        raise AmountParseError(AmountProblem.INVALID, raw)

    has_thousands = thousands_separator in integer_part
    groups = integer_part.split(thousands_separator)
    if not all(_DIGITS.fullmatch(group) for group in groups):
        raise AmountParseError(AmountProblem.INVALID, raw)
    if has_thousands and not (len(groups[0]) <= 3 and all(len(group) == 3 for group in groups[1:])):
        raise AmountParseError(AmountProblem.INVALID, raw)

    if len(fraction) == 3 and not has_thousands:
        raise AmountParseError(AmountProblem.AMBIGUOUS, raw)
    if len(fraction) > 2:
        raise AmountParseError(AmountProblem.TOO_MANY_DECIMALS, raw)

    value = Decimal("".join(groups) + "." + (fraction or "0"))
    if negative or value <= 0:
        raise AmountParseError(AmountProblem.NON_POSITIVE, raw)
    return float(value)
