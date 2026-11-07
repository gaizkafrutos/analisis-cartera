"""Minimal reader for .xlsx workbooks (Office Open XML), standard library only.

Issuers publish holdings as .xlsx; reading them only needs the cell values of one sheet, so a
small reader avoids a new dependency. A workbook is a zip of XML parts: `xl/workbook.xml` names
the sheets, `xl/_rels/workbook.xml.rels` maps them to files, `xl/sharedStrings.xml` holds the
text, and each `xl/worksheets/sheetN.xml` holds rows of cells. Python's bundled expat protects
against entity-expansion attacks; the archive's size is bounded by the upload limit.

Values come back as text exactly as stored: numbers as their decimal representation, dates as
Excel serial numbers (see `excel_date`), booleans as "0"/"1". Formulas give their cached value.
"""

from __future__ import annotations

import io
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_COLUMN = re.compile(r"([A-Z]+)")
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # a zip bomb would exceed this


class XlsxError(ValueError):
    """Not a readable .xlsx workbook."""


def is_xlsx(content: bytes) -> bool:
    return content.startswith(b"PK\x03\x04")


def _column_index(reference: str) -> int:
    letters = _COLUMN.match(reference).group(1)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - 64
    return index - 1


def _text(element: ET.Element) -> str:
    """Text of a shared string or inline string: plain <t>, or rich-text runs <r><t>."""
    return "".join(t.text or "" for t in element.iter(f"{_MAIN}t"))


def sheet_names(content: bytes) -> list[str]:
    with _open(content) as book:
        root = ET.fromstring(book.read("xl/workbook.xml"))
    return [sheet.get("name") for sheet in root.iter(f"{_MAIN}sheet")]


def _open(content: bytes) -> zipfile.ZipFile:
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise XlsxError("not a zip archive") from exc
    if sum(info.file_size for info in book.infolist()) > MAX_UNCOMPRESSED_BYTES:
        raise XlsxError("workbook too large once uncompressed")
    if "xl/workbook.xml" not in book.namelist():
        raise XlsxError("not an Excel workbook")
    return book


def read_sheet(content: bytes, name: str | None = None) -> list[list[str]]:
    """Rows of one sheet (the first if `name` is None) as lists of cell texts ('' when empty)."""
    with _open(content) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = list(workbook.iter(f"{_MAIN}sheet"))
        sheet = next((s for s in sheets if name is None or s.get("name") == name), None)
        if sheet is None:
            raise XlsxError(f"sheet {name!r} not found")
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(f"{_PKG_REL}Relationship")}
        target = targets[sheet.get(f"{_REL}id")]
        path = target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = [_text(item) for item in strings.iter(f"{_MAIN}si")]
        root = ET.fromstring(book.read(path))

    rows: list[list[str]] = []
    for row in root.iter(f"{_MAIN}row"):
        cells: dict[int, str] = {}
        for position, cell in enumerate(row.iter(f"{_MAIN}c")):
            reference = cell.get("r")
            column = _column_index(reference) if reference else position
            kind = cell.get("t")
            if kind == "inlineStr":
                inline = cell.find(f"{_MAIN}is")
                value = _text(inline) if inline is not None else ""
            else:
                raw = cell.findtext(f"{_MAIN}v") or ""
                value = shared[int(raw)] if kind == "s" and raw else raw
            cells[column] = value.strip()
        index = int(row.get("r", len(rows) + 1)) - 1
        while len(rows) < index:
            rows.append([])
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def excel_date(serial: str) -> date:
    """Excel serial day number (1900 system, as Excel counts it) to a date."""
    return date(1899, 12, 30) + timedelta(days=int(float(serial)))
