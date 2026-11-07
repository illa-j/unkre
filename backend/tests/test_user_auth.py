import asyncio
import gzip
import json
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import func, select, update

from adapters.api.dependencies.settings import get_app_settings
from adapters.api.dependencies.user import get_oauth_service
from adapters.api.guard import configure_guard
from adapters.api.main import app
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.user import router
from adapters.database import DatabaseManager, DatabaseSession, db_session
from adapters.database.models import (
    Base,
    UserAuthChallengeModel,
    UserModel,
    UserRefreshTokenModel,
    WalletModel,
)
from adapters.database.repositiries import (
    ReferralRepository,
    TransactionRepository,
    WalletRepository,
)
from adapters.security.tokens import JwtProvider
from adapters.settings import AuthSettings, DatabaseSettings, JwtTokenSettings, Settings
from domain.entities.auth import AuthProvider
from domain.exceptions.auth import AuthenticationConflictError
from domain.security import TokenManager
from domain.services.oauth import OAuthService
from domain.services.referral import ReferralService


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
async def auth(tmp_path, signing_key, monkeypatch):
    settings = Settings(
        DATABASE_SETTINGS=DatabaseSettings(
            POSTGRES_HOST="localhost",
            POSTGRES_DB_PORT=5432,
            POSTGRES_USER="test",
            POSTGRES_PASSWORD="test",
            POSTGRES_DB="test",
        ),
        JWT_TOKEN_SETTINGS=JwtTokenSettings(
            JWT_ALGORITHM="HS256",
            ACCESS_KEY_TIMEDELTA_MINUTES=15,
            REFRESH_KEY_TIMEDELTA_MINUTES=43200,
            SECRET_KEY_ACCESS="test-access-" + "a" * 32,
            SECRET_KEY_REFRESH="test-refresh-" + "b" * 32,
        ),
        AUTH_SETTINGS=AuthSettings(
            GOOGLE_CLIENT_ID="test.apps.googleusercontent.com",
            TELEGRAM_CLIENT_ID="123456789",
            USER_INITIAL_CREDITS=15,
            REFERRAL_INVITER_CREDITS=5,
            REFERRAL_INVITEE_CREDITS=5,
        ),
    )
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(db_session, "_async_session", database.session_factory)
    oauth = OAuthService(
        google_client_id=settings.AUTH_SETTINGS.GOOGLE_CLIENT_ID,
        telegram_client_id=settings.AUTH_SETTINGS.TELEGRAM_CLIENT_ID,
    )
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid="provider-key", use="sig", alg="RS256")
    for client in oauth._keys.values():
        client.fetch_data = Mock(return_value={"keys": [jwk]})
    test_app = FastAPI()
    test_app.middleware("http")(authentication_middleware)
    test_app.include_router(router)
    test_app.dependency_overrides[get_app_settings] = lambda: settings
    test_app.dependency_overrides[get_oauth_service] = lambda: oauth
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app), base_url="https://api.example"
        ) as client:
            yield SimpleNamespace(
                client=client,
                database=database,
                oauth=oauth,
                signing_key=signing_key,
                settings=settings,
                app=test_app,
                tokens=JwtProvider(settings.JWT_TOKEN_SETTINGS),
            )
    finally:
        await database.dispose()


def provider_token(auth, provider, nonce, *, changes=None, remove=()):
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": "https://accounts.google.com"
        if provider == "google"
        else "https://oauth.telegram.org",
        "aud": auth.oauth.client_id(AuthProvider(provider)),
        "sub": f"{provider}-subject",
        "exp": now + 3600,
        "iat": now,
        "nonce": nonce,
        "given_name": "Ілля",
        "family_name": "Тест",
        "picture": "https://example.com/avatar.jpg",
    }
    if provider == "google":
        claims.update(email="user@example.com", email_verified=True)
    else:
        claims.update(id=987654321, preferred_username="test_user")
    claims.update(changes or {})
    for field in remove:
        claims.pop(field, None)
    return jwt.encode(
        claims, auth.signing_key, algorithm="RS256", headers={"kid": "provider-key"}
    )


async def challenge(auth, provider="google"):
    response = await auth.client.post(
        "/users/auth/challenge", json={"provider": provider}
    )
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()["nonce"]


