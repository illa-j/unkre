import asyncio
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from sqlalchemy import func, select, update

from adapters.api.dependencies.settings import get_app_settings
from adapters.api.guard import configure_guard
from adapters.api.main import app
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.admin import router as admin_router
from adapters.api.routes.user import router as user_router
from adapters.database import DatabaseSession, db_session
from adapters.database.models import AdminModel, AdminRefreshTokenModel, Base
from adapters.security.password_hasher import Argon2PasswordHasher
from adapters.security.tokens import JwtProvider
from adapters.settings import DatabaseSettings, JwtTokenSettings, Settings
from domain.security import TokenManager

PASSWORD = " admin password with spaces "


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash_password(PASSWORD)


@pytest.fixture
async def admin_auth(tmp_path, monkeypatch, password_hash):
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
            ACCESS_KEY_TIMEDELTA_MINUTES=2,
            REFRESH_KEY_TIMEDELTA_MINUTES=120,
            SECRET_KEY_ACCESS="admin-access-" + "a" * 32,
            SECRET_KEY_REFRESH="admin-refresh-" + "b" * 32,
        ),
    )
    database = DatabaseSession(f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.session() as session:
        admin = AdminModel(
            username="owner", _hashed_password=password_hash, is_owner=True
        )
        session.add(admin)
        await session.commit()
        admin_id = admin.id
    monkeypatch.setattr(db_session, "_async_session", database.session_factory)
    test_app = FastAPI()
    test_app.middleware("http")(authentication_middleware)
    test_app.include_router(admin_router)
    test_app.include_router(user_router)
    test_app.dependency_overrides[get_app_settings] = lambda: settings
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=test_app), base_url="https://api.example"
        ) as client:
            yield SimpleNamespace(
                client=client,
                app=test_app,
                database=database,
                settings=settings,
                admin_id=admin_id,
                tokens=JwtProvider(settings.JWT_TOKEN_SETTINGS),
            )
    finally:
        await database.dispose()


async def login(auth, **changes):
    return await auth.client.post(
        "/admins/auth/login",
        json={"username": "owner", "password": PASSWORD, **changes},
    )


def session_data(auth, response):
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"admin", "expires_in"}
    assert set(data["admin"]) == {"id", "username", "is_owner"}
    api = auth.settings.API_SETTINGS
    return {
        **data,
        "access_token": response.cookies[api.ADMIN_ACCESS_TOKEN_COOKIE],
        "refresh_token": response.cookies[api.ADMIN_REFRESH_TOKEN_COOKIE],
    }


def cookie_headers(
    auth, *, access=None, refresh=None, client_access=None, client_refresh=None
):
    api = auth.settings.API_SETTINGS
    values = (
        (api.ADMIN_ACCESS_TOKEN_COOKIE, access),
        (api.ADMIN_REFRESH_TOKEN_COOKIE, refresh),
        (api.CLIENT_ACCESS_TOKEN_COOKIE, client_access),
        (api.CLIENT_REFRESH_TOKEN_COOKIE, client_refresh),
    )
    return {
        "Cookie": "; ".join(
            f"{key}={value}" for key, value in values if value is not None
        )
    }


def test_admin_routes_registered_in_main():
    paths = app.openapi()["paths"]
    assert {
        "/admins/auth/login",
        "/admins/auth/refresh",
        "/admins/auth/logout",
        "/admins/me",
    } <= paths.keys()
    assert "/admins/auth/register" not in paths


async def test_main_admin_middleware_requires_cookie():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        response = await client.get("/admins/me")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


async def test_guard_preserves_admin_login_refresh_and_logout(admin_auth):
    auth = admin_auth
    auth.settings.API_SETTINGS.SECURITY_REDIS_ENABLED = False
    configure_guard(auth.app, auth.settings)
    assert (await login(auth)).status_code == 403
    bootstrap = await auth.client.get("/admins/me")
    assert bootstrap.status_code == 401
    auth.client.headers["X-CSRF-Token"] = bootstrap.headers["X-CSRF-Token"]
    result = session_data(auth, await login(auth))
    assert (await auth.client.get("/admins/me")).json()["id"] == result["admin"]["id"]
    refreshed = session_data(auth, await auth.client.post("/admins/auth/refresh"))
    assert refreshed["refresh_token"] != result["refresh_token"]
    assert (await auth.client.post("/admins/auth/logout")).status_code == 204
    assert (await auth.client.get("/admins/me")).status_code == 401


