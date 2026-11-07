from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from adapters.settings import JwtTokenSettings, get_settings
from domain.exceptions import InvalidTokenError, TokenExpiredError
from ports.security import JwtProviderInterface


class JwtProvider(JwtProviderInterface):
    def __init__(self, settings: JwtTokenSettings | None = None) -> None:
        self._settings = settings

    @property
    def settings(self) -> JwtTokenSettings:
        return self._settings or get_settings().JWT_TOKEN_SETTINGS

    def _create_token(
        self, data: dict, secret_key: str, expires_delta: timedelta, token_type: str
    ) -> str:
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + expires_delta
        to_encode.update(
            {
                "iat": now,
                "exp": expire,
                "type": token_type,
                "jti": uuid4().hex,
            }
        )
        return jwt.encode(to_encode, secret_key, algorithm=self.settings.JWT_ALGORITHM)

    def create_access_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        settings = self.settings
        return self._create_token(
            data,
            settings.SECRET_KEY_ACCESS,
            expires_delta or timedelta(minutes=settings.ACCESS_KEY_TIMEDELTA_MINUTES),
            token_type="access",
        )

    def create_refresh_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        settings = self.settings
        return self._create_token(
            data,
            settings.SECRET_KEY_REFRESH,
            expires_delta or timedelta(minutes=settings.REFRESH_KEY_TIMEDELTA_MINUTES),
            token_type="refresh",
        )

    def decode_access_token(self, token: str) -> dict:
        settings = self.settings
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY_ACCESS,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "iat", "sub", "type", "jti"]},
            )
            if payload.get("type") != "access":
                raise InvalidTokenError
            return payload
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError from e

    def decode_refresh_token(self, token: str) -> dict:
        settings = self.settings
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY_REFRESH,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "iat", "sub", "type", "jti"]},
            )
            if payload.get("type") != "refresh":
                raise InvalidTokenError
            return payload
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError from e
