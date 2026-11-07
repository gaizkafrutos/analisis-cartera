"""Readers of Xtrackers, Amundi and SPDR holdings files, on synthetic files in their formats."""

from datetime import date

import pytest
from tests.xlsx_builder import amundi_file, build_xlsx, spdr_file, xtrackers_file

from radiografia.data.sources import labels, xlsx
from radiografia.data.sources.holdings_source import HOLDINGS_COLUMNS, HoldingsFormatError
from radiografia.data.sources.other_issuers import (
    AmundiHoldings,
    SpdrDailyHoldings,
    XtrackersConstituents,
)
from radiografia.input.holdings_file import HoldingsFileError, read_holdings_file


def test_xlsx_reader_reads_inline_and_shared_strings_and_gaps():
    rows = [["a", 1.5, None, "c"], [], ["x"]]
    for shared in (False, True):
        content = build_xlsx(rows, sheet="Hoja", shared=shared)
        assert xlsx.sheet_names(content) == ["Hoja"]
        assert xlsx.read_sheet(content) == [["a", "1.5", "", "c"], [], ["x"]]
    assert xlsx.excel_date("46325") == date(2026, 10, 30)
    with pytest.raises(xlsx.XlsxError):
        xlsx.read_sheet(b"PK\x03\x04 not really a zip")


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Estados Unidos", "United States"),
        ("Japón", "Japan"),
        ("Países Bajos", "Netherlands"),
        ("NEW_ZEALAND", "New Zealand"),
        ("Isole Cayman", "Cayman Islands"),
        ("South Korea", "Korea (South)"),
        ("Russia", "Russian Federation"),
        ("Atlantis", "Atlantis"),  # unknown: kept as published, never guessed
        ("", None),
    ],
)
def test_countries_are_translated_to_the_engine_labels(label, expected):
    assert labels.country(label) == expected


def test_sectors_are_translated_and_unknown_is_missing():
    assert labels.sector("Tecnologías de la Información") == "Information Technology"
    assert labels.sector("Atención sanitaria") == "Health Care"
    assert labels.sector("Communication Services") == "Communication"
    assert labels.sector("desconocido") is None
    assert labels.sector("Unassigned") is None


def test_xtrackers_file():
    parsed = XtrackersConstituents().parse("Constituent_IE00BJ0KDQ92.xlsx", xtrackers_file())
    h = parsed.holdings
    assert list(h.columns) == HOLDINGS_COLUMNS
    assert parsed.issuer == "Xtrackers"
    assert parsed.as_of == date(2026, 10, 31)  # the export date (the file has no other)
    assert parsed.fund_isin == "IE00BJ0KDQ92"
    assert h["asset_class"].tolist() == ["Equity"] * 5 + ["Cash", "Futures"]
    assert (
        h.loc[0, "location"] == "United States" and h.loc[0, "sector"] == "Information Technology"
    )
    assert h.loc[5, "security_isin"] is None or h["security_isin"].isna()[5]  # "_CURRENCYUSD"
    assert h["market_value"].sum() == pytest.approx(1.0)  # the future adds no market value


def test_amundi_file():
    parsed = AmundiHoldings().parse("Cartera del fondo_x.xlsx", amundi_file())
    h = parsed.holdings
    assert parsed.as_of == date(2026, 10, 30)
    assert parsed.fund_isin == "IE000BI8OT95"
    assert h["asset_class"].tolist() == ["Equity"] * 5 + ["Futures"]
    assert h.loc[4, "location"] == "Netherlands"
    assert h.loc[5, "market_value"] == 0 and h.loc[5, "notional_value"] == pytest.approx(0.004)


def test_spdr_file():
    parsed = SpdrDailyHoldings().parse("holdings-daily-emea-en-spyy-gy.xlsx", spdr_file())
    h = parsed.holdings
    assert parsed.as_of == date(2026, 10, 29)
    assert parsed.fund_isin == "IE00B44Z5B48"
    assert h["asset_class"].tolist() == ["Equity", "Equity", "Equity", "Cash", "Futures"]
    assert h.loc[2, "location"] == "Korea (South)" and h.loc[2, "sector"] == "Communication"
    assert h.loc[4, "market_value"] == 0 and h.loc[4, "notional_value"] == 900
    assert h.loc[0, "weight_published"] == pytest.approx(0.40)
    assert h["security_isin"].isna()[3]  # "Unassigned"


def test_each_file_is_recognised_by_its_own_reader_only():
    files = {
        "Xtrackers": ("Constituent_IE00BJ0KDQ92.xlsx", xtrackers_file()),
        "Amundi": ("Cartera del fondo_x.xlsx", amundi_file()),
        "SPDR": ("holdings-daily-emea-en-spyy-gy.xlsx", spdr_file()),
    }
    readers = [XtrackersConstituents(), AmundiHoldings(), SpdrDailyHoldings()]
    for issuer, (name, content) in files.items():
        assert [r.issuer for r in readers if r.recognises(name, content)] == [issuer]
        upload = read_holdings_file(name, content)
        assert upload.ok and upload.issuer == issuer
        assert upload.equity_share > 0.9


def test_spreadsheet_of_unknown_issuer_and_missing_dates():
    unknown = build_xlsx([["Some", "Other", "Table"], ["a", "b", "c"]])
    assert read_holdings_file("x.xlsx", unknown).error is HoldingsFileError.SPREADSHEET
    no_date = build_xlsx([["Fund Name:", "X"], ["ISIN", "SEDOL", "Security Name", "Currency",
                          "Percent of Fund", "Base Market Value"], ["US0000000AA1", "1", "A",
                          "USD", 100.0, 1.0]])  # fmt: skip
    upload = read_holdings_file("x.xlsx", no_date)
    assert upload.error is HoldingsFileError.BROKEN and upload.issuer == "SPDR"
    with pytest.raises(HoldingsFormatError):
        XtrackersConstituents().parse(
            "x.xlsx", build_xlsx([["", "Name", "ISIN", "Country", "Currency",
                                   "Type of Security", "Weighting"]], sheet="Hoja1")
        )  # fmt: skip