async def test_login_sets_hashed_session_and_admin_cookies(admin_auth):
    auth = admin_auth
    response = await login(auth)
    data = session_data(auth, response)
    assert data["admin"] == {
        "id": str(auth.admin_id),
        "username": "owner",
        "is_owner": True,
    }
    assert data["expires_in"] == 120
    assert response.headers["Cache-Control"] == "no-store"
    claims = auth.tokens.decode_access_token(data["access_token"])
    refresh = auth.tokens.decode_refresh_token(data["refresh_token"])
    assert claims["scope"] == refresh["scope"] == "admin"
    assert claims["exp"] - claims["iat"] == 120
    assert refresh["exp"] - refresh["iat"] == 7200
    assert "is_owner" not in claims
    cookies = SimpleCookie()
    for value in response.headers.get_list("set-cookie"):
        cookies.load(value)
    api = auth.settings.API_SETTINGS
    assert set(cookies) == {
        api.ADMIN_ACCESS_TOKEN_COOKIE,
        api.ADMIN_REFRESH_TOKEN_COOKIE,
    }
    assert cookies[api.ADMIN_ACCESS_TOKEN_COOKIE]["max-age"] == "120"
    assert cookies[api.ADMIN_REFRESH_TOKEN_COOKIE]["max-age"] == "7200"
    for cookie in cookies.values():
        assert cookie["httponly"] and cookie["path"] == "/"
        assert cookie["samesite"] == api.COOKIE_SAMESITE
    async with auth.database.session() as session:
        stored = await session.scalar(select(AdminRefreshTokenModel))
        assert stored.admin_id == auth.admin_id
        assert stored._hashed_token == TokenManager.hash_token(data["refresh_token"])
        assert stored._hashed_token != data["refresh_token"]
    me = await auth.client.get("/admins/me")
    assert me.status_code == 200 and me.json() == data["admin"]
    assert me.headers["Cache-Control"] == "no-store"


async def test_username_is_trimmed_but_password_is_preserved(admin_auth):
    assert (await login(admin_auth, username=" owner ")).status_code == 200
    assert (await login(admin_auth, password=PASSWORD.strip())).status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"username": "missing"},
        {"username": "OWNER"},
        {"password": "wrong-password"},
        {"username": "owner' OR 1=1 --"},
    ],
)
async def test_wrong_credentials_do_not_create_session(admin_auth, changes):
    response = await login(admin_auth, **changes)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired credentials"}
    assert not response.headers.get_list("set-cookie")
    assert response.headers["Cache-Control"] == "no-store"
    async with admin_auth.database.session() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(AdminRefreshTokenModel)
            )
            == 0
        )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"username": "x", "password": PASSWORD},
        {"username": "owner", "password": ""},
        {"username": 123, "password": PASSWORD},
        {"username": "owner", "password": 123},
        {"username": "owner", "password": "x" * 1025},
        {"username": "x" * 101, "password": PASSWORD},
        {"username": "owner", "password": PASSWORD, "is_owner": True},
    ],
)
async def test_login_validation(admin_auth, body):
    response = await admin_auth.client.post("/admins/auth/login", json=body)
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert not response.headers.get_list("set-cookie")


