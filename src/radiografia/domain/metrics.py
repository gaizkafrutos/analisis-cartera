"""Common result type for every metric (see CLAUDE.md, "Reglas de arquitectura").

A MetricResult carries the number *and* what is needed to read it honestly: how much of the
portfolio it covers, the uncertainty interval when there is one, the time window and number of
observations, the date of the underlying data and warning keys. User-facing texts live in
`radiografia.reporting.texts`, looked up by `key` and warning keys.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    """Computed on the covered part of the portfolio only."""
    NOT_AVAILABLE = "not_available"


class Unit(StrEnum):
    FRACTION = "fraction"
    """Shown as a percentage (0.002 -> 0,20 %)."""
    EUR = "eur"
    EUR_PER_YEAR = "eur_per_year"
    RATIO = "ratio"


class Coverage(BaseModel):
    """Share of the portfolio the metric could use. Weights are fractions of the total value."""

    model_config = ConfigDict(frozen=True)

    covered_weight: float
    covered_amount_eur: float
    not_covered_amount_eur: float

    @property
    def not_covered_weight(self) -> float:
        return 1.0 - self.covered_weight


class Interval(BaseModel):
    """Uncertainty range (e.g. a confidence interval). Phase 2 scenarios reuse it."""

    model_config = ConfigDict(frozen=True)

    low: float
    high: float
    confidence: float

    @model_validator(mode="after")
    def _ordered(self) -> Interval:
        if self.low > self.high or not 0 < self.confidence < 1:
            raise ValueError("interval needs low <= high and 0 < confidence < 1")
        return self


class MetricResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    """Identifies the metric; texts are looked up with it in reporting.texts."""
    value: float | None
    unit: Unit
    status: MetricStatus
    coverage: Coverage
    interval: Interval | None = None
    window_start: date | None = None
    window_end: date | None = None
    observations: int | None = None
    data_as_of: date | None = None
    """Date of the oldest input datum used (e.g. when TERs were retrieved)."""
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> MetricResult:
        if (self.value is None) != (self.status is MetricStatus.NOT_AVAILABLE):
            raise ValueError("value must be None exactly when the metric is not available")
        return self
