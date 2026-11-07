import asyncio
import hmac
import time

import httpx
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKSetError

from domain.entities.auth import AuthProvider, SocialIdentity
from domain.exceptions.auth import (
    AuthProviderNotConfiguredError,
    AuthProviderUnavailableError,
    InvalidCredentialsError,
)
from domain.validators import NumberValidator, TextValidator


class _ProviderJWKClient(PyJWKClient):
    def fetch_data(self) -> dict:
        # Telegram may return gzip even when identity encoding is requested.
        # HTTPX decodes Content-Encoding; urllib's json.load(response) does not.
        try:
            response = httpx.get(
                self.uri, headers=self.headers, timeout=self.timeout, follow_redirects=False
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PyJWKClientConnectionError("Cannot load provider keys") from exc
        if not isinstance(payload, dict):
            raise PyJWKSetError("Provider keys must be a JSON object")
        # Preserve PyJWKClient's cache and key-rotation cooldown bookkeeping.
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(payload)
        self._last_successful_fetch = time.monotonic()
        return payload


class OAuthService:
    _ISSUERS = {
        AuthProvider.GOOGLE: ("https://accounts.google.com", "accounts.google.com"),
        AuthProvider.TELEGRAM: ("https://oauth.telegram.org",),
    }
    _JWKS_URLS = {
        AuthProvider.GOOGLE: "https://www.googleapis.com/oauth2/v3/certs",
        AuthProvider.TELEGRAM: "https://oauth.telegram.org/.well-known/jwks.json",
    }

    def __init__(
        self, *, google_client_id: str = "", telegram_client_id: str = ""
    ) -> None:
        self._client_ids = {
            AuthProvider.GOOGLE: google_client_id.strip(),
            AuthProvider.TELEGRAM: telegram_client_id.strip(),
        }
        self._keys = {
            provider: _ProviderJWKClient(
                url,
                cache_jwk_set=True,
                lifespan=300,
                timeout=5,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            )
            for provider, url in self._JWKS_URLS.items()
        }

    def client_id(self, provider: AuthProvider) -> str:
        provider = AuthProvider(provider)
        client_id = self._client_ids[provider]
        if not client_id:
            raise AuthProviderNotConfiguredError(f"{provider} is not configured")
        return client_id

    async def verify_google(self, id_token: str, nonce: str) -> SocialIdentity:
        return await self.verify(AuthProvider.GOOGLE, id_token, nonce)

    async def verify_telegram(self, id_token: str, nonce: str) -> SocialIdentity:
        return await self.verify(AuthProvider.TELEGRAM, id_token, nonce)

    async def verify(
        self, provider: AuthProvider, id_token: str, nonce: str
    ) -> SocialIdentity:
        provider = AuthProvider(provider)
        client_id = self.client_id(provider)
        try:
            TextValidator.validate(id_token, max_length=16384)
            TextValidator.validate(nonce, min_length=32, max_length=256)
            return await asyncio.to_thread(
                self._verify, provider, id_token, nonce, client_id
            )
        except (PyJWKClientConnectionError, PyJWKSetError) as exc:
            raise AuthProviderUnavailableError("Cannot load provider keys") from exc
        except InvalidCredentialsError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
            raise InvalidCredentialsError("Invalid provider credentials") from exc

    def _verify(
        self, provider: AuthProvider, id_token: str, nonce: str, client_id: str
    ) -> SocialIdentity:
        header = jwt.get_unverified_header(id_token)
        if header.get("alg") != "RS256":
            raise InvalidCredentialsError("Unsupported signing algorithm")
        TextValidator.validate(header.get("kid"), max_length=255)

        key = self._keys[provider].get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=self._ISSUERS[provider],
            options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]},
        )
        for name in ("iat", "exp"):
            if type(claims[name]) not in (int, float):
                raise InvalidCredentialsError("Invalid token timestamp")
        if claims["exp"] <= claims["iat"]:
            raise InvalidCredentialsError("Invalid token lifetime")
        token_nonce = TextValidator.validate(claims["nonce"], max_length=256)
        if not hmac.compare_digest(token_nonce.encode(), nonce.encode()):
            raise InvalidCredentialsError("Nonce mismatch")
        audience = claims["aud"]
        authorized_party = claims.get("azp")
        if (authorized_party is not None and authorized_party != client_id) or (
            isinstance(audience, list)
            and len(audience) > 1
            and authorized_party != client_id
        ):
            raise InvalidCredentialsError("Invalid authorized party")

        if provider == AuthProvider.GOOGLE and claims.get("email_verified") is not True:
            raise InvalidCredentialsError("Google email is not verified")
        return SocialIdentity(
            provider=provider,
            subject=claims["sub"],
            first_name=claims.get("given_name", claims.get("name", "User")),
            last_name=self._optional_profile_text(claims.get("family_name")),
            email=claims.get("email") if provider == AuthProvider.GOOGLE else None,
            # Telegram sub не є Telegram user ID. id приходить зі scope profile.
            telegram_id=(
                self._telegram_user_id(claims.get("id"))
                if provider == AuthProvider.TELEGRAM
                else None
            ),
            username=(
                self._optional_profile_text(claims.get("preferred_username"))
                if provider == AuthProvider.TELEGRAM
                else None
            ),
            photo_url=self._optional_profile_text(claims.get("picture")),
            language_code=self._optional_profile_text(claims.get("language_code")),
        )

    @staticmethod
    def _optional_profile_text(value: object) -> str | None:
        text = TextValidator.validate(value, min_length=0, strip=True, nullable=True)
        return text or None

    @staticmethod
    def _telegram_user_id(value: object) -> int:
        original_type = type(value).__name__
        if (
            isinstance(value, str)
            and 1 <= len(value) <= 19
            and value.isascii()
            and value.isdecimal()
            and not value.startswith("0")
        ):
            value = int(value)
        try:
            return NumberValidator.validate_integer(value, min_value=1, max_value=2**63 - 1)
        except ValueError as exc:
            raise InvalidCredentialsError(
                f"Invalid Telegram profile ID ({original_type})"
            ) from exc
