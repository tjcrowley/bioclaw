# syntax=docker/dockerfile:1

# --- Stage: main venv (root project, Python 3.13) ---
FROM python:3.13-slim AS main-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra web --no-install-project
COPY . .
RUN uv sync --frozen --extra web

# --- Final runtime stage ---
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=main-builder /app /app
RUN chmod +x /app/docker/entrypoint.sh
ENV BIOCLAW_STORE_ROOT=/app/state/data
ENV BIOCLAW_MEMORY_DB=/app/state/agent/memory.sqlite
ENV BIOCLAW_LOG_PATH=/app/state/tool_calls.jsonl
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
