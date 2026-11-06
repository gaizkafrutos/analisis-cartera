"""iShares (BlackRock) adapter: product page and product workbook from the UK site, in English.

Two documents per share class (see docs/FUENTES_Y_LICENCIAS.md):
    - Product page (HTML): exchange listings table and the page title, which marks currency-hedged
      share classes with "| Hedged".
    - Product workbook ("Download" button): an Excel 2003 XML file with sheets such as
      "Key Facts", "Holdings", "Exposure Breakdowns" and "Historical NAVs".

Parsing functions are pure (bytes/str in, data out) and tested with small fixtures. Only
`fetch()` touches the network, and it is only called from scripts/.

Licence note: the iShares terms allow personal, non-commercial use only. Raw downloads stay in
data/raw/ (git-ignored); only reference metadata (ISIN, TER, listings...) is committed.
"""

from __future__ import annotations

import io
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser

from radiografia.domain.fund import AssetClass, Fund, IncomeTreatment, Listing, Replication

ISSUER = "iShares"
SITE = "https://www.ishares.com"
_WORKBOOK_URL = (
    "https://www.blackrock.com/varnish-api/uk-retail01-product-data/product-data/api/v1/"
    "get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=ishares-uk"
    "&locale=en_GB&portfolioId={product_id}&component=fundDownloadV2&userType=individual"
)
_USER_AGENT = "radiografia-cartera/0.1 (personal educational project)"
_SS = "{urn:schemas-microsoft-com:office:spreadsheet}"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip


class IsharesFormatError(ValueError):
    """The issuer file does not have the expected shape: fail loudly, never guess."""


def product_page_url(product_path: str) -> str:
    return SITE + product_path


def workbook_url(product_id: str) -> str:
    return _WORKBOOK_URL.format(product_id=product_id)


def fetch(url: str, timeout: float = 60) -> bytes:
    """Download a document. Network access: call only from scripts/."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_issuer_date(text: str) -> date:
    """'25/Sept/2009' -> date(2009, 9, 25). iShares writes 'Sept' for September."""
    match = re.fullmatch(r"\s*(\d{1,2})/([A-Za-z]{3,4})/(\d{4})\s*", text)
    if not match or match.group(2).lower() not in _MONTHS:
        raise IsharesFormatError(f"unexpected date {text!r}")
    day, month, year = match.groups()
    return date(int(year), _MONTHS[month.lower()], int(day))


def parse_percent(text: str) -> float:
    """'0.20%' -> 0.002 (fraction)."""
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%\s*", text)
    if not match:
        raise IsharesFormatError(f"unexpected percentage {text!r}")
    return float(Decimal(match.group(1)) / 100)


# --- Workbook (Excel 2003 XML) -----------------------------------------------------------------


_BARE_AMPERSAND = re.compile(rb"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")


def read_worksheet(workbook: bytes, sheet_name: str) -> list[list[str]]:
    """Return the rows of one worksheet as lists of cell strings.

    The issuer's XML is not always well formed: names such as "S&P 500" contain a bare '&'.
    Those are escaped first (a documented repair, no content change). Python's bundled expat
    protects against entity-expansion attacks.
    """
    source = io.BytesIO(_BARE_AMPERSAND.sub(b"&amp;", workbook))
    for _, element in ET.iterparse(source, events=("end",)):
        if element.tag != f"{_SS}Worksheet":
            continue
        if element.get(f"{_SS}Name") == sheet_name:
            return [
                [(data.text or "").strip() for data in row.iter(f"{_SS}Data")]
                for row in element.iter(f"{_SS}Row")
            ]
        element.clear()
    raise IsharesFormatError(f"worksheet {sheet_name!r} not found")


def parse_key_facts(rows: Iterable[list[str]]) -> dict[str, str]:
    """'Key Facts' rows are [label, value] or [label, value, 'as of ...']."""
    facts = {}
    for row in rows:
        if len(row) >= 2 and row[0]:
            facts[row[0]] = row[1]
    return facts


# --- Product page (HTML) -----------------------------------------------------------------------

_LISTING_COLUMNS = {
    "colExchange": "exchange",
    "colTicker": "ticker",
    "colCurrencyCode": "currency",
    "colListingDate": "listing_date",
    # Bloomberg tickers and RICs are also on the page; they are vendor identifiers the app
    # does not need, so they are not stored.
}


class _ListingsParser(HTMLParser):
    """Collects <td class="colX ..."> cells of listing rows (rows that have a colExchange cell)."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, str] | None = None
        self._column: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = {}
        elif tag == "td" and self._row is not None:
            classes = (dict(attrs).get("class") or "").split()
            self._column = next(
                (_LISTING_COLUMNS[c] for c in classes if c in _LISTING_COLUMNS), None
            )
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._column is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._row is not None and self._column is not None:
            self._row[self._column] = "".join(self._text).strip()
            self._column = None
        elif tag == "tr" and self._row is not None:
            if "exchange" in self._row:
                self.rows.append(self._row)
            self._row = None


