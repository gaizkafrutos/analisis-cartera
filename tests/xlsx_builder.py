"""Build tiny .xlsx workbooks for tests (synthetic issuer files), standard library only."""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml"
 ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml"
 ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
 Target="xl/workbook.xml"/>
</Relationships>"""
_BOOK_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId7"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
 Target="worksheets/sheet1.xml"/>
</Relationships>"""
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def build_xlsx(rows: list[list[object]], sheet: str = "Sheet1", shared: bool = False) -> bytes:
    """Numbers become numeric cells; text becomes inline strings (or shared ones)."""
    strings: list[str] = []
    xml_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{_column(c)}{r}"
            if value is None or value == "":
                continue
            if isinstance(value, int | float):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            elif shared:
                strings.append(str(value))
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    sheet_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{_MAIN}">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )
    workbook = (
        f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{_MAIN}" xmlns:r="{_REL}">'
        f'<sheets><sheet name="{escape(sheet)}" sheetId="1" r:id="rId7"/></sheets></workbook>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", _CONTENT_TYPES)
        book.writestr("_rels/.rels", _ROOT_RELS)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", _BOOK_RELS)
        book.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        if shared:
            items = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
            book.writestr(
                "xl/sharedStrings.xml",
                f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{_MAIN}">{items}</sst>',
            )
    return buffer.getvalue()


# Synthetic files in each issuer's format (companies, ISINs and weights are invented).


def xtrackers_file() -> bytes:
    header = ["", "Name", "ISIN", "Country", "Currency", "Exchange", "Type of Security",
              "Rating", "Primary Listing", "Industry Classification", "Weighting"]  # fmt: skip
    rows = [
        [],
        ["Aunque la información contenida en este documento se ha obtenido de fuentes fiables..."],
        [],
        header,
        ["1", "ALFA SYNTHETIC", "US0000000AA1", "Estados Unidos", "USD", "NASDAQ",
         "Renta Variable", "-", "-", "Tecnologías de la Información", 0.40],
        ["2", "BETA SYNTHETIC", "US0000000BB2", "Estados Unidos", "USD", "NYSE",
         "Renta Variable", "-", "-", "Finanzas", 0.20],
        ["3", "GAMMA SYNTHETIC AG", "DE0000000CC3", "Alemania", "EUR", "Xetra",
         "Renta Variable", "-", "-", "Industrial", 0.15],
        ["4", "DELTA SYNTHETIC KK", "JP0000000DD4", "Japón", "JPY", "Tokyo",
         "Renta Variable", "-", "-", "Consumo Discrecional", 0.10],
        ["5", "EPSILON SYNTHETIC PLC", "GB0000000EE5", "Reino Unido", "GBP", "London",
         "Renta Variable", "-", "-", "Salud", 0.10],
        ["6", "US DOLLAR", "_CURRENCYUSD", "Estados Unidos", "USD", "-", "Cash", "-", "-",
         "desconocido", 0.05],
        ["7", "SYNTHETIC INDEX DEC26", "___FUT0001", "Alemania", "USD", "-", "Futuro", "-", "-",
         "desconocido", "N/A"],
    ]  # fmt: skip
    return build_xlsx(rows, sheet="2026-10-31")


def amundi_file() -> bytes:
    rows = [
        ["", ""],
        [],
        ["", "Amundi ETF"],
        ["", "CARTERA DEL FONDO"],
        ["", "Nombre del fondo", "Amundi Core MSCI World UCITS ETF Acc"],
        ["", "Código ISIN", "IE000BI8OT95"],
        ["", "Tenga en cuenta que los datos pueden cambiar. Datos correctos a 30/10/2026."],
        ["", "Código ISIN", "Nombre", "Tipo de activo", "Divisa", "Ponderación", "Sector", "País"],
        ["", "US0000000AA1", "ALFA SYNTHETIC INC", "EQUITY", "USD", 0.40,
         "Tecnología de la información", "Estados Unidos"],
        ["", "US0000000BB2", "BETA SYNTHETIC CORP", "EQUITY", "USD", 0.20, "Finanzas",
         "Estados Unidos"],
        ["", "DE0000000CC3", "GAMMA SYNTHETIC AG", "EQUITY", "EUR", 0.15, "Industriales",
         "Alemania"],
        ["", "JP0000000DD4", "DELTA SYNTHETIC KK", "EQUITY", "JPY", 0.10,
         "Consumo discrecional", "Japón"],
        ["", "GB0000000EE5", "EPSILON SYNTHETIC PLC", "EQUITY", "GBP", 0.10,
         "Atención sanitaria", "Países Bajos"],
        ["", "DE000FUT0002", "SYNTHETIC INDEX 12/26", "FUTURE", "USD", 0.004, "",
         "Estados Unidos"],
        [],
        ["", "Fuente : Amundi Asset Management"],
    ]  # fmt: skip
    return build_xlsx(rows, sheet="Cartera del fondo", shared=True)


def spdr_file() -> bytes:
    rows = [
        ["Fund Name:", "State Street SPDR MSCI All Country World UCITS ETF (Acc)"],
        ["ISIN:", "IE00B44Z5B48"],
        ["Ticker Symbol:", "SPYY GY"],
        ["Holdings As Of:", "29-Oct-2026"],
        [],
        ["ISIN", "SEDOL", "Security Name", "Currency", "Number of Shares", "Percent of Fund",
         "Trade Country Name", "Local Price", "Sector Classification",
         "Industry Classification", "Base Market Value"],
        ["US0000000AA1", "0000001", "Alfa Synthetic Inc.", "USD", 40.0, 40.0, "United States",
         100.0, "Information Technology", "Software", 4000.0],
        ["US0000000BB2", "0000002", "Beta Synthetic Corporation", "USD", 20.0, 20.0,
         "United States", 100.0, "Financials", "Banks", 2000.0],
        ["KR0000000FF6", "0000003", "Zeta Synthetic Co", "KRW", 40.0, 40.0, "South Korea", 100.0,
         "Communication Services", "Media", 4000.0],
        ["Unassigned", "Unassigned", "Euro", "EUR", 50.0, "-", "European Union", 1.0,
         "Unassigned", "Unassigned", 50.0],
        ["Unassigned", "Unassigned", "SYNTH EMINI DEC26", "USD", 1.0, "-", "None", 900.0,
         "Unassigned", "Unassigned", 900.0],
        [],
        ["Marketing communication. The whole or any part of this work may not be reproduced..."],
    ]  # fmt: skip
    return build_xlsx(rows, sheet="holdings")
