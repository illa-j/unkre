from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.api.rate_limit import (
    RateLimiter,
    RouteRateLimitMiddleware,
    client_ip,
    route_policy,
)


def make_middleware(**overrides):
    api = SimpleNamespace(
        SECURITY_ROUTE_RATE_LIMIT_ENABLED=True,
        SECURITY_REDIS_PREFIX="test:guard:",
        SECURITY_REDIS_ENABLED=False,
        **overrides,
    )
    return SimpleNamespace(
        API_SETTINGS=api,
        TASK_QUEUE_SETTINGS=SimpleNamespace(REDIS_URL="redis://localhost:6379/0"),
    )


def test_route_policy_protects_sensitive_endpoints():
    assert route_policy("POST", "/users/auth/google").limit == 10
    assert route_policy("POST", "/users/auth/refresh").limit == 60
    assert route_policy("POST", "/payments/crypto").limit == 20
    assert route_policy("POST", "/payments/webhooks/atlos").limit == 300
    assert route_policy("POST", "/generations").limit == 10
    assert route_policy("POST", "/presets").limit == 30
    assert route_policy("GET", "/workflows").limit == 120
    assert route_policy("GET", "/anything-else").limit == 300


def test_client_ip_accepts_forwarded_addresses_and_rejects_garbage():
    request = SimpleNamespace(
        headers={"x-real-ip": "203.0.113.10"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(request) == "203.0.113.10"

    request = SimpleNamespace(
        headers={"cf-connecting-ip": "2001:db8::1"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(request) == "2001:db8::1"

    request = SimpleNamespace(
        headers={"x-real-ip": "not-an-ip"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(request) == "127.0.0.1"


@pytest.mark.anyio
async def test_memory_limiter_allows_the_budget_then_blocks():
    limiter = RateLimiter(redis_url=None, prefix="test:", use_redis=False)
    first = [await limiter.hit("key", limit=3, window=60) for _ in range(4)]
    assert [item[0] for item in first] == [True, True, True, False]
    assert first[-1][1] == 0


def test_middleware_returns_429_and_rate_headers():
    app = FastAPI()
    app.add_middleware(RouteRateLimitMiddleware, settings=make_middleware())

    @app.post("/users/auth/challenge")
    async def challenge():
        return {"ok": True}

    with TestClient(app) as client:
        headers = {"X-Real-IP": "203.0.113.20"}
        for _ in range(10):
            response = client.post("/users/auth/challenge", headers=headers)
            assert response.status_code == 200
        blocked = client.post("/users/auth/challenge", headers=headers)
        assert blocked.status_code == 429
        assert blocked.headers["X-RateLimit-Limit"] == "10"
        assert blocked.headers["Retry-After"] == "60"
        assert blocked.json()["detail"].startswith("Too many requests")