def _optional(value: str | None) -> str | None:
    return None if value in (None, "", "-") else value


def parse_listings(html: str, isin: str) -> list[Listing]:
    parser = _ListingsParser()
    parser.feed(html)
    listings = []
    for row in parser.rows:
        if not row.get("ticker") or not row.get("currency"):
            raise IsharesFormatError(f"incomplete listing row: {row}")
        listing_date = _optional(row.get("listing_date"))
        listings.append(
            Listing(
                isin=isin,
                exchange=row["exchange"],
                ticker=row["ticker"],
                currency=row["currency"],
                listing_date=parse_issuer_date(listing_date) if listing_date else None,
            )
        )
    if not listings:
        raise IsharesFormatError("no listings table found on the product page")
    return listings


def parse_page_title(html: str) -> str:
    """og:title, e.g. 'iShares Core Global Aggregate Bond UCITS ETF | AGGH | Hedged'."""
    for tag in re.findall(r"<meta\b[^>]*>", html):
        if re.search(r'(?:name|property)="og:title"', tag):
            content = re.search(r'content="([^"]*)"', tag)
            if content:
                return unescape(content.group(1))
    raise IsharesFormatError("og:title not found on the product page")


def name_from_title(title: str) -> str:
    """Fund name = first segment of the page title.

    Taken from the HTML page rather than the workbook: the workbook replaces '€' with U+FFFD.
    """
    return title.split("|")[0].strip()


def is_hedged_from_title(title: str) -> bool:
    """Currency-hedged share classes say 'Hedged' either as a title segment ('... | AGGH | Hedged')
    or in the fund name ('iShares MSCI World EUR Hedged UCITS ETF (Acc)'). Both forms were found
    on the iShares UK site in November 2026."""
    segments = [part.strip().lower() for part in title.split("|")]
    return "hedged" in segments or "hedged" in name_from_title(title).lower().split()


# --- Key facts -> Fund -------------------------------------------------------------------------

_ASSET_CLASSES = {"Equity": AssetClass.EQUITY, "Fixed Income": AssetClass.FIXED_INCOME}
_INCOME = {
    "Accumulating": IncomeTreatment.ACCUMULATING,
    "Distributing": IncomeTreatment.DISTRIBUTING,
}
_STRUCTURE = {"Physical": Replication.PHYSICAL, "Synthetic": Replication.SYNTHETIC}


def _first(facts: dict[str, str], *keys: str) -> str | None:
    """Labels vary between funds ('Fund Base Currency' vs 'Base Currency')."""
    for key in keys:
        value = facts.get(key, "").strip()
        if value:
            return value
    return None


def _required(facts: dict[str, str], *keys: str) -> str:
    value = _first(facts, *keys)
    if value is None:
        raise IsharesFormatError(f"key fact {keys[0]!r} missing")
    return value


def _optional_date(value: str | None) -> date | None:
    return parse_issuer_date(value) if value else None


def _mapped(facts: dict[str, str], key: str, mapping: dict[str, object]) -> object:
    value = _required(facts, key)
    if value not in mapping:
        raise IsharesFormatError(f"unknown {key!r} value {value!r}")
    return mapping[value]


def fund_from_documents(
    *,
    key_facts: dict[str, str],
    page_title: str,
    product_id: str,
    product_path: str,
    retrieved_on: date,
) -> Fund:
    """Build a Fund from the workbook's Key Facts and the product page title."""
    asset_class_raw = _required(key_facts, "Asset Class")
    return Fund(
        isin=_required(key_facts, "ISIN"),
        name=name_from_title(page_title),
        issuer=ISSUER,
        issuer_product_id=product_id,
        asset_class=_ASSET_CLASSES.get(asset_class_raw, AssetClass.OTHER),
        asset_class_raw=asset_class_raw,
        benchmark=_required(key_facts, "Benchmark Index"),
        ter=parse_percent(_required(key_facts, "Total Expense Ratio")),
        share_class_currency=_first(key_facts, "Share Class Currency"),
        base_currency=_required(key_facts, "Fund Base Currency", "Base Currency"),
        currency_hedged=is_hedged_from_title(page_title),
        income_treatment=_mapped(key_facts, "Use of Income", _INCOME),
        replication=_mapped(key_facts, "Product Structure", _STRUCTURE),
        methodology=_required(key_facts, "Methodology"),
        domicile=_required(key_facts, "Domicile"),
        fund_launch_date=parse_issuer_date(_required(key_facts, "Fund Launch Date")),
        share_class_launch_date=_optional_date(
            _first(key_facts, "Share Class Launch Date", "Inception Date")
        ),
        source_url=product_page_url(product_path),
        retrieved_on=retrieved_on,
    )
