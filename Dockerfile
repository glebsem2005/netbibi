# syntax=docker/dockerfile:1.7

# ---------- builder ----------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Install the package itself
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# Identifies images belonging to this project so the VPS-side cleanup
# cron can prune only our images and leave neighbouring projects alone.
LABEL org.opencontainers.image.source="https://github.com/glebsem2005/netbibi"

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --link --from=builder /app/.venv /app/.venv
COPY --link src/netbibi /app/src/netbibi
COPY --link unique_words.csv /app/data/unique_words.csv

RUN mkdir -p /app/output /app/logs && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import netbibi" || exit 1

ENTRYPOINT ["python", "-m", "netbibi"]
