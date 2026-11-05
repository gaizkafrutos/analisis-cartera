"""Minimal view of the fund universe needed to resolve user input.

Step 3 builds this from `data/reference/universe.csv`; input handling only needs to know which
ISINs exist and which ISINs each ticker can refer to.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class UniverseIndex:
    """ISINs in the universe and, per ticker, the ISINs it may refer to.

    A ticker can map to several ISINs because the same ticker can be used on different exchanges
    for different products; resolution then fails as ambiguous instead of guessing.
    """

    isins: frozenset[str]
    tickers: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = {isin for isins in self.tickers.values() for isin in isins} - self.isins
        if unknown:
            raise ValueError(f"tickers point to ISINs outside the universe: {sorted(unknown)}")
