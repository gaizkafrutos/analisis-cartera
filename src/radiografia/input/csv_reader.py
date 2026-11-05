"""Read a portfolio CSV into raw positions.

Format: a header row plus one row per position, with an identifier column (ISIN or ticker) and an
amount column (current market value in EUR). Accepted header names are listed in
IDENTIFIER_COLUMNS / AMOUNT_COLUMNS (case, accents and punctuation are ignored).

Locale: Excel in Spanish saves CSV with ';' and decimal comma; in English with ',' and decimal
point. The delimiter is detected from the header and fixes the decimal separator:
    ';' -> decimal ','   (1.234,56)
    ',' -> decimal '.'   (1,234.56; amounts with a comma must then be quoted)
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata

from radiografia.domain.portfolio import InputError, InputErrorCode, RawPosition
from radiografia.input.amounts import AmountParseError, AmountProblem, parse_amount

MAX_ROWS = 200

IDENTIFIER_COLUMNS = ("identificador", "isin", "ticker", "identifier", "id")
AMOUNT_COLUMNS = ("importe_eur", "importe", "valor_eur", "valor", "amount_eur", "amount", "value")

_AMOUNT_ERRORS = {
    AmountProblem.EMPTY: InputErrorCode.MISSING_AMOUNT,
    AmountProblem.INVALID: InputErrorCode.INVALID_AMOUNT,
    AmountProblem.AMBIGUOUS: InputErrorCode.AMBIGUOUS_AMOUNT,
    AmountProblem.TOO_MANY_DECIMALS: InputErrorCode.TOO_MANY_DECIMALS,
    AmountProblem.NON_POSITIVE: InputErrorCode.NON_POSITIVE_AMOUNT,
}


def decode_csv_bytes(data: bytes) -> str:
    """UTF-8 (with or without BOM) first; Excel on Windows may also save as cp1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def normalize_header(name: str) -> str:
    """'Importe (€)' -> 'importe', 'Valor EUR' -> 'valor_eur', 'Identificación' -> ..."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")


def detect_delimiter(header_line: str) -> str:
    return ";" if header_line.count(";") >= header_line.count(",") and ";" in header_line else ","


def _find_column(headers: list[str], accepted: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if header in accepted:
            return index
    return None


def read_portfolio_csv(data: bytes | str) -> tuple[list[RawPosition], list[InputError]]:
    """Return the rows that could be read and every problem found (row = line number)."""
    text = decode_csv_bytes(data) if isinstance(data, bytes) else data.removeprefix("﻿")
    lines = text.splitlines()
    first_non_blank = next((line for line in lines if line.strip()), None)
    if first_non_blank is None:
        return [], [InputError(code=InputErrorCode.EMPTY_FILE)]

    delimiter = detect_delimiter(first_non_blank)
    decimal_separator = "," if delimiter == ";" else "."
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    headers: list[str] | None = None
    id_col = amount_col = None
    positions: list[RawPosition] = []
    errors: list[InputError] = []
    data_rows = 0

    for fields in reader:
        if not any(field.strip() for field in fields):
            continue
        line = reader.line_num
        if headers is None:
            headers = [normalize_header(field) for field in fields]
            id_col = _find_column(headers, IDENTIFIER_COLUMNS)
            amount_col = _find_column(headers, AMOUNT_COLUMNS)
            if id_col is None:
                errors.append(InputError(code=InputErrorCode.MISSING_COLUMN, value="identificador"))
            if amount_col is None:
                errors.append(InputError(code=InputErrorCode.MISSING_COLUMN, value="importe_eur"))
            if errors:
                return [], errors
            continue

        assert id_col is not None and amount_col is not None
        data_rows += 1
        if data_rows > MAX_ROWS:
            errors.append(InputError(code=InputErrorCode.TOO_MANY_ROWS, value=str(MAX_ROWS)))
            break

        identifier = fields[id_col].strip() if id_col < len(fields) else ""
        raw_amount = fields[amount_col] if amount_col < len(fields) else ""
        if not identifier:
            errors.append(InputError(code=InputErrorCode.MISSING_IDENTIFIER, row=line))
        try:
            amount = parse_amount(raw_amount, decimal_separator)
        except AmountParseError as exc:
            errors.append(
                InputError(code=_AMOUNT_ERRORS[exc.problem], row=line, value=raw_amount.strip())
            )
            continue
        if identifier:
            positions.append(RawPosition(identifier=identifier, amount_eur=amount, row=line))

    return positions, errors
