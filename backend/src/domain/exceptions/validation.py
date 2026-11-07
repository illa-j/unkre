class ValidationError(ValueError):
    pass


class InvalidValidationRuleError(ValidationError):
    def __init__(self, parameter: str, requirement: str) -> None:
        self.parameter = parameter
        super().__init__(f"Invalid '{parameter}': {requirement}.")


class TextValidationError(ValidationError):
    pass


class InvalidTextTypeError(TextValidationError):
    def __init__(self) -> None:
        super().__init__("Value must be a string.")


class TextTooShortError(TextValidationError):
    def __init__(self, min_length: int, actual_length: int) -> None:
        self.min_length = min_length
        self.actual_length = actual_length
        super().__init__(
            f"Text length must be at least {min_length}; got {actual_length}."
        )


class TextTooLongError(TextValidationError):
    def __init__(self, max_length: int, actual_length: int) -> None:
        self.max_length = max_length
        self.actual_length = actual_length
        super().__init__(
            f"Text length must be at most {max_length}; got {actual_length}."
        )


class NumberValidationError(ValidationError):
    pass


class InvalidNumberTypeError(NumberValidationError):
    def __init__(self) -> None:
        super().__init__("Value must be an int or float; booleans are not allowed.")


class NonFiniteNumberError(NumberValidationError):
    def __init__(self) -> None:
        super().__init__("Value must be finite; NaN and infinity are not allowed.")


class InvalidIntegerTypeError(NumberValidationError):
    def __init__(self) -> None:
        super().__init__("Value must be an integer; booleans are not allowed.")


class NumberTooSmallError(NumberValidationError):
    def __init__(self, min_value: int | float) -> None:
        self.min_value = min_value
        super().__init__(f"Value must be greater than or equal to {min_value}.")


class NumberTooLargeError(NumberValidationError):
    def __init__(self, max_value: int | float) -> None:
        self.max_value = max_value
        super().__init__(f"Value must be less than or equal to {max_value}.")
