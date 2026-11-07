from pydantic import Field, field_validator

from adapters.settings.base import BaseAppSettings


class BotSettings(BaseAppSettings):
    """Telegram bot for the MiniApp entry point."""

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_MINIAPP_URL: str = ""
    TELEGRAM_BOT_POLLING_TIMEOUT: int = Field(default=10, ge=1, le=60)
    TELEGRAM_WEBAPP_AUTH_TTL_SECONDS: int = Field(default=3600, ge=60, le=86400)

    @field_validator("TELEGRAM_MINIAPP_URL", mode="before")
    @classmethod
    def validate_miniapp_url(cls, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.startswith("https://"):
            return raw
        if raw.startswith("http://localhost") or raw.startswith("http://127.0.0.1"):
            return raw
        raise ValueError(
            "TELEGRAM_MINIAPP_URL must be an https:// URL (Telegram requirement)"
        )

    @property
    def authenticated(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN.strip())

    @property
    def ready(self) -> bool:
        return self.authenticated and bool(self.TELEGRAM_MINIAPP_URL)
