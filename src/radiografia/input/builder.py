"""Turn raw positions into a validated Portfolio with weights and coverage.

Rules (see docs/METODOLOGIA.md, "Entrada de cartera"):
    - Identifier with 9+ characters -> treated as an ISIN (tickers are at most 8 characters,
      exchange suffix included). A malformed ISIN or a wrong check digit is an error the user
      must fix: a missing or extra character must not silently become an unknown ticker.
    - Shorter identifier -> treated as a ticker. It is resolved only if it maps to exactly one
      ISIN in the universe; otherwise the position is "not covered" (never guessed).
    - A valid ISIN outside the universe is not an error: the position is "not covered".
    - Rows resolving to the same fund are merged (amounts added).
    - Any error -> no portfolio is built: a partial portfolio would have wrong weights.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from radiografia.domain.isin import IsinProblem, isin_problem, normalize_identifier
from radiografia.domain.portfolio import (
    CoverageStatus,
    IdentifierKind,
    InputError,
    InputErrorCode,
    NotCoveredReason,
    Portfolio,
    PortfolioInputResult,
    Position,
    RawPosition,
)
from radiografia.domain.universe import UniverseIndex
from radiografia.input.csv_reader import read_portfolio_csv

MIN_ISIN_ATTEMPT_LENGTH = 9
_TICKER = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,7}")

_ISIN_ERRORS = {
    IsinProblem.WRONG_LENGTH: InputErrorCode.ISIN_WRONG_LENGTH,
    IsinProblem.BAD_COUNTRY_CODE: InputErrorCode.ISIN_BAD_COUNTRY_CODE,
    IsinProblem.BAD_CHARACTERS: InputErrorCode.ISIN_BAD_CHARACTERS,
    IsinProblem.BAD_CHECK_DIGIT: InputErrorCode.ISIN_BAD_CHECK_DIGIT,
}


@dataclass
class _Resolved:
    kind: IdentifierKind
    isin: str | None
    reason: NotCoveredReason | None
    identifiers: list[str] = field(default_factory=list)
    amount_eur: float = 0.0
    rows: list[int] = field(default_factory=list)


def _resolve_ticker(
    ticker: str, universe: UniverseIndex
) -> tuple[str | None, NotCoveredReason | None]:
    candidates = universe.tickers.get(ticker)
    if candidates is None and "." in ticker:  # "EUNL.DE" -> "EUNL"
        candidates = universe.tickers.get(ticker.split(".", 1)[0])
    if not candidates:
        return None, NotCoveredReason.UNKNOWN_TICKER
    if len(candidates) > 1:
        return None, NotCoveredReason.AMBIGUOUS_TICKER
    (isin,) = candidates
    return isin, None


def _classify(
    identifier: str, universe: UniverseIndex
) -> tuple[IdentifierKind, str | None, NotCoveredReason | None] | InputErrorCode:
    if len(identifier) >= MIN_ISIN_ATTEMPT_LENGTH:
        problem = isin_problem(identifier)
        if problem is not None:
            return _ISIN_ERRORS[problem]
        reason = None if identifier in universe.isins else NotCoveredReason.OUTSIDE_UNIVERSE
        return IdentifierKind.ISIN, identifier, reason
    if _TICKER.fullmatch(identifier):
        isin, reason = _resolve_ticker(identifier, universe)
        return IdentifierKind.TICKER, isin, reason
    return InputErrorCode.INVALID_IDENTIFIER


def build_portfolio(
    raw_positions: Sequence[RawPosition], universe: UniverseIndex
) -> PortfolioInputResult:
    """Validate raw positions and compute weights over the whole portfolio."""
    errors: list[InputError] = []
    merged: dict[str, _Resolved] = {}

    for index, raw in enumerate(raw_positions, start=1):
        row = raw.row if raw.row is not None else index
        identifier = normalize_identifier(raw.identifier)

        if not math.isfinite(raw.amount_eur) or raw.amount_eur <= 0:
            errors.append(
                InputError(
                    code=InputErrorCode.NON_POSITIVE_AMOUNT, row=row, value=str(raw.amount_eur)
                )
            )
        if not identifier:
            errors.append(InputError(code=InputErrorCode.MISSING_IDENTIFIER, row=row))
            continue

        classified = _classify(identifier, universe)
        if isinstance(classified, InputErrorCode):
            errors.append(InputError(code=classified, row=row, value=identifier))
            continue

        kind, isin, reason = classified
        key = isin if isin is not None else f"unresolved:{identifier}"
        entry = merged.setdefault(key, _Resolved(kind=kind, isin=isin, reason=reason))
        if identifier not in entry.identifiers:
            entry.identifiers.append(identifier)
        entry.amount_eur += raw.amount_eur
        entry.rows.append(row)

    if not raw_positions and not errors:
        errors.append(InputError(code=InputErrorCode.EMPTY_PORTFOLIO))
    if errors:
        return PortfolioInputResult(portfolio=None, errors=tuple(errors))

    total = sum(entry.amount_eur for entry in merged.values())
    positions = tuple(
        Position(
            identifiers=tuple(entry.identifiers),
            kind=entry.kind,
            isin=entry.isin,
            amount_eur=entry.amount_eur,
            weight=entry.amount_eur / total,
            coverage=CoverageStatus.NOT_COVERED if entry.reason else CoverageStatus.COVERED,
            not_covered_reason=entry.reason,
            rows=tuple(entry.rows),
        )
        for entry in merged.values()
    )
    return PortfolioInputResult(portfolio=Portfolio(positions=positions, total_eur=total))


def portfolio_from_csv(data: bytes | str, universe: UniverseIndex) -> PortfolioInputResult:
    """Read a CSV and build the portfolio; reports reading and validation errors together."""
    raw_positions, read_errors = read_portfolio_csv(data)
    result = build_portfolio(raw_positions, universe)
    if not read_errors:
        return result
    if result.ok:
        return PortfolioInputResult(portfolio=None, errors=tuple(read_errors))
    build_errors = [e for e in result.errors if e.code is not InputErrorCode.EMPTY_PORTFOLIO]
    errors = sorted([*read_errors, *build_errors], key=lambda e: (e.row is None, e.row or 0))
    return PortfolioInputResult(portfolio=None, errors=tuple(errors))
