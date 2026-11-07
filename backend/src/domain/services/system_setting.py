from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from logging import getLogger
from typing import Any, Literal
from uuid import UUID

from domain.entities.system_setting import (
    SystemSetting,
    SystemSettingDefaults,
    SystemSettingView,
)
from domain.exceptions.system_setting import (
    InvalidSystemSettingError,
    UnknownSystemSettingError,
)
from domain.validators import NumberValidator, PaymentAmountValidator, TextValidator
from ports.repositories.system_setting import SystemSettingRepositoryInterface

logger = getLogger(__name__)


@dataclass(frozen=True)
class _Spec:
    kind: Literal["int", "optional_int", "optional_decimal", "currency"]
    default: Any
    description: str


class SystemSettingsService:
    """Global runtime settings with env-derived defaults and admin overrides."""

    def __init__(
        self, settings: SystemSettingRepositoryInterface, defaults: SystemSettingDefaults
    ) -> None:
        self._settings = settings
        self._specs: dict[str, _Spec] = {
            "registration.initial_credits": _Spec(
                "int",
                defaults.initial_credits,
                "Credits granted to a newly registered user",
            ),
            "referral.inviter_credits": _Spec(
                "int",
                defaults.inviter_credits,
                "Credits granted to the inviter after a successful referral",
            ),
            "referral.invitee_credits": _Spec(
                "int",
                defaults.invitee_credits,
                "Credits granted to the invited user",
            ),
            "payments.crypto_price_per_credit": _Spec(
                "optional_decimal",
                defaults.crypto_price_per_credit,
                "Crypto price of one credit; null disables crypto payments",
            ),
            "payments.crypto_currency": _Spec(
                "currency",
                defaults.crypto_currency,
                "Fiat currency used for crypto checkout totals",
            ),
            "payments.stars_price_per_credit": _Spec(
                "optional_int",
                defaults.stars_price_per_credit,
                "Telegram Stars price of one credit; null disables Stars",
            ),
            "payments.crypto_min_amount": _Spec(
                "optional_decimal",
                defaults.crypto_min_amount,
                "Minimum crypto checkout total; null disables the minimum",
            ),
            "payments.stars_min_amount": _Spec(
                "int",
                defaults.stars_min_amount,
                "Minimum Telegram Stars checkout total",
            ),
        }

    def _spec(self, key: str) -> _Spec:
        spec = self._specs.get(key)
        if spec is None:
            raise UnknownSystemSettingError(key)
        return spec

    def _coerce(self, key: str, spec: _Spec, value: object) -> Any:
        try:
            if spec.kind == "int":
                return NumberValidator.validate_integer(
                    value, min_value=0, max_value=2**31 - 1
                )
            if spec.kind == "optional_int":
                return NumberValidator.validate_integer(
                    value, min_value=0, max_value=2**31 - 1, nullable=True
                )
            if spec.kind == "optional_decimal":
                if value is None:
                    return None
                if isinstance(value, bool) or not isinstance(
                    value, (str, int, Decimal)
                ):
                    raise InvalidSystemSettingError(
                        key, "expected a decimal string, integer or null"
                    )
                try:
                    amount = Decimal(str(value))
                except InvalidOperation as exc:
                    raise InvalidSystemSettingError(
                        key, "expected a decimal value"
                    ) from exc
                PaymentAmountValidator.validate(amount)
                return str(amount)
            currency = TextValidator.validate(value, min_length=3, max_length=3).upper()
            if (
                not currency.isascii()
                or not currency.isalpha()
                or not currency.isupper()
            ):
                raise InvalidSystemSettingError(
                    key, "currency must be three uppercase ASCII letters"
                )
            return currency
        except InvalidSystemSettingError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalized into a settings error
            raise InvalidSystemSettingError(key, str(exc)) from exc

    async def _effective(self, key: str) -> Any:
        spec = self._spec(key)
        row = await self._settings.get(key)
        if row is None:
            return spec.default
        try:
            return self._coerce(key, spec, row.value)
        except InvalidSystemSettingError:
            logger.warning(
                "Ignoring invalid stored system setting %s; using the default", key
            )
            return spec.default

    async def get_int(self, key: str) -> int:
        value = await self._effective(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidSystemSettingError(key, "expected an integer")
        return value

    async def get_optional_int(self, key: str) -> int | None:
        value = await self._effective(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidSystemSettingError(key, "expected an integer or null")
        return value

    async def get_decimal(self, key: str) -> Decimal | None:
        value = await self._effective(key)
        if value is None:
            return None
        return Decimal(str(value))

    async def get_str(self, key: str) -> str:
        value = await self._effective(key)
        if not isinstance(value, str):
            raise InvalidSystemSettingError(key, "expected a string")
        return value

    async def get_all(self) -> list[SystemSettingView]:
        rows = {row.key: row for row in await self._settings.list()}
        return [
            self._view(key, spec, rows.get(key)) for key, spec in self._specs.items()
        ]

    async def update(
        self, key: str, value: object, *, admin_id: UUID | None = None
    ) -> SystemSettingView:
        spec = self._spec(key)
        normalized = self._coerce(key, spec, value)
        row = await self._settings.upsert(
            key,
            value=normalized,
            description=spec.description,
            updated_by=admin_id,
        )
        return self._view(key, spec, row)

    async def reset(self, key: str, *, admin_id: UUID | None = None) -> SystemSettingView:
        spec = self._spec(key)
        await self._settings.delete(key)
        return self._view(key, spec, None)

    def _view(
        self, key: str, spec: _Spec, row: SystemSetting | None
    ) -> SystemSettingView:
        return SystemSettingView(
            key=key,
            value=row.value if row is not None else spec.default,
            default=spec.default,
            description=spec.description,
            source="database" if row is not None else "default",
            updated_by=row.updated_by if row is not None else None,
            updated_at=row.updated_at if row is not None else None,
        )
