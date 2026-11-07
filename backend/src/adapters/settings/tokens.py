from pydantic import Field

from adapters.settings import BaseAppSettings


class JwtTokenSettings(BaseAppSettings):
    JWT_ALGORITHM: str
    ACCESS_KEY_TIMEDELTA_MINUTES: int = Field(gt=0)
    REFRESH_KEY_TIMEDELTA_MINUTES: int = Field(gt=0)
    SECRET_KEY_ACCESS: str
    SECRET_KEY_REFRESH: str
