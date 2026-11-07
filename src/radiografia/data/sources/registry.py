"""Every issuer's holdings reader, in the order they are tried on an uploaded file."""

from __future__ import annotations

from radiografia.data.sources.holdings_source import HoldingsSource
from radiografia.data.sources.ishares_holdings import IsharesHoldingsCsv, IsharesWorkbook
from radiografia.data.sources.other_issuers import (
    AmundiHoldings,
    SpdrDailyHoldings,
    XtrackersConstituents,
)

HOLDINGS_SOURCES: tuple[HoldingsSource, ...] = (
    IsharesHoldingsCsv(),
    IsharesWorkbook(),
    XtrackersConstituents(),
    AmundiHoldings(),
    SpdrDailyHoldings(),
)
