"""Presentation helpers: rows for the charts."""

import pytest


def test_reference_column_shares_the_scale_of_the_portfolio():
    from radiografia.domain.metrics import BreakdownItem
    from radiografia.reporting.presentation import REST_NAME, with_reference

    mine = [BreakdownItem(label=c, weight=w) for c, w in (("US", 0.7), ("JP", 0.2), ("FR", 0.1))]
    world = [BreakdownItem(label=c, weight=w) for c, w in (("US", 0.6), ("FR", 0.3), ("CN", 0.1))]
    rows = with_reference(mine, world, n=2)
    assert rows == [
        ("US", 0.7, 0.6),
        ("JP", 0.2, 0.0),  # the reference holds no Japan in this example
        (REST_NAME, pytest.approx(0.1), pytest.approx(0.4)),  # FR + CN outside the rows shown
    ]
    assert [r[2] for r in with_reference(mine, None, n=2)] == [None, None, None]