async def login(auth, provider="google", *, changes=None, referral_code=None):
    nonce = await challenge(auth, provider)
    body = {
        "nonce": nonce,
        "id_token": provider_token(auth, provider, nonce, changes=changes),
    }
    if referral_code is not None:
        body["referral_code"] = referral_code
    return await auth.client.post(f"/users/auth/{provider}", json=body)


async def link_account(auth, provider, *, changes=None):
    nonce = await challenge(auth, provider)
    return await auth.client.post(
        f"/users/links/{provider}",
        json={
            "nonce": nonce,
            "id_token": provider_token(auth, provider, nonce, changes=changes),
        },
    )


def session_data(auth, response):
    assert response.status_code == 200, response.text
    result = response.json()
    assert "access_token" not in result and "refresh_token" not in result
    api = auth.settings.API_SETTINGS
    return {
        **result,
        "access_token": response.cookies[api.CLIENT_ACCESS_TOKEN_COOKIE],
        "refresh_token": response.cookies[api.CLIENT_REFRESH_TOKEN_COOKIE],
    }


def cookie_headers(auth, *, access=None, refresh=None):
    api = auth.settings.API_SETTINGS
    parts = []
    if access is not None:
        parts.append(f"{api.CLIENT_ACCESS_TOKEN_COOKIE}={access}")
    if refresh is not None:
        parts.append(f"{api.CLIENT_REFRESH_TOKEN_COOKIE}={refresh}")
    return {"Cookie": "; ".join(parts)}


def test_user_router_registered_in_main():
    expected = {
        "/users/auth/challenge",
        "/users/auth/google",
        "/users/auth/telegram",
        "/users/auth/refresh",
        "/users/auth/logout",
        "/users/session",
        "/users/me",
    }
    assert expected <= app.openapi()["paths"].keys()


async def test_authentication_middleware_registered_in_main():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        response = await client.get("/users/me")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


async def test_session_probe_is_anonymous_friendly(auth):
    response = await auth.client.get("/users/session")
    assert response.status_code == 200
    assert response.json() is None

    result = session_data(auth, await login(auth, "google"))
    response = await auth.client.get("/users/session")
    assert response.status_code == 200
    assert response.json()["id"] == result["user"]["id"]


@pytest.mark.parametrize("provider", ["google", "telegram"])
async def test_guard_preserves_social_login_refresh_and_logout(auth, provider):
    auth.settings.API_SETTINGS.SECURITY_REDIS_ENABLED = False
    configure_guard(auth.app, auth.settings)
    denied = await auth.client.post(
        "/users/auth/challenge", json={"provider": provider}
    )
    assert denied.status_code == 403
    bootstrap = await auth.client.get("/users/me")
    assert bootstrap.status_code == 401
    auth.client.headers["X-CSRF-Token"] = bootstrap.headers["X-CSRF-Token"]
    result = session_data(auth, await login(auth, provider))
    assert (await auth.client.get("/users/me")).json()["id"] == result["user"]["id"]
    refreshed = session_data(auth, await auth.client.post("/users/auth/refresh"))
    assert refreshed["refresh_token"] != result["refresh_token"]
    assert (await auth.client.post("/users/auth/logout")).status_code == 204
    assert (await auth.client.get("/users/me")).status_code == 401


@pytest.mark.parametrize("provider", ["google", "telegram"])
async def test_login_registers_wallet_and_sets_cookie_session(auth, provider):
    response = await login(auth, provider)
    result = session_data(auth, response)
    user = result["user"]
    assert user["first_name"] == "Ілля" and user["credits"] == 15
    assert len(user["referral_code"]) == 24
    assert "google_sub" not in user and "is_blocked" not in user
    assert result["is_new_user"] is True and result["expires_in"] == 900
    assert response.headers["Cache-Control"] == "no-store"
    assert user["telegram_id"] == (987654321 if provider == "telegram" else None)
    assert user["google_email"] == (
        "user@example.com" if provider == "google" else None
    )
    cookies = SimpleCookie()
    for value in response.headers.get_list("set-cookie"):
        cookies.load(value)
    api = auth.settings.API_SETTINGS
    assert cookies[api.CLIENT_ACCESS_TOKEN_COOKIE]["max-age"] == "900"
    assert cookies[api.CLIENT_REFRESH_TOKEN_COOKIE]["max-age"] == str(43200 * 60)
    for cookie in cookies.values():
        assert cookie["httponly"] and cookie["path"] == "/"
        assert cookie["samesite"] == api.COOKIE_SAMESITE
    async with auth.database.session() as session:
        stored = await session.scalar(select(UserRefreshTokenModel))
        assert stored._hashed_token == TokenManager.hash_token(result["refresh_token"])
        assert await session.scalar(select(func.count()).select_from(WalletModel)) == 1
    me = await auth.client.get("/users/me")
    assert me.status_code == 200 and me.json()["id"] == user["id"]
    assert "google_sub" not in me.json()


