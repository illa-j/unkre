from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from adapters.settings import BaseAppSettings


class ApiSettings(BaseAppSettings):
    API_WORKERS: int = Field(default=6, ge=1)
    MODES_CACHE_TTL_SECONDS: int = Field(default=300, ge=0)

    COOKIE_DOMAIN: str | None = None
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_SECURE: bool = False
    ADMIN_ACCESS_TOKEN_COOKIE: str = "ad_access_token"
    ADMIN_REFRESH_TOKEN_COOKIE: str = "ad_refresh_token"
    CLIENT_ACCESS_TOKEN_COOKIE: str = "cl_access_token"
    CLIENT_REFRESH_TOKEN_COOKIE: str = "cl_refresh_token"

    # Empty by default: same-origin only. A dev or tunnel origin is set in .env,
    # never hard-coded here (a personal tunnel domain was the old default).
    CORS_ALLOWED_ORIGINS: str = ""

    CSRF_ENABLED: bool = True
    CSRF_COOKIE_NAME: str = "csrf_token"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    CSRF_EXEMPT_PATHS: str = ""

    # Shared per-IP budget across all API processes (Redis), including the
    # requests issued together by page navigation and background polling.
    SECURITY_RATE_LIMIT: int = Field(default=1200, ge=1)
    SECURITY_RATE_LIMIT_WINDOW: int = Field(default=60, ge=1)
    SECURITY_ROUTE_RATE_LIMIT_ENABLED: bool = True
    SECURITY_AUTO_BAN_THRESHOLD: int = Field(default=10, ge=1)
    SECURITY_AUTO_BAN_DURATION: int = Field(default=3600, ge=1)
    SECURITY_ENFORCE_HTTPS: bool = False
    SECURITY_BLOCKED_USER_AGENTS: str = ""
    SECURITY_TRUSTED_PROXIES: str = ""
    SECURITY_PASSIVE_MODE: bool = False
    SECURITY_REDIS_ENABLED: bool = True
    SECURITY_REDIS_PREFIX: str = Field(default="unkre:guard:", min_length=1)

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = []
        for origin in value.split(","):
            origin = origin.strip().rstrip("/")
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins")
            origins.append(origin)
        return ",".join(dict.fromkeys(origins))
