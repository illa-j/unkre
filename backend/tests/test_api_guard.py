from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, Request
from guard import RateLimitManager, SecurityConfig, SecurityMiddleware
from guard_core.exceptions import GuardRedisError
from guard_core.handlers.ipban_handler import reset_global_state
from pydantic import ValidationError

from adapters.api.guard import configure_guard
from adapters.api.main import app as main_app
from adapters.api.middlewares import authentication_middleware
from adapters.security.tokens import JwtProvider
from adapters.settings import ApiSettings, Settings
from domain.exceptions.auth import InvalidCredentialsError


@pytest.fixture(autouse=True)
async def clear_bans():
    await reset_global_state()
    await RateLimitManager(SecurityConfig(enable_redis=False)).reset()
    yield
    await reset_global_state()
    await RateLimitManager(SecurityConfig(enable_redis=False)).reset()


@pytest.fixture
def make_api():
    def create(*, client_ip="198.51.100.10", base_url="https://api.example", **values):
        config = ApiSettings(
            _env_file=None,
            CORS_ALLOWED_ORIGINS="https://frontend.example",
            SECURITY_REDIS_ENABLED=False,
            **values,
        )
        settings = Settings(API_SETTINGS=config)
        app = FastAPI()
        app.middleware("http")(authentication_middleware)
        configure_guard(app, settings)
        state = SimpleNamespace(calls=0, settings=settings, app=app)

        @app.get("/check")
        async def check():
            state.calls += 1
            return {"ok": True}

        @app.post("/write")
        async def write(data: dict):
            state.calls += 1
            return data

        @app.post("/payments/webhooks/atlos")
        async def webhook(request: Request):
            return {"body": (await request.body()).decode()}

        @app.get("/unauthenticated")
        async def unauthenticated():
            raise InvalidCredentialsError("Missing cookie")

        state.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(client_ip, 12345)),
            base_url=base_url,
        )
        return state

    return create


def test_main_registers_guard():
    assert any(item.cls is SecurityMiddleware for item in main_app.user_middleware)


async def test_safe_request_bootstraps_csrf_and_security_headers(make_api):
    api = make_api(COOKIE_SECURE=True)
    async with api.client as client:
        response = await client.get("/check")
        token = response.headers["X-CSRF-Token"]
        assert response.status_code == 200
        assert client.cookies["csrf_token"] == token
        assert "Secure" in response.headers["set-cookie"]
        assert "HttpOnly" not in response.headers["set-cookie"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in response.headers
        again = await client.get("/check")
        assert again.headers["X-CSRF-Token"] == token
        assert "set-cookie" not in again.headers


async def test_unauthenticated_request_can_bootstrap_csrf(make_api):
    api = make_api()
    async with api.client as client:
        response = await client.get("/unauthenticated")
        assert response.status_code == 401
        assert response.headers["X-CSRF-Token"] == client.cookies["csrf_token"]


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:18080", "http://127.0.0.1:8080", "http://192.168.1.10:8080"],
)
async def test_local_browser_can_bootstrap_csrf_and_write(make_api, origin):
    api = make_api(base_url=origin)
    async with api.client as client:
        bootstrap = await client.get(
            "/unauthenticated", headers={"Referer": f"{origin}/studio"}
        )
        assert bootstrap.status_code == 401
        token = bootstrap.headers["X-CSRF-Token"]
        assert client.cookies["csrf_token"] == token
        response = await client.post(
            "/write",
            json={"ok": True},
            headers={
                "Origin": origin,
                "Referer": f"{origin}/studio",
                "X-CSRF-Token": token,
            },
        )
        assert response.status_code == 200
        assert api.calls == 1