@pytest.mark.parametrize("provider", ["google", "telegram"])
@pytest.mark.parametrize("empty", ["", "   "])
async def test_empty_optional_provider_profile_fields_are_absent(auth, provider, empty):
    response = await login(
        auth,
        provider,
        changes={
            "family_name": empty,
            "preferred_username": empty,
            "picture": empty,
            "language_code": empty,
        },
    )
    result = session_data(auth, response)
    assert result["user"]["first_name"] == "Ілля"
    for field in ("last_name", "username", "photo_url", "language_code"):
        assert result["user"][field] is None
    me = await auth.client.get("/users/me")
    assert me.status_code == 200


async def test_telegram_jwks_accepts_gzip_and_caches_keys(auth, monkeypatch):
    # Exercise the real PyJWKClient fetch path, rather than its fixture mock.
    auth.oauth._keys[AuthProvider.TELEGRAM] = OAuthService()._keys[AuthProvider.TELEGRAM]
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(auth.signing_key.public_key()))
    jwk.update(kid="provider-key", use="sig", alg="RS256")
    payload = json.dumps({"keys": [jwk]}).encode()
    requests = []

    def serve_jwks(request):
        requests.append(request)
        # Telegram can return gzip even if identity encoding is requested.
        return httpx.Response(
            200, headers={"Content-Encoding": "gzip"}, content=gzip.compress(payload)
        )

    def fetch_jwks(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(serve_jwks)) as client:
            return client.get(url, **kwargs)

    monkeypatch.setattr("domain.services.oauth.httpx.get", fetch_jwks)
    result = session_data(auth, await login(auth, "telegram"))
    assert result["user"]["telegram_id"] == 987654321
    session_data(auth, await login(auth, "telegram"))
    assert len(requests) == 1
    assert requests[0].headers["Accept"] == "application/json"
    assert str(requests[0].url) == OAuthService._JWKS_URLS[AuthProvider.TELEGRAM]


async def test_telegram_numeric_string_profile_id_is_normalized(auth):
    result = session_data(auth, await login(auth, "telegram", changes={"id": "987654321"}))
    assert result["user"]["telegram_id"] == 987654321
    assert (await auth.client.get("/users/me")).status_code == 200


@pytest.mark.parametrize("invalid_keys", [b"not-json", gzip.compress(b"{}")])
async def test_unreadable_provider_keys_return_503(auth, monkeypatch, invalid_keys):
    auth.oauth._keys[AuthProvider.TELEGRAM] = OAuthService()._keys[AuthProvider.TELEGRAM]
    monkeypatch.setattr(
        "domain.services.oauth.httpx.get",
        Mock(return_value=httpx.Response(
            200, content=invalid_keys, request=httpx.Request("GET", "https://provider.example")
        )),
    )
    response = await login(auth, "telegram")
    assert response.status_code == 503
    assert not response.headers.get_list("set-cookie")


@pytest.mark.parametrize("provider", ["google", "telegram"])
async def test_returning_login_updates_profile_without_recrediting(auth, provider):
    first = session_data(auth, await login(auth, provider))
    async with auth.database.session() as session:
        await session.execute(
            update(WalletModel)
            .where(WalletModel.user_id == UUID(first["user"]["id"]))
            .values(credits=3)
        )
        await session.commit()
    result = session_data(
        auth, await login(auth, provider, changes={"given_name": "Нове ім’я"})
    )
    assert result["user"]["id"] == first["user"]["id"]
    assert result["user"]["first_name"] == "Нове ім’я"
    assert result["user"]["credits"] == 3 and result["is_new_user"] is False
    async with auth.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(UserModel)) == 1
        assert await session.scalar(select(func.count()).select_from(WalletModel)) == 1


