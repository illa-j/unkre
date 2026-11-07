from functools import lru_cache

from pydantic import Field

from adapters.settings import (
    AdminSettings,
    ApiSettings,
    BaseAppSettings,
    BotSettings,
    DatabaseSettings,
    JwtTokenSettings,
    PaymentSettings,
    RunPodSettings,
    StorageSettings,
    TaskQueueSettings,
)
from adapters.settings.auth import AuthSettings


class Settings(BaseAppSettings):
    ADMIN_SETTINGS: AdminSettings = Field(default_factory=AdminSettings)
    BOT_SETTINGS: BotSettings = Field(default_factory=BotSettings)
    DATABASE_SETTINGS: DatabaseSettings = Field(default_factory=DatabaseSettings)
    API_SETTINGS: ApiSettings = Field(default_factory=ApiSettings)
    JWT_TOKEN_SETTINGS: JwtTokenSettings = Field(default_factory=JwtTokenSettings)
    AUTH_SETTINGS: AuthSettings = Field(default_factory=AuthSettings)
    RUNPOD_SETTINGS: RunPodSettings = Field(default_factory=RunPodSettings)
    TASK_QUEUE_SETTINGS: TaskQueueSettings = Field(default_factory=TaskQueueSettings)
    PAYMENT_SETTINGS: PaymentSettings = Field(default_factory=PaymentSettings)
    STORAGE_SETTINGS: StorageSettings = Field(default_factory=StorageSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings


def __getattr__(name: str) -> Settings:
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
