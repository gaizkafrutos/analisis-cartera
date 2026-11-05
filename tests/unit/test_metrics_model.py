import pytest
from pydantic import ValidationError

from radiografia.domain.metrics import Coverage, Interval, MetricResult, MetricStatus, Unit

COVERAGE = Coverage(covered_weight=1.0, covered_amount_eur=100, not_covered_amount_eur=0)


def test_value_must_match_status():
    with pytest.raises(ValidationError):
        MetricResult(
            key="x", value=None, unit=Unit.RATIO, status=MetricStatus.AVAILABLE, coverage=COVERAGE
        )
    with pytest.raises(ValidationError):
        MetricResult(
            key="x",
            value=1.0,
            unit=Unit.RATIO,
            status=MetricStatus.NOT_AVAILABLE,
            coverage=COVERAGE,
        )


def test_interval_must_be_ordered_with_valid_confidence():
    assert Interval(low=-0.01, high=0.03, confidence=0.95).high == 0.03
    with pytest.raises(ValidationError):
        Interval(low=0.03, high=-0.01, confidence=0.95)
    with pytest.raises(ValidationError):
        Interval(low=0, high=1, confidence=95)


def test_not_covered_weight():
    coverage = Coverage(covered_weight=0.9, covered_amount_eur=90, not_covered_amount_eur=10)
    assert coverage.not_covered_weight == pytest.approx(0.1)
