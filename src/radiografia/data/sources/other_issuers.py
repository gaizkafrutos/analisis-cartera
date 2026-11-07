"""Holdings files of Xtrackers, Amundi and SPDR, as each user downloads them from the issuer.

None of these issuers allows automated downloads or reuse of its data without consent (quotes in
docs/FUENTES_Y_LICENCIAS.md), so the app only reads the file a person downloads for personal use
and uploads. Formats checked on files downloaded on 7-nov-2026 (docs/METODOLOGIA.md):

- Xtrackers, "Descargar la lista completa de componentes" / "Download full securities list"
  (`Constituent_<ISIN>.xlsx`): one sheet named after the export date; columns Name, ISIN,
  Country, Currency, Exchange, Type of Security, Rating, Primary Listing, Industry
  Classification, Weighting (fraction). Countries and sectors in the site's language. The file
  carries no holdings date: the sheet's date (the day it was exported) is used.
- Amundi, "Descargar todas las posiciones del fondo" (`Cartera del fondo_<name>_<ISIN>_<date>
  .xlsx`): a header block (fund name, ISIN, "Datos correctos a dd/mm/yyyy") and columns Código
  ISIN, Nombre, Tipo de activo, Divisa, Ponderación (fraction), Sector, País. No cash lines: the
  weights add up to a little under 100 %.
- SPDR, "Download Daily Holdings" (`holdings-daily-emea-en-<ticker>.xlsx`): a header block
  (Fund Name, ISIN, Holdings As Of) and columns ISIN, SEDOL, Security Name, Currency, Number of
  Shares, Percent of Fund (percent), Trade Country Name, Local Price, Sector Classification,
  Industry Classification, Base Market Value. Cash and futures lines have "-" as weight.
  The country is the trading country, not always the issuer's.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime

import pandas as pd

from radiografia.data.sources import labels, xlsx
from radiografia.data.sources.holdings_source import (
    HoldingsFormatError,
    ParsedHoldings,
    normalise,
)

_ASSET_CLASSES = {
    "renta variable": "Equity",
    "equity": "Equity",
    "equities": "Equity",
    "recibos de deposito": "Equity",
    "depositary receipts": "Equity",
    "cash": "Cash",
    "efectivo": "Cash",
    "futuro": "Futures",
    "future": "Futures",
    "futures": "Futures",
    "warrant": "Warrant",
    "warrants": "Warrant",
    "renta fija": "Fixed Income",
    "bond": "Fixed Income",
    "bonds": "Fixed Income",
    "fixed income": "Fixed Income",
}
_GICS = {
    "Communication",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
}
_ISIN = re.compile(r"(?<![A-Z0-9])([A-Z]{2}[A-Z0-9]{9}[0-9])(?![A-Z0-9])")
_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _asset_class(label: str) -> str | None:
    plain = " ".join(label.lower().split())
    return _ASSET_CLASSES.get(plain, label.strip() or None)


def _number(text: str) -> float:
    text = text.strip()
    if text in ("", "-", "N/A", "n/a"):
        return math.nan
    try:
        return float(text.replace(",", ""))
    except ValueError as exc:
        raise HoldingsFormatError(f"unexpected number {text!r}") from exc


def _header(rows: list[list[str]], required: set[str]) -> int | None:
    for index, row in enumerate(rows):
        if required <= {cell.strip() for cell in row}:
            return index
    return None


def _columns(header: list[str], wanted: dict[str, tuple[str, ...]]) -> dict[str, int]:
    names = [cell.strip() for cell in header]
    found = {}
    for key, options in wanted.items():
        position = next((names.index(o) for o in options if o in names), None)
        if position is None:
            raise HoldingsFormatError(f"column {options[0]!r} not found")
        found[key] = position
    return found


def _cell(row: list[str], position: int) -> str:
    return row[position] if position < len(row) else ""


def _first_sheet(content: bytes) -> list[list[str]] | None:
    if not xlsx.is_xlsx(content):
        return None
    try:
        return xlsx.read_sheet(content)
    except (xlsx.XlsxError, KeyError, ValueError):
        return None


def _frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        raise HoldingsFormatError("no holdings rows")
    return normalise(pd.DataFrame.from_records(records))


# --- Xtrackers ---------------------------------------------------------------------------------

_XTRACKERS_HEADER = {"Name", "ISIN", "Country", "Currency", "Type of Security", "Weighting"}


class XtrackersConstituents:
    issuer = "Xtrackers"

    def recognises(self, filename: str, content: bytes) -> bool:
        rows = _first_sheet(content)
        return rows is not None and _header(rows, _XTRACKERS_HEADER) is not None

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        try:
            sheet = xlsx.sheet_names(content)[0]
            rows = xlsx.read_sheet(content)
        except (xlsx.XlsxError, KeyError, ValueError) as exc:
            raise HoldingsFormatError(str(exc)) from exc
        try:
            as_of = date.fromisoformat(sheet)
        except ValueError as exc:
            raise HoldingsFormatError(f"export date not found (sheet {sheet!r})") from exc
        start = _header(rows, _XTRACKERS_HEADER)
        cols = _columns(
            rows[start],
            {
                "name": ("Name",),
                "isin": ("ISIN",),
                "country": ("Country",),
                "currency": ("Currency",),
                "exchange": ("Exchange",),
                "type": ("Type of Security",),
                "sector": ("Industry Classification",),
                "weight": ("Weighting",),
            },
        )
        records = []
        for row in rows[start + 1 :]:
            name = _cell(row, cols["name"])
            if not name:
                continue
            asset_class = _asset_class(_cell(row, cols["type"]))
            weight = _number(_cell(row, cols["weight"]))
            security = _cell(row, cols["isin"])
            exchange = _cell(row, cols["exchange"])
            future = asset_class == "Futures"
            records.append(
                {
                    "name": name,
                    "security_isin": None if security.startswith("_") else security or None,
                    "location": labels.country(_cell(row, cols["country"])),
                    "market_currency": _cell(row, cols["currency"]) or None,
                    "exchange": None if exchange in ("", "-") else exchange,
                    "asset_class": asset_class,
                    "sector": labels.sector(_cell(row, cols["sector"])),
                    "market_value": 0.0 if future else weight,
                    "notional_value": weight,
                    "weight_published": 0.0 if future else weight,
                }
            )
        match = _ISIN.search(filename.upper())
        return ParsedHoldings(
            self.issuer, as_of, _frame(records), fund_isin=match.group(1) if match else None
        )


# --- Amundi ------------------------------------------------------------------------------------

_AMUNDI_COLUMNS = {
    "isin": ("Código ISIN", "ISIN code", "ISIN Code", "ISIN"),
    "name": ("Nombre", "Name"),
    "type": ("Tipo de activo", "Asset class", "Asset Class"),
    "currency": ("Divisa", "Currency"),
    "weight": ("Ponderación", "Weight", "Weighting"),
    "sector": ("Sector",),
    "country": ("País", "Country"),
}


def _amundi_header(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        cells = {cell.strip() for cell in row}
        if all(any(o in cells for o in options) for options in _AMUNDI_COLUMNS.values()):
            return index
    return None


class AmundiHoldings:
    issuer = "Amundi"

    def recognises(self, filename: str, content: bytes) -> bool:
        rows = _first_sheet(content)
        if rows is None or _amundi_header(rows) is None:
            return False
        return any("Amundi" in cell for row in rows[:12] for cell in row)

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        try:
            rows = xlsx.read_sheet(content)
        except (xlsx.XlsxError, KeyError, ValueError) as exc:
            raise HoldingsFormatError(str(exc)) from exc
        start = _amundi_header(rows)
        fund_isin, as_of = None, None
        for row in rows[:start]:
            cells = [cell.strip() for cell in row]
            if any(c in ("Código ISIN", "ISIN code", "ISIN Code") for c in cells):
                found = _ISIN.search(" ".join(cells))
                fund_isin = found.group(1) if found else fund_isin
            text = " ".join(cells)
            if as_of is None or "correctos" in text.lower() or "as of" in text.lower():
                found = _DMY.search(text)
                if found and ("correctos" in text.lower() or "as of" in text.lower()):
                    day, month, year = (int(g) for g in found.groups())
                    as_of = date(year, month, day)
        if as_of is None:
            raise HoldingsFormatError("holdings date ('Datos correctos a') not found")
        cols = _columns(rows[start], _AMUNDI_COLUMNS)
        records = []
        for row in rows[start + 1 :]:
            name = _cell(row, cols["name"])
            if not name:
                continue
            asset_class = _asset_class(_cell(row, cols["type"]))
            weight = _number(_cell(row, cols["weight"]))
            future = asset_class == "Futures"
            records.append(
                {
                    "name": name,
                    "security_isin": _cell(row, cols["isin"]) or None,
                    "location": labels.country(_cell(row, cols["country"])),
                    "market_currency": _cell(row, cols["currency"]) or None,
                    "asset_class": asset_class,
                    "sector": labels.sector(_cell(row, cols["sector"])),
                    "market_value": 0.0 if future else weight,
                    "notional_value": weight,
                    "weight_published": 0.0 if future else weight,
                }
            )
        return ParsedHoldings(self.issuer, as_of, _frame(records), fund_isin=fund_isin)


# --- SPDR --------------------------------------------------------------------------------------

_SPDR_HEADER = {"ISIN", "Security Name", "Currency", "Percent of Fund", "Base Market Value"}


class SpdrDailyHoldings:
    issuer = "SPDR"

    def recognises(self, filename: str, content: bytes) -> bool:
        rows = _first_sheet(content)
        return (
            rows is not None
            and bool(rows)
            and bool(rows[0])
            and rows[0][0].startswith("Fund Name")
            and _header(rows, _SPDR_HEADER) is not None
        )

    def parse(self, filename: str, content: bytes) -> ParsedHoldings:
        try:
            rows = xlsx.read_sheet(content)
        except (xlsx.XlsxError, KeyError, ValueError) as exc:
            raise HoldingsFormatError(str(exc)) from exc
        start = _header(rows, _SPDR_HEADER)
        meta = {row[0].strip().rstrip(":"): row[1].strip() for row in rows[:start] if len(row) > 1}
        try:
            as_of = datetime.strptime(meta["Holdings As Of"], "%d-%b-%Y").date()
        except (KeyError, ValueError) as exc:
            raise HoldingsFormatError("holdings date ('Holdings As Of') not found") from exc
        cols = _columns(
            rows[start],
            {
                "isin": ("ISIN",),
                "name": ("Security Name",),
                "currency": ("Currency",),
                "weight": ("Percent of Fund",),
                "country": ("Trade Country Name",),
                "price": ("Local Price",),
                "sector": ("Sector Classification",),
                "value": ("Base Market Value",),
            },
        )
        records = []
        for row in rows[start + 1 :]:
            name = _cell(row, cols["name"])
            if not name or len(row) < len(rows[start]) - 2:
                continue  # blank line or the closing disclaimer
            weight = _number(_cell(row, cols["weight"]))
            value = _number(_cell(row, cols["value"]))
            sector = labels.sector(_cell(row, cols["sector"]))
            security = _cell(row, cols["isin"])
            if math.isnan(weight):  # cash and derivatives carry no weight
                price = _number(_cell(row, cols["price"]))
                asset_class = "Cash" if price == 1.0 or value == 0 else "Futures"
            else:
                asset_class = "Equity" if sector in _GICS else None
            future = asset_class == "Futures"
            records.append(
                {
                    "name": name,
                    "security_isin": None if security in ("", "Unassigned") else security,
                    "location": labels.country(_cell(row, cols["country"])),
                    "market_currency": _cell(row, cols["currency"]) or None,
                    "asset_class": asset_class,
                    "sector": sector,
                    "market_value": 0.0 if future else value,
                    "notional_value": value,
                    "weight_published": weight / 100 if not math.isnan(weight) else 0.0,
                }
            )
        found = _ISIN.search(meta.get("ISIN", ""))
        return ParsedHoldings(
            self.issuer, as_of, _frame(records), fund_isin=found.group(1) if found else None
        )
