"""Fund (ETF share class) reference data.

Every field comes from an official issuer document; `source_url` and `retrieved_on` record where
and when. Nothing is filled in by hand or guessed (see CLAUDE.md, "Reglas de datos").
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from radiografia.domain.isin import is_valid_isin

MAX_PLAUSIBLE_TER = 0.03  # 3 % a year: far above any ETF in scope; catches unit errors (20 vs 0.20)


class AssetClass(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    OTHER = "other"


class IncomeTreatment(StrEnum):
    ACCUMULATING = "accumulating"
    DISTRIBUTING = "distributing"


class Replication(StrEnum):
    PHYSICAL = "physical"
    SYNTHETIC = "synthetic"


class Listing(BaseModel):
    """One exchange where the share class trades. Same ISIN, different ticker and currency."""

    model_config = ConfigDict(frozen=True)

    isin: str
    exchange: str
    ticker: str
    currency: str
    listing_date: date | None = None


class Fund(BaseModel):
    model_config = ConfigDict(frozen=True)

    isin: str
    name: str
    issuer: str
    issuer_product_id: str
    asset_class: AssetClass
    asset_class_raw: str
    """Issuer's own label (e.g. 'Commodity' maps to OTHER)."""
    benchmark: str
    ter: float
    """Total expense ratio as a fraction per year (0.002 = 0.20 %)."""
    share_class_currency: str | None
    """None when the issuer does not publish it (not inferred from the base currency)."""
    base_currency: str | None
    """None when the issuer does not publish it on the documents used (not inferred)."""
    currency_hedged: bool
    income_treatment: IncomeTreatment
    replication: Replication
    methodology: str
    """Issuer label: 'Replicated' (holds every index member) or 'Optimised'/'Sampled'."""
    domicile: str
    fund_launch_date: date
    share_class_launch_date: date | None
    """None when the issuer only publishes the fund's launch date (not inferred)."""
    source_url: str
    retrieved_on: date

    @field_validator("isin")
    @classmethod
    def _valid_isin(cls, value: str) -> str:
        if not is_valid_isin(value):
            raise ValueError(f"invalid ISIN {value!r}")
        return value

    @field_validator("ter")
    @classmethod
    def _plausible_ter(cls, value: float) -> float:
        if not 0 <= value <= MAX_PLAUSIBLE_TER:
            raise ValueError(f"TER {value} outside [0, {MAX_PLAUSIBLE_TER}]: check units")
        return value
