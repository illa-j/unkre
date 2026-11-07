import pytest

from domain.exceptions import (
    InvalidIntegerTypeError,
    InvalidNumberTypeError,
    InvalidTextTypeError,
    InvalidValidationRuleError,
    NonFiniteNumberError,
    NumberTooLargeError,
    NumberTooSmallError,
    NumberValidationError,
    TextTooLongError,
    TextTooShortError,
    TextValidationError,
    ValidationError,
)
from domain.validators import NumberValidator, TextValidator


@pytest.mark.parametrize("value", [0, 1, 2**63 - 1])
def test_integer_validation(value):
    assert NumberValidator.validate_integer(value, min_value=0) == value


@pytest.mark.parametrize("value", [0.0, 1.5])
def test_integer_validation_rejects_floats(value):
    with pytest.raises(InvalidIntegerTypeError):
        NumberValidator.validate_integer(value)


def test_integer_nullable_validation():
    assert NumberValidator.validate_integer(None, nullable=True) is None
    with pytest.raises(InvalidNumberTypeError):
        NumberValidator.validate_integer(True)
    with pytest.raises(InvalidNumberTypeError):
        NumberValidator.validate_integer(None)


def test_text_bounds_and_unicode():
    assert TextValidator.validate("їж", min_length=2, max_length=3) == "їж"
    assert TextValidator.validate("їжа", min_length=2, max_length=3) == "їжа"
    for value in ("ї", "їжак"):
        with pytest.raises(TextValidationError):
            TextValidator.validate(value, min_length=2, max_length=3)


def test_text_normalization_is_optional_and_precedes_validation():
    assert TextValidator.validate("  текст  ") == "  текст  "
    assert TextValidator.validate("  текст  ", strip=True) == "текст"
    assert TextValidator.validate("", min_length=0, max_length=0) == ""
    with pytest.raises(TextValidationError):
        TextValidator.validate(" \n\t ", strip=True)


@pytest.mark.parametrize("value", [None, 1, True, b"text", [], ""])
def test_invalid_text(value):
    with pytest.raises(TextValidationError):
        TextValidator.validate(value)


@pytest.mark.parametrize(
    "options",
    [
        {"min_length": -1},
        {"min_length": True},
        {"min_length": None},
        {"max_length": 1.5},
        {"min_length": 3, "max_length": 2},
        {"strip": "yes"},
    ],
)
def test_invalid_text_rules(options):
    with pytest.raises(InvalidValidationRuleError):
        TextValidator.validate("текст", **options)


@pytest.mark.parametrize("value", [-2, 0, 1.5, 3])
def test_number_inclusive_bounds_preserve_type(value):
    result = NumberValidator.validate(value, min_value=-2, max_value=3)
    assert result == value
    assert type(result) is type(value)


def test_large_integer_does_not_require_float_conversion():
    value = 10**1000
    assert NumberValidator.validate(value) == value


@pytest.mark.parametrize(
    "value", [None, "1", True, False, float("nan"), float("inf"), -float("inf")]
)
def test_invalid_number(value):
    with pytest.raises(NumberValidationError):
        NumberValidator.validate(value)


@pytest.mark.parametrize("value", [-1, 2])
def test_number_outside_bounds(value):
    with pytest.raises(NumberValidationError):
        NumberValidator.validate(value, min_value=0, max_value=1)


@pytest.mark.parametrize(
    "options",
    [
        {"min_value": True},
        {"min_value": "0"},
        {"min_value": float("nan")},
        {"max_value": float("inf")},
        {"min_value": 2, "max_value": 1},
    ],
)
def test_invalid_number_rules(options):
    with pytest.raises(InvalidValidationRuleError):
        NumberValidator.validate(0, **options)


def test_validation_errors_share_domain_base():
    assert issubclass(TextValidationError, ValidationError)
    assert issubclass(NumberValidationError, ValidationError)


@pytest.mark.parametrize(
    ("validator", "error"),
    [(TextValidator, InvalidTextTypeError), (NumberValidator, InvalidNumberTypeError)],
)
def test_nullable_allows_only_explicit_null(validator, error):
    assert validator.validate(None, nullable=True) is None
    with pytest.raises(error):
        validator.validate(None)
    with pytest.raises(error):
        validator.validate(None, nullable=False)
    with pytest.raises(error):
        validator.validate([], nullable=True)


def test_nullable_preserves_validation_for_present_values():
    assert TextValidator.validate("text", nullable=True) == "text"
    assert NumberValidator.validate(0, nullable=True) == 0
    with pytest.raises(TextTooShortError):
        TextValidator.validate("", nullable=True)
    with pytest.raises(NumberTooSmallError):
        NumberValidator.validate(-1, min_value=0, nullable=True)


@pytest.mark.parametrize("validator", [TextValidator, NumberValidator])
@pytest.mark.parametrize("nullable", [None, 0, 1, "true"])
def test_nullable_requires_boolean(validator, nullable):
    with pytest.raises(InvalidValidationRuleError, match="'nullable'"):
        validator.validate(None, nullable=nullable)


@pytest.mark.parametrize(
    ("validator", "options"),
    [(TextValidator, {"min_length": -1}), (NumberValidator, {"min_value": True})],
)
def test_nullable_does_not_bypass_invalid_rules(validator, options):
    with pytest.raises(InvalidValidationRuleError):
        validator.validate(None, nullable=True, **options)


@pytest.mark.parametrize(
    ("validator", "value", "options", "error", "message"),
    [
        (TextValidator, 1, {}, InvalidTextTypeError, "Value must be a string."),
        (
            TextValidator,
            "",
            {},
            TextTooShortError,
            "Text length must be at least 1; got 0.",
        ),
        (
            TextValidator,
            "abc",
            {"max_length": 2},
            TextTooLongError,
            "Text length must be at most 2; got 3.",
        ),
        (
            NumberValidator,
            True,
            {},
            InvalidNumberTypeError,
            "Value must be an int or float; booleans are not allowed.",
        ),
        (
            NumberValidator,
            float("nan"),
            {},
            NonFiniteNumberError,
            "Value must be finite; NaN and infinity are not allowed.",
        ),
        (
            NumberValidator,
            -1,
            {"min_value": 0},
            NumberTooSmallError,
            "Value must be greater than or equal to 0.",
        ),
        (
            NumberValidator,
            2,
            {"max_value": 1},
            NumberTooLargeError,
            "Value must be less than or equal to 1.",
        ),
        (
            NumberValidator,
            0,
            {"min_value": True},
            InvalidValidationRuleError,
            "Invalid 'min_value': must be an int or float.",
        ),
    ],
)
def test_specific_errors_and_english_messages(
    validator, value, options, error, message
):
    with pytest.raises(error) as caught:
        validator.validate(value, **options)
    assert str(caught.value) == message
