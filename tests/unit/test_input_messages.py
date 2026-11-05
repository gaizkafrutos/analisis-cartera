from radiografia.domain.portfolio import InputError, InputErrorCode, NotCoveredReason
from radiografia.reporting.input_messages import (
    INPUT_ERROR_MESSAGES,
    NOT_COVERED_MESSAGES,
    format_input_error,
)


def test_every_error_code_has_a_message():
    assert set(INPUT_ERROR_MESSAGES) == set(InputErrorCode)


def test_every_not_covered_reason_has_a_message():
    assert set(NOT_COVERED_MESSAGES) == set(NotCoveredReason)


def test_format_with_row_and_value():
    error = InputError(code=InputErrorCode.ISIN_BAD_CHECK_DIGIT, row=3, value="IE00B4L5Y984")
    assert format_input_error(error) == (
        "Fila 3: «IE00B4L5Y984» tiene un dígito de control incorrecto: "
        "probablemente hay una errata."
    )


def test_messages_contain_no_investment_recommendations():
    texts = [*INPUT_ERROR_MESSAGES.values(), *NOT_COVERED_MESSAGES.values()]
    forbidden = ("deberías", "recomend", "compra", "vende")
    assert not [t for t in texts for word in forbidden if word in t.lower()]
