from radiografia.domain.portfolio import InputErrorCode
from radiografia.input.csv_reader import (
    MAX_ROWS,
    decode_csv_bytes,
    normalize_header,
    read_portfolio_csv,
)


def _amounts(positions):
    return [(p.identifier, p.amount_eur, p.row) for p in positions]


def test_spanish_excel_csv():
    text = "ISIN;Importe (€)\nIE00B4L5Y983;6.000,50\nIE00BK5BQT80;3000\n"
    positions, errors = read_portfolio_csv(text)
    assert errors == []
    assert _amounts(positions) == [("IE00B4L5Y983", 6000.5, 2), ("IE00BK5BQT80", 3000.0, 3)]


def test_international_csv_with_quoted_thousands():
    text = 'identifier,amount_eur\nIE00B4L5Y983,"6,000.50"\nIE00BK5BQT80,3000\n'
    positions, errors = read_portfolio_csv(text)
    assert errors == []
    assert _amounts(positions) == [("IE00B4L5Y983", 6000.5, 2), ("IE00BK5BQT80", 3000.0, 3)]


def test_utf8_bom_and_cp1252_are_decoded():
    text = "identificador;importe_eur\nIE00B4L5Y983;10\n"
    assert decode_csv_bytes(b"\xef\xbb\xbf" + text.encode()) == text
    assert decode_csv_bytes("Identificación;Importe €".encode("cp1252")) == (
        "Identificación;Importe €"
    )


def test_bytes_input_with_bom():
    data = b"\xef\xbb\xbfidentificador;importe_eur\r\nIE00B4L5Y983;10\r\n"
    positions, errors = read_portfolio_csv(data)
    assert errors == []
    assert _amounts(positions) == [("IE00B4L5Y983", 10.0, 2)]


def test_header_normalization():
    assert normalize_header(" Importe (€) ") == "importe"
    assert normalize_header("Valor EUR") == "valor_eur"
    assert normalize_header("ISIN") == "isin"


def test_blank_lines_are_skipped_and_line_numbers_kept():
    text = "isin;importe\n\nIE00B4L5Y983;10\n;\nIE00BK5BQT80;20\n"
    positions, errors = read_portfolio_csv(text)
    assert errors == []
    assert [p.row for p in positions] == [3, 5]


def test_empty_file():
    _, errors = read_portfolio_csv("  \n\n")
    assert [e.code for e in errors] == [InputErrorCode.EMPTY_FILE]


def test_missing_columns():
    _, errors = read_portfolio_csv("nombre;cantidad\nX;1\n")
    assert [(e.code, e.value) for e in errors] == [
        (InputErrorCode.MISSING_COLUMN, "identificador"),
        (InputErrorCode.MISSING_COLUMN, "importe_eur"),
    ]


def test_row_errors_carry_line_number_and_value():
    text = "isin;importe\nIE00B4L5Y983;1,500\n;100\nIE00BK5BQT80;\nIE00B3RBWM25;-5\n"
    positions, errors = read_portfolio_csv(text)
    assert positions == []
    assert [(e.code, e.row, e.value) for e in errors] == [
        (InputErrorCode.AMBIGUOUS_AMOUNT, 2, "1,500"),
        (InputErrorCode.MISSING_IDENTIFIER, 3, None),
        (InputErrorCode.MISSING_AMOUNT, 4, ""),
        (InputErrorCode.NON_POSITIVE_AMOUNT, 5, "-5"),
    ]


def test_too_many_rows():
    rows = "".join(f"IE00B4L5Y983;{i + 1}\n" for i in range(MAX_ROWS + 5))
    positions, errors = read_portfolio_csv("isin;importe\n" + rows)
    assert len(positions) == MAX_ROWS
    assert [e.code for e in errors] == [InputErrorCode.TOO_MANY_ROWS]