async def test_refresh_rotates_and_logout_clears_only_admin_cookies(admin_auth):
    auth = admin_auth
    first = session_data(auth, await login(auth))
    api = auth.settings.API_SETTINGS
    auth.client.cookies.set(
        api.CLIENT_ACCESS_TOKEN_COOKIE, "client-access", domain="api.example", path="/"
    )
    auth.client.cookies.set(
        api.CLIENT_REFRESH_TOKEN_COOKIE,
        "client-refresh",
        domain="api.example",
        path="/",
    )
    second = session_data(auth, await auth.client.post("/admins/auth/refresh"))
    assert second["refresh_token"] != first["refresh_token"]
    assert second["admin"]["id"] == first["admin"]["id"]
    assert (
        await auth.client.post(
            "/admins/auth/refresh",
            headers=cookie_headers(auth, refresh=first["refresh_token"]),
        )
    ).status_code == 401
    response = await auth.client.post("/admins/auth/logout")
    assert response.status_code == 204 and response.content == b""
    for value in response.headers.get_list("set-cookie"):
        cookie = next(iter(SimpleCookie(value).values()))
        assert cookie["max-age"] == "0"
        assert cookie.key in (
            api.ADMIN_ACCESS_TOKEN_COOKIE,
            api.ADMIN_REFRESH_TOKEN_COOKIE,
        )
    assert api.ADMIN_ACCESS_TOKEN_COOKIE not in auth.client.cookies
    assert api.ADMIN_REFRESH_TOKEN_COOKIE not in auth.client.cookies
    assert auth.client.cookies[api.CLIENT_ACCESS_TOKEN_COOKIE] == "client-access"
    assert auth.client.cookies[api.CLIENT_REFRESH_TOKEN_COOKIE] == "client-refresh"
    headers = cookie_headers(auth, refresh=second["refresh_token"])
    assert (
        await auth.client.post("/admins/auth/logout", headers=headers)
    ).status_code == 204
    assert (
        await auth.client.post("/admins/auth/refresh", headers=headers)
    ).status_code == 401


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "malformed",
        "expired",
        "refresh",
        "user_scope",
        "unknown",
        "bad_subject",
        "header_only",
        "user_cookie",
    ],
)
async def test_current_admin_rejects_invalid_credentials(admin_auth, kind):
    auth = admin_auth
    claims = {"sub": str(auth.admin_id), "scope": "admin"}
    headers = cookie_headers(auth)
    if kind == "malformed":
        headers = cookie_headers(auth, access="bad-token")
    elif kind == "expired":
        headers = cookie_headers(
            auth, access=auth.tokens.create_access_token(claims, timedelta(seconds=-1))
        )
    elif kind == "refresh":
        headers = cookie_headers(auth, access=auth.tokens.create_refresh_token(claims))
    elif kind == "user_scope":
        headers = cookie_headers(
            auth, access=auth.tokens.create_access_token({**claims, "scope": "user"})
        )
    elif kind == "unknown":
        headers = cookie_headers(
            auth,
            access=auth.tokens.create_access_token({**claims, "sub": str(uuid4())}),
        )
    elif kind == "bad_subject":
        headers = cookie_headers(
            auth, access=auth.tokens.create_access_token({**claims, "sub": "bad-id"})
        )
    elif kind == "header_only":
        headers["Authorization"] = f"Bearer {auth.tokens.create_access_token(claims)}"
    elif kind == "user_cookie":
        headers = cookie_headers(
            auth, client_access=auth.tokens.create_access_token(claims)
        )
    response = await auth.client.get("/admins/me", headers=headers)
    assert response.status_code == 401
    assert "WWW-Authenticate" not in response.headers


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "invalid",
        "access",
        "expired",
        "user_scope",
        "unstored",
        "user_cookie",
        "body_only",
    ],
)
async def test_refresh_requires_persisted_admin_refresh_cookie(admin_auth, kind):
    auth = admin_auth
    result = session_data(auth, await login(auth))
    claims = {"sub": str(auth.admin_id), "scope": "admin"}
    token = auth.tokens.create_refresh_token(claims)
    headers = cookie_headers(auth, refresh=token)
    body = None
    if kind == "missing":
        headers = cookie_headers(auth)
    elif kind == "invalid":
        headers = cookie_headers(auth, refresh="broken")
    elif kind == "access":
        headers = cookie_headers(auth, refresh=result["access_token"])
    elif kind == "expired":
        headers = cookie_headers(
            auth,
            refresh=auth.tokens.create_refresh_token(claims, timedelta(seconds=-1)),
        )
    elif kind == "user_scope":
        headers = cookie_headers(
            auth, refresh=auth.tokens.create_refresh_token({**claims, "scope": "user"})
        )
    elif kind == "user_cookie":
        headers = cookie_headers(auth, client_refresh=result["refresh_token"])
    elif kind == "body_only":
        headers = cookie_headers(auth)
        body = {"refresh_token": result["refresh_token"]}
    response = await auth.client.post(
        "/admins/auth/refresh", headers=headers, json=body
    )
    assert response.status_code == 401 and not response.headers.get_list("set-cookie")


async def test_admin_tokens_do_not_authorize_user_routes(admin_auth):
    auth = admin_auth
    data = session_data(auth, await login(auth))
    response = await auth.client.get(
        "/users/me", headers=cookie_headers(auth, client_access=data["access_token"])
    )
    assert response.status_code == 401
    response = await auth.client.post(
        "/users/auth/refresh",
        headers=cookie_headers(auth, client_refresh=data["refresh_token"]),
    )
    assert response.status_code == 401
    assert (await auth.client.get("/admins/me")).status_code == 200


async def test_parallel_refresh_has_one_winner(admin_auth):
    auth = admin_auth
    data = session_data(auth, await login(auth))
    headers = cookie_headers(auth, refresh=data["refresh_token"])
    responses = await asyncio.gather(
        *(auth.client.post("/admins/auth/refresh", headers=headers) for _ in range(2))
    )
    assert sorted(response.status_code for response in responses) == [200, 401]


async def test_logout_preserves_other_device_session(admin_auth):
    auth = admin_auth
    first = session_data(auth, await login(auth))
    second = session_data(auth, await login(auth))
    assert (
        await auth.client.post(
            "/admins/auth/logout",
            headers=cookie_headers(auth, refresh=first["refresh_token"]),
        )
    ).status_code == 204
    assert (
        await auth.client.post(
            "/admins/auth/refresh",
            headers=cookie_headers(auth, refresh=second["refresh_token"]),
        )
    ).status_code == 200


