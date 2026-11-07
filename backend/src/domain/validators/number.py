from math import isfinite
from typing import Literal, overload

from domain.exceptions import (
    InvalidIntegerTypeError,
    InvalidNumberTypeError,
    InvalidValidationRuleError,
    NonFiniteNumberError,
    NumberTooLargeError,
    NumberTooSmallError,
)


class NumberValidator:
    @staticmethod
    @overload
    def validate_integer(
        value: object,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        nullable: Literal[False] = False,
    ) -> int: ...

    @staticmethod
    @overload
    def validate_integer(
        value: object,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        nullable: bool,
    ) -> int | None: ...

    @staticmethod
    def validate_integer(
        value: object,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        nullable: bool = False,
    ) -> int | None:
        result = NumberValidator.validate(
            value, min_value=min_value, max_value=max_value, nullable=nullable
        )
        if result is not None and not isinstance(result, int):
            raise InvalidIntegerTypeError()
        return result

    @staticmethod
    @overload
    def validate(
        value: object,
        *,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        nullable: Literal[False] = False,
    ) -> int | float: ...

    @staticmethod
    @overload
    def validate(
        value: object,
        *,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        nullable: bool,
    ) -> int | float | None: ...

    @staticmethod
    def validate(
        value: object,
        *,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        nullable: bool = False,
    ) -> int | float | None:
        for name, bound in (("min_value", min_value), ("max_value", max_value)):
            if bound is None:
                continue
            if isinstance(bound, bool) or not isinstance(bound, (int, float)):
                raise InvalidValidationRuleError(name, "must be an int or float")
            if isinstance(bound, float) and not isfinite(bound):
                raise InvalidValidationRuleError(name, "must be finite")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise InvalidValidationRuleError(
                "min_value", "must be less than or equal to max_value"
            )
        if not isinstance(nullable, bool):
            raise InvalidValidationRuleError("nullable", "must be a boolean")

        if value is None and nullable:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidNumberTypeError()
        if isinstance(value, float) and not isfinite(value):
            raise NonFiniteNumberError()
        if min_value is not None and value < min_value:
            raise NumberTooSmallError(min_value)
        if max_value is not None and value > max_value:
            raise NumberTooLargeError(max_value)
        return value
