from decimal import Decimal
from typing import Literal, overload

from domain.exceptions import InvalidPaymentAmountError, InvalidValidationRuleError


class PaymentAmountValidator:
    @staticmethod
    @overload
    def validate(
        value: object, *, allow_zero: bool = False, nullable: Literal[False] = False
    ) -> Decimal: ...

    @staticmethod
    @overload
    def validate(
        value: object, *, allow_zero: bool = False, nullable: bool
    ) -> Decimal | None: ...

    @staticmethod
    def validate(
        value: object, *, allow_zero: bool = False, nullable: bool = False
    ) -> Decimal | None:
        if not isinstance(allow_zero, bool):
            raise InvalidValidationRuleError("allow_zero", "must be a boolean")
        if not isinstance(nullable, bool):
            raise InvalidValidationRuleError("nullable", "must be a boolean")
        if value is None and nullable:
            return None
        if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
            raise InvalidPaymentAmountError(
                "use Decimal or int; floats are not allowed"
            )
        amount = Decimal(value)
        if not amount.is_finite():
            raise InvalidPaymentAmountError("amount must be finite")
        if amount < 0 or (amount == 0 and not allow_zero):
            raise InvalidPaymentAmountError(
                "amount must be non-negative"
                if allow_zero
                else "amount must be positive"
            )
        if amount > Decimal("99999999999999999999.999999999999999999"):
            raise InvalidPaymentAmountError("amount exceeds NUMERIC(38, 18)")
        digits = list(amount.as_tuple().digits)
        exponent = amount.as_tuple().exponent
        assert isinstance(exponent, int)
        while digits and digits[-1] == 0:
            digits.pop()
            exponent += 1
        if digits and exponent < -18:
            raise InvalidPaymentAmountError(
                "amount cannot have more than 18 decimal places"
            )
        return amount
