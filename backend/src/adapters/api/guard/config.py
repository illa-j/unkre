from functools import partial

from fastapi import FastAPI
from guard import SecurityConfig, SecurityMiddleware

from adapters.api.guard.referer import OmitRefererMiddleware
from adapters.api.middlewares import csrf_middleware
from adapters.settings import Settings


def create_security_config(settings: Settings) -> SecurityConfig:
    api = settings.API_SETTINGS
    return SecurityConfig(
        enable_redis=api.SECURITY_REDIS_ENABLED,
        redis_url=settings.TASK_QUEUE_SETTINGS.REDIS_URL,
        redis_prefix=api.SECURITY_REDIS_PREFIX,
        redis_fail_open=False,
        enable_rate_limiting=True,
        rate_limit=api.SECURITY_RATE_LIMIT,
        rate_limit_window=api.SECURITY_RATE_LIMIT_WINDOW,
        enable_ip_banning=True,
        auto_ban_threshold=api.SECURITY_AUTO_BAN_THRESHOLD,
        auto_ban_duration=api.SECURITY_AUTO_BAN_DURATION,
        blocked_user_agents=[
            value.strip()
            for value in api.SECURITY_BLOCKED_USER_AGENTS.split(",")
            if value.strip()
        ],
        trusted_proxies=tuple(
            value.strip()
            for value in api.SECURITY_TRUSTED_PROXIES.split(",")
            if value.strip()
        ),
        trust_x_forwarded_proto=bool(api.SECURITY_TRUSTED_PROXIES.strip()),
        enforce_https=api.SECURITY_ENFORCE_HTTPS,
        passive_mode=api.SECURITY_PASSIVE_MODE,
        enable_cors=True,
        cors_allow_origins=[
            origin for origin in api.CORS_ALLOWED_ORIGINS.split(",") if origin
        ],
        cors_allow_credentials=True,
        cors_allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        cors_allow_headers=["Content-Type", api.CSRF_HEADER_NAME],
        cors_expose_headers=[api.CSRF_HEADER_NAME, "Retry-After"],
        exclude_paths=[],
        enable_penetration_detection=True,
        # Prompts, credentials and signed webhook bodies are validated by the API.
        detection_scan_body=False,
        excluded_semantic_detection_headers={"cookie"},
        log_sensitive_headers={
            "cookie",
            api.CSRF_HEADER_NAME.lower(),
            "signature",
            "x-telegram-bot-api-secret-token",
        },
        security_headers={
            "enabled": True,
            "hsts": {"max_age": 31536000, "include_subdomains": True}
            if api.SECURITY_ENFORCE_HTTPS
            else None,
        },
    )


def configure_guard(app: FastAPI, settings: Settings) -> None:
    app.middleware("http")(partial(csrf_middleware, settings=settings))
    app.add_middleware(SecurityMiddleware, config=create_security_config(settings))
    app.add_middleware(OmitRefererMiddleware)
