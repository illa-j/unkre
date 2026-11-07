import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import FastAPI

from adapters.api.dependencies.settings import get_app_settings
from adapters.api.dependencies.user import get_user_service
from adapters.api.middlewares import authentication_middleware
from adapters.api.routes.user import router
from adapters.settings import ApiSettings, BotSettings, Settings
from domain.entities.auth import AuthProvider, UserSession
from domain.entities.user import User

TOKEN = "777:route-test-token"


def init_data() -> str:
    fields = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "query_id": "AAHdF6IQAAAAAN0Xoha",
        "user": json.dumps(
            {
                "id": 42,
                "first_name": "Route",
                "username": "route_user",
                "is_premium": True,
                "allows_write_to_pm": True,
            },
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class FakeService:
    def __init__(self) -> None:
        self.identity = None
        self.referral = None

    async def login_miniapp(self, identity, referral_code=None):
        self.identity = identity
        self.referral = referral_code
        return UserSession(
            user=User(id=uuid4(), first_name=identity.first_name, telegram_id=42),
            access_token="access",
            refresh_token="refresh",
            expires_in=900,
            is_new_user=True,
        )


def app_with(settings: Settings, service) -> FastAPI:
    app = FastAPI()
    app.middleware("http")(authentication_middleware)
    app.include_router(router)
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_user_service] = lambda: service
    return app


def settings() -> Settings:
    return Settings(
        API_SETTINGS=ApiSettings(CSRF_ENABLED=False, SECURITY_REDIS_ENABLED=False),
        BOT_SETTINGS=BotSettings(
            TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_MINIAPP_URL="https://example.com/studio"
        ),
    )


async def test_route_logs_in_with_verified_init_data():
    service = FakeService()
    app = app_with(settings(), service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        response = await client.post(
            "/users/auth/telegram-webapp",
            json={"init_data": init_data(), "referral_code": "abc123"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_new_user"] is True
    assert body["user"]["telegram_id"] == 42
    assert service.identity.provider == AuthProvider.TELEGRAM
    assert service.identity.telegram_id == 42
    assert service.identity.is_premium is True
    assert service.identity.allows_write_to_pm is True
    assert service.identity.added_to_attachment_menu is None
    assert service.referral == "abc123"
    assert any(cookie.startswith("cl_access_token=") for cookie in response.headers.get_list("set-cookie"))


async def test_route_rejects_tampered_init_data():
    service = FakeService()
    app = app_with(settings(), service)
    payload = init_data().replace("Route", "Fake")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.example"
    ) as client:
        response = await client.post(
            "/users/auth/telegram-webapp", json={"init_data": payload}
        )

    assert response.status_code == 401
    assert service.identity is None