async def test_deleted_admin_cannot_read_profile_or_refresh(admin_auth):
    auth = admin_auth
    await login(auth)
    async with auth.database.session() as session:
        model = await session.get(AdminModel, auth.admin_id)
        await session.delete(model)
        await session.commit()
    assert (await auth.client.get("/admins/me")).status_code == 401
    assert (await auth.client.post("/admins/auth/refresh")).status_code == 401


async def test_admin_profile_and_role_are_loaded_from_database(admin_auth):
    auth = admin_auth
    await login(auth)
    async with auth.database.session() as session:
        await session.execute(
            update(AdminModel)
            .where(AdminModel.id == auth.admin_id)
            .values(is_owner=False, username="renamed")
        )
        await session.commit()
    response = await auth.client.get("/admins/me")
    assert response.status_code == 200
    assert (
        response.json()["is_owner"] is False
        and response.json()["username"] == "renamed"
    )
    response = await auth.client.post("/admins/auth/refresh")
    assert response.status_code == 200 and response.json()["admin"]["is_owner"] is False


async def test_expired_database_refresh_is_rejected(admin_auth):
    auth = admin_auth
    await login(auth)
    async with auth.database.session() as session:
        await session.execute(
            update(AdminRefreshTokenModel).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
        await session.commit()
    assert (await auth.client.post("/admins/auth/refresh")).status_code == 401


@pytest.mark.parametrize("correct_password", [True, False])
async def test_password_hash_is_upgraded_only_after_successful_login(
    admin_auth, correct_password
):
    auth = admin_auth
    old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(
        PASSWORD
    )
    async with auth.database.session() as session:
        await session.execute(
            update(AdminModel)
            .where(AdminModel.id == auth.admin_id)
            .values(_hashed_password=old_hash)
        )
        await session.commit()
    response = await login(
        auth, password=PASSWORD if correct_password else "wrong-password"
    )
    assert response.status_code == (200 if correct_password else 401)
    async with auth.database.session() as session:
        model = await session.get(AdminModel, auth.admin_id)
        if correct_password:
            assert model._hashed_password != old_hash
            assert Argon2PasswordHasher().verify_password(
                PASSWORD, model._hashed_password
            )
            assert not Argon2PasswordHasher().needs_rehash(model._hashed_password)
        else:
            assert model._hashed_password == old_hash


async def test_custom_admin_cookies_are_used_for_set_read_and_delete(admin_auth):
    auth = admin_auth
    api = auth.settings.API_SETTINGS
    api.ADMIN_ACCESS_TOKEN_COOKIE = "custom_admin_access"
    api.ADMIN_REFRESH_TOKEN_COOKIE = "custom_admin_refresh"
    api.COOKIE_DOMAIN = "api.example"
    api.COOKIE_SECURE = True
    api.COOKIE_SAMESITE = "strict"
    response = await login(auth)
    assert response.status_code == 200
    for value in response.headers.get_list("set-cookie"):
        cookie = next(iter(SimpleCookie(value).values()))
        assert cookie.key in (
            api.ADMIN_ACCESS_TOKEN_COOKIE,
            api.ADMIN_REFRESH_TOKEN_COOKIE,
        )
        assert cookie["domain"] == "api.example" and cookie["path"] == "/"
        assert (
            cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "strict"
        )
    assert (await auth.client.get("/admins/me")).status_code == 200
    response = await auth.client.post("/admins/auth/logout")
    assert response.status_code == 204
    for value in response.headers.get_list("set-cookie"):
        cookie = next(iter(SimpleCookie(value).values()))
        assert cookie["domain"] == "api.example" and cookie["max-age"] == "0"
    assert (await auth.client.get("/admins/me")).status_code == 401


async def test_commit_failure_does_not_send_admin_cookies(admin_auth, monkeypatch):
    auth = admin_auth
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
            "/admins/auth/login", json={"username": "owner", "password": PASSWORD}
        )
    assert response.status_code == 500 and not response.headers.get_list("set-cookie")
    async with auth.database.session() as stored:
        assert (
            await stored.scalar(
                select(func.count()).select_from(AdminRefreshTokenModel)
            )
            == 0
        )


def test_admin_openapi_has_no_password_token_response_or_refresh_body():
    schema = app.openapi()
    fields = schema["components"]["schemas"]["AdminResponse"]["properties"]
    assert set(fields) == {"id", "username", "is_owner"}
    session_fields = schema["components"]["schemas"]["AdminSessionResponse"][
        "properties"
    ]
    assert set(session_fields) == {"admin", "expires_in"}
    assert "requestBody" not in schema["paths"]["/admins/auth/refresh"]["post"]
