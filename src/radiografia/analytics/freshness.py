"""How old the holdings behind an analysis are, and whether that deserves a warning.

A fund's composition changes over time (index rebalancing, prices moving the weights), so an
analysis is a picture of the date of its holdings. Up to a month old the picture is close enough
for what the app shows; older than that the app says so. The date used is the oldest holdings
date among the funds analysed (the look-through's `data_as_of`). The synthetic demo is never
flagged: its dates are part of the invented data.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

STALE_AFTER_DAYS = 31


class DataFreshness(BaseModel):
    model_config = ConfigDict(frozen=True)

    holdings_as_of: date
    age_days: int
    stale: bool


def data_freshness(holdings_as_of: date | None, today: date) -> DataFreshness | None:
    if holdings_as_of is None:
        return None
    age = (today - holdings_as_of).days
    return DataFreshness(holdings_as_of=holdings_as_of, age_days=age, stale=age > STALE_AFTER_DAYS)