async def test_local_browser_origin_still_requires_csrf(make_api):
    origin = "http://localhost:18080"
    api = make_api(base_url=origin)
    async with api.client as client:
        response = await client.post(
            "/write", json={}, headers={"Origin": origin, "Referer": f"{origin}/"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF validation failed"
        assert api.calls == 0


async def test_local_browser_cannot_write_from_another_origin(make_api):
    api = make_api(base_url="http://localhost:18080")
    async with api.client as client:
        bootstrap = await client.get("/check")
        response = await client.post(
            "/write",
            json={},
            headers={
                "Origin": "http://localhost:18081",
                "Referer": "http://localhost:18081/",
                "X-CSRF-Token": bootstrap.headers["X-CSRF-Token"],
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF validation failed"
        assert api.calls == 1


@pytest.mark.parametrize("header", [None, "incorrect", "токен"])
async def test_write_rejects_missing_or_incorrect_csrf(make_api, header):
    api = make_api()
    async with api.client as client:
        await client.get("/check")
        headers = {} if header is None else {"X-CSRF-Token": header.encode()}
        response = await client.post("/write", json={"ok": True}, headers=headers)
        assert response.status_code == 403
        assert api.calls == 1


async def test_write_accepts_cookie_and_matching_header(make_api):
    api = make_api()
    async with api.client as client:
        bootstrap = await client.get("/check")
        response = await client.post(
            "/write",
            json={"prompt": "A sign reading <script>alert(1)</script>"},
            headers={"X-CSRF-Token": bootstrap.headers["X-CSRF-Token"]},
        )
        assert response.status_code == 200
        assert response.json()["prompt"].startswith("A sign")


async def test_forged_matching_csrf_cookie_is_rejected(make_api):
    api = make_api()
    async with api.client as client:
        token = "a" * 64 + "." + "b" * 64
        client.cookies.set("csrf_token", token)
        response = await client.post("/write", json={}, headers={"X-CSRF-Token": token})
        assert response.status_code == 403
        assert api.calls == 0


@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
async def test_untrusted_origin_is_rejected_even_with_valid_csrf(make_api, origin):
    api = make_api()
    async with api.client as client:
        bootstrap = await client.get("/check")
        response = await client.post(
            "/write",
            json={},
            headers={
                "Origin": origin,
                "X-CSRF-Token": bootstrap.headers["X-CSRF-Token"],
            },
        )
        assert response.status_code == 403
        assert "Access-Control-Allow-Origin" not in response.headers


async def test_cors_exposes_csrf_to_allowed_frontend_including_errors(make_api):
    api = make_api()
    async with api.client as client:
        response = await client.get(
            "/check", headers={"Origin": "https://frontend.example"}
        )
        assert (
            response.headers["Access-Control-Allow-Origin"]
            == "https://frontend.example"
        )
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert "X-CSRF-Token" in response.headers["Access-Control-Expose-Headers"]
        denied = await client.post(
            "/write", json={}, headers={"Origin": "https://frontend.example"}
        )
        assert denied.status_code == 403
        assert (
            denied.headers["Access-Control-Allow-Origin"] == "https://frontend.example"
        )


async def test_cors_preflight_needs_no_csrf_or_authentication(make_api):
    api = make_api()
    async with api.client as client:
        response = await client.options(
            "/write",
            headers={
                "Origin": "https://frontend.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["Access-Control-Allow-Origin"]
            == "https://frontend.example"
        )
        assert api.calls == 0


async def test_csrf_disabled_does_not_issue_cookie(make_api):
    api = make_api(CSRF_ENABLED=False)
    async with api.client as client:
        response = await client.post("/write", json={})
        assert response.status_code == 200
        assert "set-cookie" not in response.headers


async def test_webhook_body_passes_unchanged_without_csrf(make_api):
    api = make_api()
    body = b'{ "OrderId": "signed", "text": "<script>alert(1)</script>" }\n'
    async with api.client as client:
        response = await client.post(
            "/payments/webhooks/atlos",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["body"].encode() == body
        assert "set-cookie" not in response.headers
        denied = await client.post("/payments/webhooks/atlos/extra", json={})
        assert denied.status_code == 403


async def test_cookie_jwt_does_not_trigger_attack_detection(make_api):
    api = make_api()
    token = JwtProvider(api.settings.JWT_TOKEN_SETTINGS).create_access_token(
        {"sub": "018f2429-aaca-7c21-b0a3-2fbef2bbd331", "scope": "user"}
    )
    async with api.client as client:
        client.cookies.set(api.settings.API_SETTINGS.CLIENT_ACCESS_TOKEN_COOKIE, token)
        response = await client.get("/check")
        assert response.status_code == 200


async def test_rate_limit_is_enforced_and_cors_headers_survive(make_api):
    api = make_api(SECURITY_RATE_LIMIT=2)
    async with api.client as client:
        assert (await client.get("/check")).status_code == 200
        assert (await client.get("/check")).status_code == 200
        response = await client.get(
            "/check", headers={"Origin": "https://frontend.example"}
        )
        assert response.status_code == 429
        assert (
            response.headers["Access-Control-Allow-Origin"]
            == "https://frontend.example"
        )
        assert api.calls == 2


async def test_forwarded_ip_cannot_bypass_limit_from_untrusted_client(make_api):
    api = make_api(SECURITY_RATE_LIMIT=1)
    async with api.client as client:
        assert (await client.get("/check")).status_code == 200
        response = await client.get(
            "/check", headers={"X-Forwarded-For": "203.0.113.7"}
        )
        assert response.status_code == 429


async def test_forwarded_ip_is_used_from_configured_proxy(make_api):
    api = make_api(SECURITY_RATE_LIMIT=1, SECURITY_TRUSTED_PROXIES="198.51.100.10")
    async with api.client as client:
        first = await client.get("/check", headers={"X-Forwarded-For": "203.0.113.7"})
        second = await client.get("/check", headers={"X-Forwarded-For": "203.0.113.8"})
        third = await client.get("/check", headers={"X-Forwarded-For": "203.0.113.7"})
        assert first.status_code == second.status_code == 200
        assert third.status_code == 429


@pytest.mark.parametrize("referer", [None, "http://localhost:18080/studio"])
async def test_query_attack_is_blocked_and_repeated_attacker_is_banned(
    make_api, referer
):
    api = make_api(SECURITY_AUTO_BAN_THRESHOLD=2)
    async with api.client as client:
        for expected in (400, 403):
            response = await client.get(
                "/check",
                params={"q": "<script>alert(1)</script>"},
                headers={} if referer is None else {"Referer": referer},
            )
            assert response.status_code == expected
        response = await client.get("/check")
        assert response.status_code == 403
        assert api.calls == 0


async def test_blocked_user_agent_is_enforced(make_api):
    api = make_api(SECURITY_BLOCKED_USER_AGENTS="BadBot")
    async with api.client as client:
        response = await client.get("/check", headers={"User-Agent": "BadBot"})
        assert response.status_code == 403
        assert api.calls == 0


async def test_https_cannot_be_spoofed_by_untrusted_client(make_api):
    api = make_api(base_url="http://api.example", SECURITY_ENFORCE_HTTPS=True)
    async with api.client as client:
        response = await client.get("/check", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 301
        assert response.headers["Location"] == "https://api.example/check"
        assert api.calls == 0


async def test_https_is_recognized_from_trusted_proxy(make_api):
    api = make_api(
        base_url="http://api.example",
        SECURITY_ENFORCE_HTTPS=True,
        SECURITY_TRUSTED_PROXIES="198.51.100.10",
    )
    async with api.client as client:
        response = await client.get("/check", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 200
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


async def test_passive_mode_still_enforces_csrf(make_api):
    api = make_api(SECURITY_PASSIVE_MODE=True)
    async with api.client as client:
        response = await client.post("/write", json={})
        assert response.status_code == 403


async def test_redis_failure_returns_503_instead_of_disabling_guard(
    make_api, monkeypatch
):
    api = make_api()
    api.settings.API_SETTINGS.SECURITY_REDIS_ENABLED = True
    app = FastAPI()
    configure_guard(app, api.settings)
    monkeypatch.setattr(
        "guard_core.handlers.redis_handler.RedisManager.initialize",
        AsyncMock(side_effect=GuardRedisError(503, "Redis unavailable")),
    )
    async with api.client:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.example"
        ) as client:
            response = await client.get("/check")
            assert response.status_code == 503


@pytest.mark.parametrize(
    "origin", ["*", "https://*.example", "https://app.example/path"]
)
def test_wildcard_or_path_cors_origins_are_rejected(origin):
    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None, CORS_ALLOWED_ORIGINS=origin)


@pytest.mark.parametrize(
    "name",
    [
        "SECURITY_RATE_LIMIT_WINDOW",
        "SECURITY_AUTO_BAN_THRESHOLD",
        "SECURITY_AUTO_BAN_DURATION",
    ],
)
def test_invalid_security_limits_are_rejected(name):
    with pytest.raises(ValidationError):
        ApiSettings(_env_file=None, **{name: 0})


async def test_telegram_miniapp_auth_is_csrf_exempt(make_api):
    api = make_api()
    async with api.client as client:
        response = await client.post(
            "/users/auth/telegram-webapp", json={"init_data": "signed"}
        )
        assert response.status_code != 403
        assert response.json().get("detail") != "CSRF validation failed"