async def test_google_and_telegram_can_be_linked_both_ways(auth):
    google = session_data(auth, await login(auth, "google"))
    linked = await link_account(auth, "telegram")
    assert linked.status_code == 200, linked.text
    assert linked.json()["telegram_id"] == 987654321
    assert linked.json()["google_email"] == "user@example.com"

    auth.client.cookies.clear()
    telegram = session_data(auth, await login(auth, "telegram"))
    assert telegram["user"]["id"] == google["user"]["id"]
    assert telegram["user"]["google_email"] == "user@example.com"

    auth.client.cookies.clear()
    again = session_data(auth, await login(auth, "google"))
    assert again["user"]["id"] == google["user"]["id"]
    assert again["user"]["telegram_id"] == 987654321


async def test_telegram_account_can_link_google(auth):
    telegram = session_data(auth, await login(auth, "telegram"))
    linked = await link_account(auth, "google")
    assert linked.status_code == 200, linked.text
    assert linked.json()["google_email"] == "user@example.com"
    assert linked.json()["telegram_id"] == 987654321

    auth.client.cookies.clear()
    google = session_data(auth, await login(auth, "google"))
    assert google["user"]["id"] == telegram["user"]["id"]


async def test_identity_cannot_be_linked_to_two_users(auth):
    await login(auth, "google")
    assert (await link_account(auth, "telegram")).status_code == 200
    auth.client.cookies.clear()
    await login(
        auth,
        "google",
        changes={"sub": "google-two", "email": "two@example.com"},
    )
    conflict = await link_account(auth, "telegram")
    assert conflict.status_code == 409


async def test_linking_requires_a_session(auth):
    nonce = await challenge(auth, "telegram")
    response = await auth.client.post(
        "/users/links/telegram",
        json={
            "nonce": nonce,
            "id_token": provider_token(auth, "telegram", nonce),
        },
    )
    assert response.status_code == 401


async def test_referral_code_credits_both_accounts_only_on_signup(auth):
    first = session_data(auth, await login(auth))
    code = first["user"]["referral_code"]
    second = session_data(
        auth,
        await login(
            auth,
            changes={"sub": "referred-subject"},
            referral_code=code.upper(),
        ),
    )
    assert second["is_new_user"] is True
    assert second["user"]["credits"] == 15
    async with db_session.session_scope() as session:
        service = ReferralService(
            ReferralRepository(DatabaseManager(session)),
            WalletRepository(DatabaseManager(session)),
            TransactionRepository(DatabaseManager(session)),
            inviter_credits=5,
            invitee_credits=5,
        )
        assert await service.reward_for_purchase(UUID(second["user"]["id"])) is True
    async with auth.database.session() as session:
        balances = dict(
            (
                await session.execute(
                    select(WalletModel.user_id, WalletModel.credits)
                )
            ).all()
        )
        assert balances[UUID(first["user"]["id"])] == 20
        assert balances[UUID(second["user"]["id"])] == 20
    again = session_data(
        auth,
        await login(auth, changes={"sub": "referred-subject"}, referral_code=code),
    )
    assert again["is_new_user"] is False and again["user"]["credits"] == 20
    ignored = session_data(
        auth,
        await login(
            auth,
            changes={"sub": "unknown-code-subject"},
            referral_code="0" * 24,
        ),
    )
    assert ignored["user"]["credits"] == 15


async def test_subject_is_account_key_and_is_not_normalized(auth):
    first = session_data(auth, await login(auth))
    second = session_data(auth, await login(auth, changes={"sub": "another-account"}))
    third = session_data(auth, await login(auth, "telegram"))
    fourth = session_data(auth, await login(auth, changes={"sub": " google-subject "}))
    assert len({item["user"]["id"] for item in (first, second, third, fourth)}) == 4


async def test_nonce_is_hashed_and_single_use(auth):
    nonce = await challenge(auth)
    async with auth.database.session() as session:
        stored = await session.scalar(select(UserAuthChallengeModel))
        assert stored.nonce_hash == TokenManager.hash_token(nonce)
    body = {"nonce": nonce, "id_token": provider_token(auth, "google", nonce)}
    assert (await auth.client.post("/users/auth/google", json=body)).status_code == 200
    rejected = await auth.client.post("/users/auth/google", json=body)
    assert rejected.status_code == 401 and not rejected.headers.get_list("set-cookie")


