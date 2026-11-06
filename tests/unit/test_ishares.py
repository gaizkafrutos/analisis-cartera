"""iShares parsers, tested on small synthetic documents shaped like the real ones."""

from datetime import date

import pytest

from radiografia.data.sources import ishares
from radiografia.domain.fund import AssetClass, IncomeTreatment, Replication

WORKBOOK = b"""<?xml version="1.0"?>
<ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
<ss:Worksheet ss:Name="Fund Header"><ss:Table>
<ss:Row><ss:Cell>
<ss:Data ss:Type="String">iShares Core S&P 500 UCITS ETF</ss:Data>
</ss:Cell></ss:Row>
</ss:Table></ss:Worksheet>
<ss:Worksheet ss:Name="Key Facts"><ss:Table>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Net Assets of Fund</ss:Data></ss:Cell>
<ss:Cell><ss:Data ss:Type="String">USD 1,000</ss:Data></ss:Cell>
<ss:Cell><ss:Data ss:Type="String">as of 04/Nov/2026</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">Total Expense Ratio</ss:Data></ss:Cell>
<ss:Cell><ss:Data ss:Type="String">0.07%</ss:Data></ss:Cell></ss:Row>
<ss:Row><ss:Cell><ss:Data ss:Type="String">ISIN</ss:Data></ss:Cell>
<ss:Cell><ss:Data ss:Type="String">IE00B5BMR087</ss:Data></ss:Cell></ss:Row>
</ss:Table></ss:Worksheet>
</ss:Workbook>"""

LISTINGS_HTML = """
<table><tbody>
<tr class="dataTable-data-row">
 <td class="colExchange oneds-body-m-compact left-align">Deutsche Boerse Xetra</td>
 <td class="colTicker oneds-body-m-compact">SXR8</td>
 <td class="colCurrencyCode oneds-body-m-compact">EUR</td>
 <td class="colListingDate oneds-body-m-compact">25/Sept/2010</td>
 <td class="colSedol oneds-body-m-compact">B3XXRP0</td>
 <td class="colBBEQTICK oneds-body-m-compact">SXR8 GY</td>
 <td class="colRic oneds-body-m-compact">SXR8.DE</td>
</tr>
<tr class="dataTable-data-row">
 <td class="colExchange">Bolsa Mexicana De Valores</td><td class="colTicker">CSPX</td>
 <td class="colCurrencyCode">MXN</td><td class="colListingDate">-</td>
 <td class="colBBEQTICK">CSPXN MM</td><td class="colRic">-</td>
</tr>
<tr><td class="colFund">unrelated table row</td></tr>
</tbody></table>
"""

KEY_FACTS = {
    "ISIN": "IE00B5BMR087",
    "Total Expense Ratio": "0.07%",
    "Asset Class": "Equity",
    "Benchmark Index": "S&P 500",
    "Share Class Currency": "USD",
    "Base Currency": "USD",
    "Use of Income": "Accumulating",
    "Product Structure": "Physical",
    "Methodology": "Replicated",
    "Domicile": "Ireland",
    "Fund Launch Date": "19/May/2010",
    "Inception Date": "19/May/2010",
}


def _fund(**overrides):
    facts = {**KEY_FACTS, **overrides}
    return ishares.fund_from_documents(
        key_facts={k: v for k, v in facts.items() if v is not None},
        page_title="iShares Core S&P 500 UCITS ETF | CSPX",
        product_id="253743",
        product_path="/uk/individual/en/products/253743/x",
        retrieved_on=date(2026, 11, 5),
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("25/Sept/2009", date(2009, 9, 25)),
        ("04/Nov/2026", date(2026, 11, 4)),
        (" 1/Jan/2010 ", date(2010, 1, 1)),
    ],
)
def test_issuer_dates(text, expected):
    assert ishares.parse_issuer_date(text) == expected


@pytest.mark.parametrize("text", ["2009-09-25", "25/Sep/09", "31/Foo/2020"])
def test_bad_dates_fail_loudly(text):
    with pytest.raises(ishares.IsharesFormatError):
        ishares.parse_issuer_date(text)


def test_percent_is_converted_to_fraction():
    assert ishares.parse_percent("0.20%") == pytest.approx(0.002)
    assert ishares.parse_percent("0.07 %") == pytest.approx(0.0007)
    with pytest.raises(ishares.IsharesFormatError):
        ishares.parse_percent("0.20")


