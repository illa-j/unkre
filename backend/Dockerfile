# syntax=docker/dockerfile:1

# Build the virtualenv from the lockfile. The project is a src-layout
# application, not an installable package, so uv is told not to install it.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY scripts ./scripts

FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PATH=/opt/venv/bin:$PATH

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=build --chown=app:app /opt/venv /opt/venv
COPY --from=build --chown=app:app /app/src ./src
COPY --from=build --chown=app:app /app/scripts ./scripts

USER app
EXPOSE 8000

# API_WORKERS is read by the shell command, not by application settings.
CMD ["sh", "-c", "exec uvicorn adapters.api.main:app --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-2}"]
