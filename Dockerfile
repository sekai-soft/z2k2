# https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile

# Multi-stage build: First build the application with uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
 --mount=type=bind,source=uv.lock,target=uv.lock \
 --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
 uv sync --frozen --no-install-project --no-dev

ADD . /app

RUN --mount=type=cache,target=/root/.cache/uv \
 uv sync --frozen --no-dev

# Then, use a final image without uv
FROM python:3.13-slim-bookworm
# It is important to use the image that matches the builder, as the path to the
# Python executable must be the same.

# Copy the application from the builder
COPY --from=builder --chown=app:app /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Expose port
EXPOSE 8000

CMD ["fastapi", "run", "app.py", "--port", "8000", "--proxy-headers"]