def test_read_worksheet_repairs_bare_ampersands_and_picks_the_sheet():
    assert ishares.read_worksheet(WORKBOOK, "Fund Header") == [["iShares Core S&P 500 UCITS ETF"]]
    facts = ishares.parse_key_facts(ishares.read_worksheet(WORKBOOK, "Key Facts"))
    assert facts == {
        "Net Assets of Fund": "USD 1,000",
        "Total Expense Ratio": "0.07%",
        "ISIN": "IE00B5BMR087",
    }


def test_missing_worksheet():
    with pytest.raises(ishares.IsharesFormatError, match="Holdings"):
        ishares.read_worksheet(WORKBOOK, "Holdings")


def test_listings():
    listings = ishares.parse_listings(LISTINGS_HTML, "IE00B5BMR087")
    assert [(li.exchange, li.ticker, li.currency) for li in listings] == [
        ("Deutsche Boerse Xetra", "SXR8", "EUR"),
        ("Bolsa Mexicana De Valores", "CSPX", "MXN"),
    ]
    assert listings[0].listing_date == date(2010, 9, 25)
    # vendor identifiers (Bloomberg ticker, RIC) are on the page but not kept
    kept = {"isin", "exchange", "ticker", "currency", "listing_date"}
    assert set(listings[0].model_dump()) == kept
    assert listings[1].listing_date is None  # "-" means not published


def test_no_listings_is_an_error():
    with pytest.raises(ishares.IsharesFormatError):
        ishares.parse_listings("<table></table>", "IE00B5BMR087")


@pytest.mark.parametrize(
    "meta",
    [
        '<meta name="og:title" content="iShares Core € Govt Bond UCITS ETF | SEGA"/>',
        '<meta content="iShares Core € Govt Bond UCITS ETF | SEGA" property="og:title">',
    ],
)
def test_page_title_in_any_attribute_order(meta):
    html = f"<html><head><meta charset='utf-8'>{meta}</head></html>"
    assert ishares.parse_page_title(html) == "iShares Core € Govt Bond UCITS ETF | SEGA"
    assert ishares.name_from_title(ishares.parse_page_title(html)) == (
        "iShares Core € Govt Bond UCITS ETF"
    )


@pytest.mark.parametrize(
    ("title", "hedged"),
    [
        ("iShares Core Global Aggregate Bond UCITS ETF | AGGH | Hedged", True),
        ("iShares MSCI World EUR Hedged UCITS ETF (Acc) | IWDE", True),
        ("iShares Core MSCI World UCITS ETF | SWDA", False),
        ("iShares Hedgedfund Style ETF | XYZ", False),  # whole words only
    ],
)
def test_hedged_detection(title, hedged):
    assert ishares.is_hedged_from_title(title) is hedged


def test_fund_from_documents():
    fund = _fund()
    assert fund.name == "iShares Core S&P 500 UCITS ETF"
    assert fund.ter == pytest.approx(0.0007)
    assert fund.asset_class is AssetClass.EQUITY
    assert fund.income_treatment is IncomeTreatment.ACCUMULATING
    assert fund.replication is Replication.PHYSICAL
    assert fund.base_currency == "USD"  # 'Base Currency' alias accepted
    assert fund.share_class_launch_date == date(2010, 5, 19)  # 'Inception Date' alias
    assert fund.source_url == "https://www.ishares.com/uk/individual/en/products/253743/x"


def test_optional_fields_stay_empty_instead_of_being_guessed():
    fund = _fund(**{"Share Class Currency": None, "Inception Date": None})
    assert fund.share_class_currency is None
    assert fund.share_class_launch_date is None


def test_unknown_asset_class_maps_to_other_and_keeps_raw_label():
    fund = _fund(**{"Asset Class": "Commodity"})
    assert fund.asset_class is AssetClass.OTHER
    assert fund.asset_class_raw == "Commodity"


@pytest.mark.parametrize(
    ("key", "value"),
    [("Use of Income", "Reinvesting"), ("Product Structure", "Hybrid"), ("ISIN", None)],
)
def test_unexpected_or_missing_values_fail_loudly(key, value):
    with pytest.raises(ishares.IsharesFormatError):
        _fund(**{key: value})


def test_implausible_ter_is_rejected():
    # "20%" would be a unit error (e.g. 0.20 % typed as 20 %)
    with pytest.raises(ValueError, match="TER"):
        _fund(**{"Total Expense Ratio": "20%"})


def test_page_title_html_entities_are_unescaped():
    html = '<meta name="og:title" content="iShares Core S&amp;P 500 UCITS ETF | CSPX">'
    assert ishares.parse_page_title(html) == "iShares Core S&P 500 UCITS ETF | CSPX"
