"""Shared factory for the global runtime settings service."""

from adapters.database.repositiries import SystemSettingRepository
from adapters.settings import Settings
from domain.entities.system_setting import SystemSettingDefaults
from domain.services.system_setting import SystemSettingsService
from ports import DatabaseManagerInterface


def build_system_settings(
    manager: DatabaseManagerInterface, settings: Settings
) -> SystemSettingsService:
    auth = settings.AUTH_SETTINGS
    payment = settings.PAYMENT_SETTINGS
    return SystemSettingsService(
        SystemSettingRepository(manager),
        SystemSettingDefaults(
            initial_credits=auth.USER_INITIAL_CREDITS,
            inviter_credits=auth.REFERRAL_INVITER_CREDITS,
            invitee_credits=auth.REFERRAL_INVITEE_CREDITS,
            crypto_price_per_credit=str(payment.CRYPTO_PRICE_PER_CREDIT)
            if payment.CRYPTO_PRICE_PER_CREDIT is not None
            else None,
            crypto_currency=payment.CRYPTO_CURRENCY,
            stars_price_per_credit=payment.STARS_PRICE_PER_CREDIT,
            crypto_min_amount=str(payment.CRYPTO_MIN_AMOUNT),
            stars_min_amount=payment.STARS_MIN_AMOUNT,
        ),
    )
