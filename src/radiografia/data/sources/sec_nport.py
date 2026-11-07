"""SEC Form N-PORT (public filings of US registered funds): holdings and monthly returns.

The SEC publishes every US fund's monthly portfolio report about 60 days after month end.
Information on sec.gov "is considered public information and may be copied or further
distributed by users of the web site without the SEC's permission" (citing the SEC as source),
which is why the app's SEC mode can show it (see docs/FUENTES_Y_LICENCIAS.md).

What one filing (primary_doc.xml) gives, per holding: issuer name, LEI, ISIN and ticker (when
reported), country (`invCountry`, the issuer's country), currency, value in USD, % of net assets
and asset category. Per share class: the total return of the last three months. It does NOT give
sector, daily prices or the expense ratio.

The output uses the same columns as the iShares holdings (radiografia.data.snapshots), so the
engine needs no special case: `location` holds English country names (the labels the UI
translates), `sector` is empty, and `exchange` is "-".
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import pandas as pd

NS = {"n": "http://www.sec.gov/edgar/nport"}

# N-PORT asset categories -> the asset-class labels the engine already understands
ASSET_CLASSES = {
    "EC": "Equity",  # common equity
    "EP": "Equity",  # preferred equity
    "DBT": "Fixed Income",
    "ABS-MBS": "Fixed Income",
    "ABS-ASBS": "Fixed Income",
    "ABS-CBDO": "Fixed Income",
    "ABS-O": "Fixed Income",
    "STIV": "Money Market",  # short-term investment vehicles (money market funds)
    "RA": "Money Market",  # repurchase agreements
    "DE": "Futures",  # derivatives: equity
    "DIR": "Futures",
    "DCR": "Futures",
    "DFE": "FX",
    "DCO": "Futures",
    "DO": "Futures",
}

# ISO 3166-1 alpha-2 -> English name as used by the iShares files (the UI translates these)
COUNTRIES = {
    "US": "United States",
    "JP": "Japan",
    "GB": "United Kingdom",
    "CA": "Canada",
    "CH": "Switzerland",
    "FR": "France",
    "DE": "Germany",
    "NL": "Netherlands",
    "TW": "Taiwan",
    "CN": "China",
    "IN": "India",
    "KR": "Korea (South)",
    "AU": "Australia",
    "IT": "Italy",
    "ES": "Spain",
    "SE": "Sweden",
    "DK": "Denmark",
    "BR": "Brazil",
    "IE": "Ireland",
    "HK": "Hong Kong",
    "SA": "Saudi Arabia",
    "ZA": "South Africa",
    "BE": "Belgium",
    "FI": "Finland",
    "SG": "Singapore",
    "IL": "Israel",
    "NO": "Norway",
    "MX": "Mexico",
    "AT": "Austria",
    "PT": "Portugal",
    "NZ": "New Zealand",
    "LU": "Luxembourg",
    "ID": "Indonesia",
    "TH": "Thailand",
    "MY": "Malaysia",
    "PH": "Philippines",
    "AE": "United Arab Emirates",
    "QA": "Qatar",
    "KW": "Kuwait",
    "TR": "Turkey",
    "PL": "Poland",
    "GR": "Greece",
    "CL": "Chile",
    "PE": "Peru",
    "CO": "Colombia",
    "HU": "Hungary",
    "CZ": "Czech Republic",
    "EG": "Egypt",
    "BM": "Bermuda",
    "KY": "Cayman Islands",
    "JE": "Jersey",
    "GG": "Guernsey",
    "IM": "Isle of Man",
    "CW": "Curacao",
    "LR": "Liberia",
    "PA": "Panama",
    "MO": "Macau",
    "VG": "British Virgin Islands",
}

HOLDING_COLUMNS = [
    "ticker",
    "name",
    "sector",
    "asset_class",
    "location",
    "exchange",
    "market_currency",
    "market_value",
    "notional_value",
    "weight_published",
    "security_isin",
    "lei",
]


class NportFormatError(ValueError):
    """The filing does not have the structure this reader expects."""


@dataclass(frozen=True)
class NportFiling:
    series_id: str
    series_name: str
    report_date: date
    holdings: pd.DataFrame
    """One row per holding, HOLDING_COLUMNS (no fund ISIN: the caller adds it)."""
    monthly_returns: pd.DataFrame
    """class_id, month_end, total_return (fraction): the three months of the report."""


def _text(element: ET.Element | None, path: str) -> str | None:
    found = element.find(path, NS) if element is not None else None
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def _identifier(holding: ET.Element, kind: str) -> str | None:
    found = holding.find(f"n:identifiers/n:{kind}", NS)
    value = found.get("value") if found is not None else None
    return value.strip() if value and value.strip() not in {"", "N/A", "000000000"} else None


def _currency(holding: ET.Element) -> str | None:
    code = _text(holding, "n:curCd")
    if code:
        return code
    conditional = holding.find("n:currencyConditional", NS)  # non-USD holdings
    return conditional.get("curCd") if conditional is not None else None


def _lei(holding: ET.Element) -> str | None:
    lei = _text(holding, "n:lei")
    return lei if lei and lei != "N/A" else None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _month_ends(report_date: date) -> list[date]:
    """rtn1, rtn2, rtn3 are the months ending 2, 1 and 0 months before the report date."""
    end = pd.Timestamp(report_date)
    return [(end - pd.offsets.MonthEnd(k)).date() if k else end.date() for k in (2, 1, 0)]


def parse_nport(xml: bytes | str) -> NportFiling:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise NportFormatError(f"not valid XML: {error}") from error
    general = root.find(".//n:genInfo", NS)
    series_id = _text(general, "n:seriesId")
    series_name = _text(general, "n:seriesName")
    report = _text(general, "n:repPdDate")
    if not (series_id and report):
        raise NportFormatError("missing seriesId or repPdDate")
    report_date = date.fromisoformat(report)

    rows = []
    for holding in root.iterfind(".//n:invstOrSecs/n:invstOrSec", NS):
        category = _text(holding, "n:assetCat") or ""
        country = _text(holding, "n:invCountry")
        value = _float(_text(holding, "n:valUSD"))
        rows.append(
            {
                "ticker": _identifier(holding, "ticker"),
                "name": _text(holding, "n:name") or _text(holding, "n:title"),
                "sector": None,  # N-PORT does not report sectors
                "asset_class": ASSET_CLASSES.get(category, "Other"),
                "location": COUNTRIES.get(country, country) if country else "-",
                "exchange": "-",
                "market_currency": _currency(holding),
                "market_value": value,
                "notional_value": value,
                "weight_published": (_float(_text(holding, "n:pctVal")) or 0.0) / 100,
                "security_isin": _identifier(holding, "isin"),
                "lei": _lei(holding),
            }
        )
    if not rows:
        raise NportFormatError("no holdings in the filing")

    returns = []
    for entry in root.iterfind(".//n:returnInfo/n:monthlyTotReturns/n:monthlyTotReturn", NS):
        for month_end, attribute in zip(
            _month_ends(report_date), ("rtn1", "rtn2", "rtn3"), strict=True
        ):
            value = _float(entry.get(attribute))
            if value is not None:
                returns.append(
                    {
                        "class_id": entry.get("classId"),
                        "month_end": month_end,
                        "total_return": value / 100,
                    }
                )
    return NportFiling(
        series_id=series_id,
        series_name=series_name or series_id,
        report_date=report_date,
        holdings=pd.DataFrame(rows, columns=HOLDING_COLUMNS),
        monthly_returns=pd.DataFrame(returns, columns=["class_id", "month_end", "total_return"]),
    )


def harmonise_companies(holdings: pd.DataFrame) -> pd.DataFrame:
    """Same company, same name and country in every fund (needed to measure overlap).

    Each fund writes names its own way ('Alphabet, Inc.' / 'ALPHABET INC.'). Lines with the same
    LEI (the global legal-entity code) get one name and country: the most frequent spelling,
    ties broken alphabetically. Lines without LEI keep their own.
    """
    with_lei = holdings["lei"].notna()
    if not with_lei.any():
        return holdings
    canonical = (
        holdings[with_lei]
        .groupby(["lei", "name", "location"])
        .size()
        .reset_index(name="n")
        .sort_values(["lei", "n", "name"], ascending=[True, False, True])
        .drop_duplicates("lei")
        .set_index("lei")
    )
    result = holdings.copy()
    result.loc[with_lei, "name"] = result.loc[with_lei, "lei"].map(canonical["name"])
    result.loc[with_lei, "location"] = result.loc[with_lei, "lei"].map(canonical["location"])
    return result
