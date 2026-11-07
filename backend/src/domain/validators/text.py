from typing import Literal, overload

from domain.exceptions import (
    InvalidTextTypeError,
    InvalidValidationRuleError,
    TextTooLongError,
    TextTooShortError,
)


class TextValidator:
    @staticmethod
    @overload
    def validate(
        value: object,
        *,
        min_length: int = 1,
        max_length: int | None = None,
        strip: bool = False,
        nullable: Literal[False] = False,
    ) -> str: ...

    @staticmethod
    @overload
    def validate(
        value: object,
        *,
        min_length: int = 1,
        max_length: int | None = None,
        strip: bool = False,
        nullable: bool,
    ) -> str | None: ...

    @staticmethod
    def validate(
        value: object,
        *,
        min_length: int = 1,
        max_length: int | None = None,
        strip: bool = False,
        nullable: bool = False,
    ) -> str | None:
        for name, bound in (("min_length", min_length), ("max_length", max_length)):
            if name == "max_length" and bound is None:
                continue
            if isinstance(bound, bool) or not isinstance(bound, int) or bound < 0:
                raise InvalidValidationRuleError(name, "must be a non-negative integer")
        if max_length is not None and min_length > max_length:
            raise InvalidValidationRuleError(
                "min_length", "must be less than or equal to max_length"
            )
        if not isinstance(strip, bool):
            raise InvalidValidationRuleError("strip", "must be a boolean")
        if not isinstance(nullable, bool):
            raise InvalidValidationRuleError("nullable", "must be a boolean")

        if value is None and nullable:
            return None
        if not isinstance(value, str):
            raise InvalidTextTypeError()
        if strip:
            value = value.strip()
        length = len(value)
        if length < min_length:
            raise TextTooShortError(min_length, length)
        if max_length is not None and length > max_length:
            raise TextTooLongError(max_length, length)
        return value
