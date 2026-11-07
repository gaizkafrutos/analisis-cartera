"""Reading the holdings files users upload: what is accepted, and a clear error for the rest."""

from datetime import date
from pathlib import Path

import pytest

from radiografia.domain.universe import UniverseIndex
from radiografia.input.holdings_file import (
    MAX_FILE_BYTES,
    HoldingsFileError,
    read_holdings_file,
)
from radiografia.reporting.input_messages import HOLDINGS_FILE_MESSAGES, format_holdings_file_error

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "SWDA_holdings.csv"
CONTENT = FIXTURE.read_bytes()
INDEX = UniverseIndex(
    isins=frozenset({"IE00B4L5Y983", "IE00B5BMR087", "IE00BKM4GZ66"}),
    tickers={
        "SWDA": frozenset({"IE00B4L5Y983"}),
        "CSPX": frozenset({"IE00B5BMR087"}),
        "XYZ": frozenset({"IE00B5BMR087", "IE00BKM4GZ66"}),  # ambiguous: never guessed
    },
)


def test_ishares_csv_is_read_like_a_snapshot():
    upload = read_holdings_file("SWDA_holdings.csv", CONTENT, INDEX)
    assert upload.ok and upload.issuer == "iShares"
    assert upload.as_of == date(2026, 10, 30)
    assert len(upload.holdings) == 7  # trailing note and blank lines ignored
    # 9,500 of 10,000 in equity lines (cash 500, the future has no market value)
    assert upload.equity_share == pytest.approx(0.95)
    assert upload.holdings["weight_published"].sum() == pytest.approx(1.0)
    # missing text is missing (NaN), as when a stored snapshot is read back; '-' is kept as is
    assert upload.holdings.loc[6, "location"] == "-"
    assert upload.suggested_isin == "IE00B4L5Y983"


@pytest.mark.parametrize(
    ("filename", "suggested"),
    [
        ("SWDA_holdings (1).csv", "IE00B4L5Y983"),
        ("cspx_holdings.csv", "IE00B5BMR087"),
        ("XYZ_holdings.csv", None),  # the ticker could be two funds
        ("posiciones.csv", None),
        ("SWDA_holdings.csv", "IE00B4L5Y983"),
    ],
)
def test_fund_is_suggested_from_the_file_name(filename, suggested):
    assert read_holdings_file(filename, CONTENT, INDEX).suggested_isin == suggested


def test_without_universe_nothing_is_suggested():
    assert read_holdings_file("SWDA_holdings.csv", CONTENT).suggested_isin is None


def test_byte_order_mark_and_windows_encoding_are_accepted():
    assert read_holdings_file("a.csv", b"\xef\xbb\xbf" + CONTENT).ok
    latin = CONTENT.replace(b"ALFA SYNTHETIC CORP", "ALFA SÍNTESIS".encode("cp1252"))
    upload = read_holdings_file("a.csv", latin)
    assert upload.ok and "ALFA S" in upload.holdings.loc[0, "name"]


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (b"", HoldingsFileError.EMPTY),
        (b"   \n", HoldingsFileError.EMPTY),
        (
            b'<?xml version="1.0"?><ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:'
            b'spreadsheet">',
            HoldingsFileError.ISHARES_WORKBOOK,
        ),
        (b"PK\x03\x04 rest of a zip file", HoldingsFileError.SPREADSHEET),
        (b"identificador;importe_eur\nIE00B4L5Y983;1000\n", HoldingsFileError.NOT_RECOGNISED),
        (b'Fund Holdings as of,"30/Oct/2026"\n\nName,Weight\n', HoldingsFileError.BROKEN),
        (b'Fund Holdings as of,"not a date"\n', HoldingsFileError.BROKEN),
    ],
)
def test_unusable_files_get_a_clear_error(content, error):
    upload = read_holdings_file("x.csv", content)
    assert upload.error is error and not upload.ok
    assert upload.holdings is None
    assert format_holdings_file_error(upload.error, upload.detail)  # a message for every case


def test_file_without_market_value_is_rejected():
    zeroed = b"\n".join(
        line if not line.startswith(b'"') else line.replace(b'"4,000.00"', b'"0.00"')
        for line in CONTENT.splitlines()
    )
    zeroed = zeroed.replace(b'"2,000.00"', b'"0.00"').replace(b'"1,500.00"', b'"0.00"')
    zeroed = zeroed.replace(b'"1,000.00"', b'"0.00"').replace(b'"500.00"', b'"0.00"')
    assert read_holdings_file("x.csv", zeroed).error is HoldingsFileError.NO_POSITIONS


def test_too_large_file_is_not_parsed():
    upload = read_holdings_file("x.csv", CONTENT + b" " * MAX_FILE_BYTES)
    assert upload.error is HoldingsFileError.TOO_LARGE


def test_every_error_has_a_spanish_message():
    assert set(HOLDINGS_FILE_MESSAGES) == set(HoldingsFileError)
