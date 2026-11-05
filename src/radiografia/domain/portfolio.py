"""Portfolio input models.

Amounts are the **current market value in EUR** of each position (what it is worth today, not
what was paid). Weights are fractions of the total (0-1), computed over every position,
including those not covered by the universe, so the "not covered" share is a share of the
whole portfolio.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, computed_field


class IdentifierKind(StrEnum):
    ISIN = "isin"
    TICKER = "ticker"


class CoverageStatus(StrEnum):
    COVERED = "covered"
    NOT_COVERED = "not_covered"


class NotCoveredReason(StrEnum):
    """Why a valid position cannot be analysed. Not an error: it is reported with its weight."""

    OUTSIDE_UNIVERSE = "outside_universe"
    UNKNOWN_TICKER = "unknown_ticker"
    AMBIGUOUS_TICKER = "ambiguous_ticker"


class InputErrorCode(StrEnum):
    """Problems the user must fix before any analysis runs (texts in reporting.input_messages)."""

    EMPTY_FILE = "empty_file"
    MISSING_COLUMN = "missing_column"
    TOO_MANY_ROWS = "too_many_rows"
    EMPTY_PORTFOLIO = "empty_portfolio"
    MISSING_IDENTIFIER = "missing_identifier"
    INVALID_IDENTIFIER = "invalid_identifier"
    ISIN_WRONG_LENGTH = "isin_wrong_length"
    ISIN_BAD_COUNTRY_CODE = "isin_bad_country_code"
    ISIN_BAD_CHARACTERS = "isin_bad_characters"
    ISIN_BAD_CHECK_DIGIT = "isin_bad_check_digit"
    MISSING_AMOUNT = "missing_amount"
    INVALID_AMOUNT = "invalid_amount"
    AMBIGUOUS_AMOUNT = "ambiguous_amount"
    TOO_MANY_DECIMALS = "too_many_decimals"
    NON_POSITIVE_AMOUNT = "non_positive_amount"


class InputError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: InputErrorCode
    row: int | None = None
    """Line number in the CSV (header is line 1) or 1-based row in the form."""
    value: str | None = None
    """Offending value as entered, or the missing column name."""


class RawPosition(BaseModel):
    """One line as entered by the user, before validation."""

    model_config = ConfigDict(frozen=True)

    identifier: str
    amount_eur: float
    row: int | None = None


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    identifiers: tuple[str, ...]
    """Normalised identifiers as entered (several if the same fund appeared on several rows)."""
    kind: IdentifierKind
    """Kind of the first identifier entered."""
    isin: str | None
    """Resolved ISIN; None when a ticker could not be resolved."""
    amount_eur: float
    weight: float
    coverage: CoverageStatus
    not_covered_reason: NotCoveredReason | None = None
    rows: tuple[int, ...] = ()


class Portfolio(BaseModel):
    model_config = ConfigDict(frozen=True)

    positions: tuple[Position, ...]
    total_eur: float

    @computed_field
    @property
    def covered_weight(self) -> float:
        return sum(p.weight for p in self.positions if p.coverage is CoverageStatus.COVERED)

    @computed_field
    @property
    def not_covered_weight(self) -> float:
        return sum(p.weight for p in self.positions if p.coverage is CoverageStatus.NOT_COVERED)


class PortfolioInputResult(BaseModel):
    """Either a portfolio or the list of errors that prevent building one (never both)."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio | None
    errors: tuple[InputError, ...] = ()

    @property
    def ok(self) -> bool:
        return self.portfolio is not None