@pytest.mark.parametrize("kind", ["expired", "unknown", "wrong_provider", "mismatch"])
async def test_invalid_nonce_is_rejected_without_registration(auth, kind):
    nonce = await challenge(auth, "telegram" if kind == "wrong_provider" else "google")
    if kind == "expired":
        async with auth.database.session() as session:
            await session.execute(
                update(UserAuthChallengeModel).values(
                    expires_at=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
            await session.commit()
    if kind == "unknown":
        nonce = "x" * 43
    token_nonce = "y" * 43 if kind == "mismatch" else nonce
    response = await auth.client.post(
        "/users/auth/google",
        json={"nonce": nonce, "id_token": provider_token(auth, "google", token_nonce)},
    )
    assert response.status_code == 401
    async with auth.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(UserModel)) == 0


@pytest.mark.parametrize(
    ("provider", "changes", "remove"),
    [
        ("google", {"aud": "attacker-client"}, ()),
        ("telegram", {"aud": "attacker-client"}, ()),
        ("google", {"iss": "https://attacker.example"}, ()),
        ("telegram", {"iss": "https://attacker.example"}, ()),
        ("google", {"exp": 1}, ()),
        ("telegram", {"iat": 9999999999}, ()),
        ("google", {"email_verified": False}, ()),
        ("google", {"email_verified": "true"}, ()),
        ("google", {"sub": ""}, ()),
        ("google", {"given_name": "a" * 256}, ()),
        ("google", {"given_name": "   "}, ()),
        ("google", {"azp": "attacker-client"}, ()),
        ("google", {"aud": ["test.apps.googleusercontent.com", "another"]}, ()),
        ("google", {}, ("sub",)),
        ("google", {}, ("exp",)),
        ("google", {}, ("nonce",)),
        ("google", {}, ("email",)),
        ("telegram", {}, ("id",)),
        ("telegram", {"id": True}, ()),
        ("telegram", {"id": -1}, ()),
        ("telegram", {"id": 2**63}, ()),
        ("telegram", {"id": "not-an-id"}, ()),
        ("telegram", {"id": "0"}, ()),
        ("telegram", {"id": "1e3"}, ()),
        ("telegram", {"id": "9" * 200}, ()),
    ],
)
async def test_invalid_provider_claims_are_rejected(
    auth, provider, changes, remove, caplog
):
    nonce = await challenge(auth, provider)
    response = await auth.client.post(
        f"/users/auth/{provider}",
        json={
            "nonce": nonce,
            "id_token": provider_token(
                auth, provider, nonce, changes=changes, remove=remove
            ),
        },
    )
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert not response.headers.get_list("set-cookie")
    assert f"provider_login_rejected provider={provider}" in caplog.text
    assert nonce not in caplog.text


@pytest.mark.parametrize("kind", ["malformed", "unsigned", "wrong_key", "hmac"])
async def test_forged_provider_token_is_rejected(auth, kind):
    nonce = await challenge(auth)
    claims = jwt.decode(
        provider_token(auth, "google", nonce), options={"verify_signature": False}
    )
    if kind == "malformed":
        token = "invalid.jwt"
    elif kind == "unsigned":
        token = jwt.encode(claims, "", algorithm="none")
    elif kind == "hmac":
        token = jwt.encode(claims, "attacker-secret" * 3, algorithm="HS256")
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            claims, key, algorithm="RS256", headers={"kid": "provider-key"}
        )
    response = await auth.client.post(
        "/users/auth/google", json={"nonce": nonce, "id_token": token}
    )
    assert response.status_code == 401


async def test_google_alternative_issuer_and_missing_name(auth):
    nonce = await challenge(auth)
    token = provider_token(
        auth,
        "google",
        nonce,
        changes={"iss": "accounts.google.com"},
        remove=("given_name", "family_name"),
    )
    response = await auth.client.post(
        "/users/auth/google", json={"nonce": nonce, "id_token": token}
    )
    assert (
        response.status_code == 200 and response.json()["user"]["first_name"] == "User"
    )


