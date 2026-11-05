"""Spanish texts for portfolio input: field help, errors and "not covered" reasons."""

from __future__ import annotations

from radiografia.domain.portfolio import InputError, InputErrorCode, NotCoveredReason

AMOUNT_FIELD_LABEL = "Valor actual (€)"
AMOUNT_FIELD_HELP = (
    "Lo que vale hoy cada posición en euros, según tu bróker. No es lo que pagaste: "
    "el análisis describe tu cartera actual."
)
IDENTIFIER_FIELD_HELP = (
    "El ISIN del ETF (12 caracteres, p. ej. IE00B4L5Y983). También se acepta el ticker si "
    "identifica un único ETF del universo."
)
CSV_FORMAT_HELP = (
    "Una fila por posición con dos columnas: identificador (ISIN o ticker) e importe_eur. "
    "Se aceptan CSV de Excel en español (separador ';' y coma decimal) o en inglés "
    "(separador ',' y punto decimal)."
)

INPUT_ERROR_MESSAGES: dict[InputErrorCode, str] = {
    InputErrorCode.EMPTY_FILE: "El fichero está vacío.",
    InputErrorCode.MISSING_COLUMN: "Falta la columna «{value}» en la cabecera del CSV.",
    InputErrorCode.TOO_MANY_ROWS: "La cartera tiene más de {value} posiciones; no se procesa.",
    InputErrorCode.EMPTY_PORTFOLIO: "La cartera no tiene ninguna posición.",
    InputErrorCode.MISSING_IDENTIFIER: "Falta el ISIN o ticker.",
    InputErrorCode.INVALID_IDENTIFIER: "«{value}» no parece un ISIN ni un ticker.",
    InputErrorCode.ISIN_WRONG_LENGTH: "«{value}» no tiene 12 caracteres, como todo ISIN.",
    InputErrorCode.ISIN_BAD_COUNTRY_CODE: "«{value}» debe empezar por dos letras (código de país).",
    InputErrorCode.ISIN_BAD_CHARACTERS: "«{value}» contiene caracteres no válidos para un ISIN.",
    InputErrorCode.ISIN_BAD_CHECK_DIGIT: (
        "«{value}» tiene un dígito de control incorrecto: probablemente hay una errata."
    ),
    InputErrorCode.MISSING_AMOUNT: "Falta el importe.",
    InputErrorCode.INVALID_AMOUNT: "«{value}» no es un importe válido.",
    InputErrorCode.AMBIGUOUS_AMOUNT: (
        "«{value}» es ambiguo (¿miles o decimales?). Escríbelo sin separador de miles, "
        "p. ej. 1500 o 1500,00."
    ),
    InputErrorCode.TOO_MANY_DECIMALS: "«{value}» tiene más de 2 decimales.",
    InputErrorCode.NON_POSITIVE_AMOUNT: "El importe debe ser mayor que cero (valor: «{value}»).",
}

NOT_COVERED_MESSAGES: dict[NotCoveredReason, str] = {
    NotCoveredReason.OUTSIDE_UNIVERSE: (
        "ISIN válido, pero este ETF aún no está en el universo analizado."
    ),
    NotCoveredReason.UNKNOWN_TICKER: "Ticker no reconocido. Introduce el ISIN para identificarlo.",
    NotCoveredReason.AMBIGUOUS_TICKER: (
        "Este ticker corresponde a varios productos. Introduce el ISIN para identificarlo."
    ),
}


def format_input_error(error: InputError) -> str:
    message = INPUT_ERROR_MESSAGES[error.code].format(value=error.value or "")
    return f"Fila {error.row}: {message}" if error.row is not None else message
