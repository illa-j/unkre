from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from adapters.settings import Settings

logger = logging.getLogger(__name__)

_REDIS_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window: int
    scope: str


DEFAULT_POLICY = RateLimitPolicy(limit=300, window=60, scope="default")


def route_policy(method: str, path: str) -> RateLimitPolicy:
    """Return the per-route budget for an API request.

    The global fastapi-guard limit remains the outer safety net. These rules
    make expensive or credential-sensitive endpoints stricter than the rest.
    """
    if path == "/healthz":
        return RateLimitPolicy(120, 60, "health")
    if path.startswith("/users/auth/"):
        if path == "/users/auth/refresh":
            return RateLimitPolicy(60, 60, "auth-refresh")
        return RateLimitPolicy(10, 60, "auth")
    if path == "/users/me":
        return RateLimitPolicy(120, 60, "account")
    if path.startswith("/payments/webhooks/"):
        return RateLimitPolicy(300, 60, "payment-webhook")
    if path.startswith("/payments"):
        return RateLimitPolicy(20 if method == "POST" else 120, 60, "payments")
    if path == "/generations" and method == "POST":
        return RateLimitPolicy(10, 60, "generation-create")
    if path.startswith("/generations"):
        return RateLimitPolicy(120, 60, "generation-read")
    if path.startswith("/presets"):
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            return RateLimitPolicy(30, 60, "preset-write")
        return RateLimitPolicy(120, 60, "preset-read")
    if path.startswith("/promos"):
        return RateLimitPolicy(15, 60, "promo")
    if path.startswith("/referrals"):
        return RateLimitPolicy(60, 60, "referral")
    if path.startswith("/workflows"):
        return RateLimitPolicy(120, 60, "workflow")
    if path.startswith("/admins"):
        return RateLimitPolicy(300, 60, "admin")
    return DEFAULT_POLICY


def client_ip(request: Request) -> str:
    """Use the address nginx forwards, falling back to the socket peer."""
    candidates = (
        request.headers.get("x-real-ip", ""),
        request.headers.get("cf-connecting-ip", ""),
        request.client.host if request.client else "",
    )
    for value in candidates:
        try:
            return ipaddress.ip_address(value.strip()).compressed
        except ValueError:
            continue
    return "unknown"


class RateLimiter:
    def __init__(self, *, redis_url: str | None, prefix: str, use_redis: bool) -> None:
        self._redis = (
            Redis.from_url(redis_url, decode_responses=True)
            if use_redis and redis_url
            else None
        )
        self._prefix = prefix
        self._memory: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def hit(
        self, key: str, limit: int, window: int
    ) -> tuple[bool, int, int]:
        count = await self._increment(key, window)
        remaining = max(0, limit - count)
        return count <= limit, remaining, window

    async def _increment(self, key: str, window: int) -> int:
        if self._redis is None:
            return await self._increment_memory(key, window)
        try:
            return int(
                await self._redis.eval(
                    _REDIS_WINDOW_SCRIPT, 1, key, str(window)
                )
            )
        except RedisError:
            # The guard already fails closed when Redis is required. Keep the
            # process-local limiter as a defence in depth instead of turning a
            # Redis outage into an application outage.
            logger.warning("route rate limiter Redis unavailable; using process memory")
            return await self._increment_memory(key, window)

    async def _increment_memory(self, key: str, window: int) -> int:
        now = time.monotonic()
        async with self._lock:
            count, reset_at = self._memory.get(key, (0, now + window))
            if now >= reset_at:
                count, reset_at = 0, now + window
            count += 1
            self._memory[key] = (count, reset_at)
            if len(self._memory) > 10_000:
                self._memory = {
                    name: value
                    for name, value in self._memory.items()
                    if value[1] > now
                }
            return count

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()


class RouteRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        api = settings.API_SETTINGS
        self._enabled = api.SECURITY_ROUTE_RATE_LIMIT_ENABLED
        self._prefix = f"{api.SECURITY_REDIS_PREFIX}route:"
        self._limiter = RateLimiter(
            redis_url=settings.TASK_QUEUE_SETTINGS.REDIS_URL,
            prefix=self._prefix,
            use_redis=api.SECURITY_REDIS_ENABLED,
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._enabled or request.method == "OPTIONS":
            return await call_next(request)

        policy = route_policy(request.method, request.url.path)
        key = f"{self._prefix}{policy.scope}:{client_ip(request)}"
        allowed, remaining, window = await self._limiter.hit(
            key, policy.limit, policy.window
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests; please try again later"},
                headers={
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(policy.limit),
                    "X-RateLimit-Remaining": "0",
                    "Cache-Control": "no-store",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(policy.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