async def test_provider_outage_and_missing_configuration_return_503(auth):
    nonce = await challenge(auth)
    auth.oauth._keys[
        AuthProvider.GOOGLE
    ].fetch_data.side_effect = PyJWKClientConnectionError()
    response = await auth.client.post(
        "/users/auth/google",
        json={"nonce": nonce, "id_token": provider_token(auth, "google", nonce)},
    )
    assert response.status_code == 503
    auth.oauth._client_ids[AuthProvider.TELEGRAM] = ""
    response = await auth.client.post(
        "/users/auth/challenge", json={"provider": "telegram"}
    )
    assert response.status_code == 503


async def test_registration_conflict_is_mapped_to_409(auth, monkeypatch):
    nonce = await challenge(auth)
    token = provider_token(auth, "google", nonce)
    monkeypatch.setattr(
        auth.oauth, "verify", AsyncMock(side_effect=AuthenticationConflictError)
    )
    response = await auth.client.post(
        "/users/auth/google", json={"nonce": nonce, "id_token": token}
    )
    assert response.status_code == 409 and not response.headers.get_list("set-cookie")


async def test_refresh_rotates_cookies_and_logout_revokes_session(auth):
    first = session_data(auth, await login(auth))
    response = await auth.client.post("/users/auth/refresh")
    second = session_data(auth, response)
    assert second["refresh_token"] != first["refresh_token"]
    assert second["user"]["id"] == first["user"]["id"] and not second["is_new_user"]
    assert (
        await auth.client.post(
            "/users/auth/refresh",
            headers=cookie_headers(auth, refresh=first["refresh_token"]),
        )
    ).status_code == 401
    response = await auth.client.post("/users/auth/logout")
    assert response.status_code == 204 and response.content == b""
    for value in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie(value)
        assert next(iter(cookie.values()))["max-age"] == "0"
    assert (
        auth.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE not in auth.client.cookies
    )
    assert (
        auth.settings.API_SETTINGS.CLIENT_REFRESH_TOKEN_COOKIE
        not in auth.client.cookies
    )
    assert (await auth.client.get("/users/me")).status_code == 401
    headers = cookie_headers(auth, refresh=second["refresh_token"])
    assert (
        await auth.client.post("/users/auth/logout", headers=headers)
    ).status_code == 204
    assert (
        await auth.client.post("/users/auth/refresh", headers=headers)
    ).status_code == 401


@pytest.mark.parametrize("kind", ["nonce", "refresh"])
async def test_parallel_replay_has_one_winner(auth, kind):
    if kind == "nonce":
        nonce = await challenge(auth)
        path = "/users/auth/google"
        kwargs = {
            "json": {"nonce": nonce, "id_token": provider_token(auth, "google", nonce)}
        }
    else:
        result = session_data(auth, await login(auth))
        path = "/users/auth/refresh"
        kwargs = {"headers": cookie_headers(auth, refresh=result["refresh_token"])}
    responses = await asyncio.gather(
        *(auth.client.post(path, **kwargs) for _ in range(2))
    )
    assert sorted(response.status_code for response in responses) == [200, 401]


async def test_logout_preserves_other_device_session(auth):
    first = session_data(auth, await login(auth))
    second = session_data(auth, await login(auth))
    await auth.client.post(
        "/users/auth/logout",
        headers=cookie_headers(auth, refresh=first["refresh_token"]),
    )
    response = await auth.client.post(
        "/users/auth/refresh",
        headers=cookie_headers(auth, refresh=second["refresh_token"]),
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "kind",
    ["missing", "invalid", "refresh", "admin", "unknown", "expired", "header_only"],
)
async def test_current_user_requires_valid_access_cookie(auth, kind):
    result = session_data(auth, await login(auth))
    payload = {"sub": result["user"]["id"], "scope": "user"}
    token = "bad-token"
    if kind == "refresh":
        token = result["refresh_token"]
    elif kind == "admin":
        token = auth.tokens.create_access_token({**payload, "scope": "admin"})
    elif kind == "unknown":
        token = auth.tokens.create_access_token({**payload, "sub": str(uuid4())})
    elif kind == "expired":
        token = auth.tokens.create_access_token(payload, timedelta(seconds=-1))
    headers = cookie_headers(
        auth, access=None if kind in ("missing", "header_only") else token
    )
    if kind == "header_only":
        headers["Authorization"] = f"Bearer {result['access_token']}"
    response = await auth.client.get("/users/me", headers=headers)
    assert response.status_code == 401 and "WWW-Authenticate" not in response.headers


@pytest.mark.parametrize(
    "kind", ["missing", "access", "unknown", "expired", "admin", "body_only"]
)
async def test_refresh_requires_valid_persisted_refresh_cookie(auth, kind):
    result = session_data(auth, await login(auth))
    payload = {"sub": result["user"]["id"], "scope": "user"}
    if kind == "access":
        token = result["access_token"]
    elif kind == "expired":
        token = auth.tokens.create_refresh_token(payload, timedelta(seconds=-1))
    elif kind == "admin":
        token = auth.tokens.create_refresh_token({**payload, "scope": "admin"})
    else:
        token = auth.tokens.create_refresh_token(payload)
    response = await auth.client.post(
        "/users/auth/refresh",
        headers=cookie_headers(
            auth, refresh=None if kind in ("missing", "body_only") else token
        ),
        json={"refresh_token": result["refresh_token"]}
        if kind == "body_only"
        else None,
    )
    assert response.status_code == 401


async def test_blocked_user_cannot_login_read_profile_or_refresh(auth):
    await login(auth)
    async with auth.database.session() as session:
        await session.execute(update(UserModel).values(is_blocked=True))
        await session.commit()
    assert (await login(auth)).status_code == 403
    assert (await auth.client.get("/users/me")).status_code == 403
    assert (await auth.client.post("/users/auth/refresh")).status_code == 403


async def test_cookie_configuration_is_used_for_set_read_and_delete(auth):
    api = auth.settings.API_SETTINGS
    api.CLIENT_ACCESS_TOKEN_COOKIE = "custom_access"
    api.CLIENT_REFRESH_TOKEN_COOKIE = "custom_refresh"
    api.COOKIE_DOMAIN = "api.example"
    api.COOKIE_SECURE = True
    api.COOKIE_SAMESITE = "strict"
    response = await login(auth)
    assert response.status_code == 200
    for value in response.headers.get_list("set-cookie"):
        cookie = next(iter(SimpleCookie(value).values()))
        assert cookie["domain"] == "api.example" and cookie["secure"]
        assert cookie["samesite"] == "strict" and cookie["httponly"]
    assert (await auth.client.get("/users/me")).status_code == 200
    response = await auth.client.post("/users/auth/logout")
    assert response.status_code == 204
    for value in response.headers.get_list("set-cookie"):
        cookie = next(iter(SimpleCookie(value).values()))
        assert cookie["domain"] == "api.example" and cookie["path"] == "/"
        assert cookie["max-age"] == "0" and cookie["secure"]
    assert (await auth.client.get("/users/me")).status_code == 401


@pytest.mark.parametrize(
    "path,body",
    [
        ("/users/auth/challenge", {"provider": "invalid"}),
        ("/users/auth/google", {"id_token": "x", "nonce": "short"}),
        ("/users/auth/telegram", {"id_token": 123, "nonce": "x" * 43}),
    ],
)
async def test_invalid_request_returns_422(auth, path, body):
    response = await auth.client.post(path, json=body)
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert not response.headers.get_list("set-cookie")


async def test_commit_failure_does_not_send_session_cookies(auth, monkeypatch):
    nonce = await challenge(auth)
    token = provider_token(auth, "google", nonce)
    original_factory = db_session._async_session
    session = original_factory()
    monkeypatch.setattr(
        session, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))
    )
    monkeypatch.setattr(db_session, "_async_session", lambda: session)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=auth.app, raise_app_exceptions=False),
        base_url="https://api.example",
    ) as client:
        response = await client.post(
            "/users/auth/google", json={"nonce": nonce, "id_token": token}
        )
    assert response.status_code == 500 and not response.headers.get_list("set-cookie")
    async with auth.database.session() as stored:
        assert await stored.scalar(select(func.count()).select_from(UserModel)) == 0


def test_openapi_does_not_expose_token_response_fields_or_refresh_body():
    schema = app.openapi()
    fields = schema["components"]["schemas"]["UserSessionResponse"]["properties"]
    assert "access_token" not in fields and "refresh_token" not in fields
    assert "requestBody" not in schema["paths"]["/users/auth/refresh"]["post"]
